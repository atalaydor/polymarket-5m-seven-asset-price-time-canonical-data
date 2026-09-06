"""Durable inventory-scoped acquisition and certification on GitHub Actions."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import platform
import re
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pflow.inventory import discover, validate_inventory
from pflow.model import micros
from pflow.observed_v1 import (
    CERTIFICATION_SCOPE,
    MAPPING_SCHEMA,
    OBSERVATION_SCHEMA,
    PROFILE,
    PROFILE_VERSION,
    RESOLUTION_SCHEMA,
    TRANSFORM,
    iter_jsonl_gzip,
    jsonl_gzip,
    mapping_record,
    observation_record,
    profile_fields,
    read_jsonl_gzip,
    resolution_record,
    select_window,
    validate_mapping,
    validate_observation,
    validate_resolution,
)
from pflow.probe import batches
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import Reader, canonical, fetch_products, sha

MAPPING_PARTITION = "pendulumflow-v3-observed-mapping-partition.v1"
CATALOG_SCHEMA = "pendulumflow-v3-observed-inventory-catalog.v1"
DATA_PARTITION = "pendulumflow-v3-observed-data-partition.v1"
DATA_INDEX_SCHEMA = "pendulumflow-v3-observed-data-index.v1"
DAY_SCHEMA = "pendulumflow-v3-observed-certified-day.v1"
WINDOW_SCHEMA = "pendulumflow-v3-observed-window.v1"
MAPPING_CHUNK = 8
DATA_CHUNK = 4


def _implementation_bundle_digest(files: dict[str, bytes]) -> str:
    return sha(canonical({name: sha(data) for name, data in sorted(files.items())}))


_MODULE_DIR = Path(__file__).parent
_ROOT_DIR = _MODULE_DIR.parents[1]
TRANSFORM_IMPLEMENTATION_FILES = {
    "requirements.lock": _ROOT_DIR / "requirements.lock",
    "src/pflow/model.py": _MODULE_DIR / "model.py",
    "src/pflow/observed_v1.py": _MODULE_DIR / "observed_v1.py",
    "src/pflow/probe.py": _MODULE_DIR / "probe.py",
    "src/pflow/production.py": Path(__file__),
    "src/pflow/source.py": _MODULE_DIR / "source.py",
}
TRANSFORM_IMPLEMENTATION_SHA256 = _implementation_bundle_digest(
    {name: path.read_bytes() for name, path in TRANSFORM_IMPLEMENTATION_FILES.items()}
)
ASSET_ALIASES = {
    "BTC": ("btc", "bitcoin"),
    "ETH": ("eth", "ethereum"),
    "SOL": ("sol", "solana"),
    "XRP": ("xrp",),
    "DOGE": ("doge", "dogecoin"),
    "BNB": ("bnb",),
    "HYPE": ("hype", "hyperliquid"),
}


def _output(name: str, value: Any) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={rendered}\n")
    print(canonical({name: value}).decode(), end="")


def _question_assets(question: Any) -> set[str]:
    if not isinstance(question, str):
        return set()
    normalized = question.lower()
    return {
        asset
        for asset, aliases in ASSET_ALIASES.items()
        if any(re.search(rf"\b{re.escape(alias)}\b", normalized) for alias in aliases)
    }


def _target_like(slug: str, question: Any) -> bool:
    slug_assets = {
        asset
        for asset, aliases in ASSET_ALIASES.items()
        if any(re.search(rf"(?:^|-){re.escape(alias)}(?:-|$)", slug) for alias in aliases)
    }
    slug_five = re.search(r"(?:^|-)5(?:m|-?min|-?minute)(?:-|$)", slug) is not None
    slug_direction = "updown" in slug or ("up" in slug and "down" in slug)
    text = question.lower() if isinstance(question, str) else ""
    question_target = bool(_question_assets(question) and "up" in text and "down" in text)
    question_five = re.search(r"\b5\s*-?\s*(?:m|min|minute)s?\b", text) is not None
    return bool(slug_assets and slug_five and slug_direction) or bool(
        question_target and (not slug or question_five)
    )


def _record_target_error(
    errors: list[dict[str, Any]],
    hour: str,
    ordinal: int,
    slug: str,
    question: Any,
    reason: str,
) -> None:
    detail: dict[str, Any] = {"hour": hour, "ordinal": ordinal, "reason": reason}
    if len(errors) < 20:
        detail["slug_sample"] = slug[:500]
        detail["question_sample"] = question[:500] if isinstance(question, str) else None
    errors.append(detail)


def _chunks(
    hours: list[str],
    size: int,
    kind: str,
    inventory: dict[str, Any],
    transform_implementation_sha256: str = TRANSFORM_IMPLEMENTATION_SHA256,
) -> list[dict[str, str]]:
    manifests = {item["hour"]: item for item in inventory["hours"]}
    result = []
    buckets: dict[int, list[str]] = defaultdict(list)
    for hour in hours:
        instant = datetime.strptime(hour, "%Y-%m-%d/%H").replace(tzinfo=UTC)
        buckets[int(instant.timestamp()) // 3600 // size].append(hour)
    for bucket in sorted(buckets):
        subset = buckets[bucket]
        identity = sha(
            canonical(
                {
                    "kind": kind,
                    "transform": TRANSFORM,
                    "transform_implementation_sha256": transform_implementation_sha256,
                    "sources": {
                        hour: {
                            "manifest_sha256": manifests[hour]["manifest_sha256"],
                            "product": manifests[hour]["manifest"]["products"][
                                "new_market" if kind == "mapping" else "best_bid_ask"
                            ],
                        }
                        for hour in subset
                    },
                    "resolution_sources": {
                        hour: {
                            "manifest_sha256": manifests[hour]["manifest_sha256"],
                            "product": manifests[hour]["manifest"]["products"]["market_resolved"],
                        }
                        for hour in subset
                    }
                    if kind == "data"
                    else None,
                }
            )
        )
        result.append({"id": identity, "hours": ",".join(subset)})
    return result


def _work_batches(items: list[dict[str, str]], maximum_jobs: int = 128) -> list[dict[str, Any]]:
    if not items:
        raise ValueError("empty work plan")
    width = max(1, (len(items) + maximum_jobs - 1) // maximum_jobs)
    return [{"items": items[start : start + width]} for start in range(0, len(items), width)]


def _day_batches(days: list[str], maximum_jobs: int = 128) -> list[dict[str, Any]]:
    if not days:
        raise ValueError("no eligible past market-start day")
    width = max(1, (len(days) + maximum_jobs - 1) // maximum_jobs)
    return [{"days": days[start : start + width]} for start in range(0, len(days), width)]


def _require_chunk(planned: list[dict[str, str]], partition: str, hours: list[str]) -> None:
    matches = [item for item in planned if item["id"] == partition]
    if len(matches) != 1 or matches[0]["hours"].split(",") != hours:
        raise ValueError("supplied partition hours do not match deterministic plan")


def _verify_partition_proofs(
    report: dict[str, Any], inventory: dict[str, Any], hours: list[str], products: tuple[str, ...]
) -> None:
    proofs = report.get("source_integrity")
    if not isinstance(proofs, dict) or set(proofs) != set(hours):
        raise ValueError("partition proof hour coverage mismatch")
    items = {item["hour"]: item for item in inventory["hours"]}
    for hour in hours:
        actual = proofs[hour].get("products")
        if not isinstance(actual, dict) or set(actual) != set(products):
            raise ValueError("partition proof product coverage mismatch")
        for product in products:
            expected = items[hour]["manifest"]["products"][product]
            if any(actual[product].get(name) != expected[name] for name in expected):
                raise ValueError("partition proof manifest binding mismatch")
            if (
                actual[product].get("range_sha256_verified") is not True
                or actual[product].get("footer_binding_checked") is not True
            ):
                raise ValueError("partition product integrity not verified")


def _catalog_dependency(catalog_value: dict[str, Any], encountered: set[str]) -> str:
    fields = ("market", "asset", "start_us", "end_us", "up_token", "down_token")
    relevant = [
        {name: row[name] for name in fields}
        for row in catalog_value["mappings"]
        if row["market"] in encountered
    ]
    return sha(canonical(relevant))


def _encountered(partition: str) -> set[str] | None:
    tag = "observed-conditions-v1-" + partition
    release = api(f"releases/tags/{tag}")
    if release is None or release.get("draft"):
        return None
    _, data = _release_asset(tag, "conditions.jsonl.gz")
    values = {row["market"] for row in iter_jsonl_gzip(data)}
    if any(not isinstance(value, str) or len(value) != 64 for value in values):
        raise ValueError("encountered condition inventory invalid")
    return values


def _release_asset(tag: str, suffix: str) -> tuple[dict[str, Any], bytes]:
    release = api(f"releases/tags/{tag}")
    if release is None or release.get("draft") or not release.get("immutable"):
        raise ValueError(f"immutable release unavailable: {tag}")
    matches = [asset for asset in release["assets"] if asset["name"].endswith("--" + suffix)]
    if len(matches) != 1:
        raise ValueError(f"asset unavailable or ambiguous: {tag}/{suffix}")
    asset = matches[0]
    if asset.get("state") != "uploaded" or asset.get("digest") != "sha256:" + asset["name"][:64]:
        raise ValueError("release asset metadata digest mismatch")
    return release, read_asset(asset)


def _load_json(tag: str, digest: str, suffix: str) -> tuple[dict[str, Any], dict[str, Any]]:
    release, data = _release_asset(tag, suffix)
    if sha(data) != digest:
        raise ValueError("external generation digest mismatch")
    return release, json.loads(data)


def plan() -> dict[str, Any]:
    inventory = discover()
    validate_inventory(inventory)
    payload = canonical(inventory)
    tag = "v3-inventory-v1-" + inventory["generation"]
    release = publish(
        tag,
        {"inventory.json": payload},
        current_commit(),
        "Pinned published PendulumFlow V3 inventory",
        "Complete stable V3 published-index generation. "
        "Scope is served inventory, not venue history.",
    )
    hours = [item["hour"] for item in inventory["hours"]]
    result = {
        "schema": "pendulumflow-v3-production-plan.v1",
        "inventory_tag": tag,
        "inventory_sha256": sha(payload),
        "inventory_generation": inventory["generation"],
        "inventory_release_id": release["id"],
        "hours": len(hours),
        "first_hour": hours[0],
        "last_hour": hours[-1],
        "mapping_chunks": _chunks(hours, MAPPING_CHUNK, "mapping", inventory),
        "data_chunks": _chunks(hours, DATA_CHUNK, "data", inventory),
    }
    result["mapping_batches"] = _work_batches(result["mapping_chunks"])
    result["data_batches"] = _work_batches(result["data_chunks"])
    for key in ("inventory_tag", "inventory_sha256", "inventory_generation"):
        _output(key, result[key])
    _output("mapping_batches", result["mapping_batches"])
    _output("data_batches", result["data_batches"])
    return result


def _inventory(tag: str, digest: str) -> dict[str, Any]:
    _, value = _load_json(tag, digest, "inventory.json")
    validate_inventory(value)
    return value


def _source(manifest_item: dict[str, Any], product: str, ordinal: int) -> dict[str, Any]:
    return {
        "source_hour": manifest_item["hour"],
        "source_manifest_sha256": manifest_item["manifest_sha256"],
        "source_product_sha256": manifest_item["manifest"]["products"][product]["sha256"],
        "source_product_row_ordinal": ordinal,
    }


def _existing_partition(tag: str, schema: str, partition: str) -> dict[str, Any] | None:
    release = api(f"releases/tags/{tag}")
    if release is None:
        return None
    if not release.get("draft") and not release.get("immutable"):
        raise ValueError("existing partition is not immutable")
    reports = [asset for asset in release["assets"] if asset["name"].endswith("--report.json")]
    if release.get("draft") and not reports:
        return None
    if len(reports) != 1:
        raise ValueError("existing partition has no unique report")
    if release.get("draft") and reports[0].get("state") != "uploaded":
        if reports[0].get("size") != 0 or reports[0].get("digest") is not None:
            raise ValueError("incomplete report is not a safe upload starter")
        api(f"releases/assets/{reports[0]['id']}", "DELETE")
        return None
    report = json.loads(read_asset(reports[0], draft=release["draft"]))
    if report.get("schema") != schema or report.get("partition_identity") != partition:
        raise ValueError("existing partition binding differs")
    expected = report.get("payload_assets")
    if not isinstance(expected, dict):
        raise ValueError("partition report lacks exact payload inventory")
    actual = [asset for asset in release["assets"] if asset["id"] != reports[0]["id"]]
    if {
        asset["name"].split("--", 1)[1]: {
            "sha256": asset["name"].split("--", 1)[0],
            "size": asset["size"],
        }
        for asset in actual
    } != expected:
        raise ValueError("partition payload inventory differs")
    if release["draft"]:
        for asset in release["assets"]:
            read_asset(asset, draft=True)
        release = api(
            f"releases/{release['id']}", "PATCH", {"draft": False, "make_latest": "false"}
        )
        verify_release(release)
    print(canonical({"checkpoint_reused": True, "tag": tag, "new_source_bytes": 0}).decode())
    return dict(release)


def mapping_shard(inventory_tag: str, inventory_sha: str, chunk: str, partition: str) -> None:
    inventory = _inventory(inventory_tag, inventory_sha)
    hours = chunk.split(",")
    planned = _chunks([i["hour"] for i in inventory["hours"]], MAPPING_CHUNK, "mapping", inventory)
    _require_chunk(planned, partition, hours)
    tag = "observed-mapping-v1-" + partition
    if _existing_partition(tag, MAPPING_PARTITION, partition):
        return
    items = {item["hour"]: item for item in inventory["hours"]}
    reader = Reader(limit=1_900_000_000)
    rows: list[dict[str, Any]] = []
    condition_rows: list[dict[str, Any]] = []
    target_like_errors: list[dict[str, Any]] = []
    classifications = Counter[str]()
    decoded = 0
    proofs: dict[str, Any] = {}
    started = time.monotonic()
    work = Path("work") / partition
    for hour in hours:
        item = items[hour]
        path = work / (hour.replace("/", "T") + ".parquet")
        parquet, proof = fetch_products(reader, item["manifest"], ("new_market",), path)
        proofs[hour] = proof
        ordinal = 0
        for batch in batches(parquet, item["manifest"], "new_market"):
            for source_row in batch.to_pylist():
                decoded += 1
                if source_row.get("event_type") != "new_market":
                    raise ValueError("decoded event type differs from mapped product")
                slug = str(source_row.get("slug") or "").lower()
                native_market = source_row.get("market")
                market = (
                    native_market.hex()
                    if isinstance(native_market, bytes) and len(native_market) == 32
                    else None
                )
                disposition = "out_of_scope"

                try:
                    record = mapping_record(source_row, _source(item, "new_market", ordinal))
                except (ValueError, TypeError, AttributeError, KeyError) as exc:
                    if _target_like(slug, source_row.get("question")):
                        disposition = "ambiguous_target_like"
                        classifications["ambiguous_target_like"] += 1
                        _record_target_error(
                            target_like_errors,
                            hour,
                            ordinal,
                            slug,
                            source_row.get("question"),
                            str(exc),
                        )
                    else:
                        classifications["out_of_scope"] += 1
                    if market is not None:
                        condition_rows.append(
                            {
                                "market": market,
                                "disposition": disposition,
                                "source_hour": hour,
                                "source_product_row_ordinal": ordinal,
                            }
                        )
                    ordinal += 1
                    continue
                if record is not None:
                    question_assets = _question_assets(source_row.get("question"))
                    if question_assets and question_assets != {record["asset"]}:
                        disposition = "ambiguous_target_like"
                        classifications["ambiguous_target_like"] += 1
                        _record_target_error(
                            target_like_errors,
                            hour,
                            ordinal,
                            slug,
                            source_row.get("question"),
                            "question asset contradicts canonical target slug",
                        )
                    else:
                        disposition = "in_scope_target"
                        classifications["in_scope_target"] += 1
                        rows.append(record)
                elif _target_like(slug, source_row.get("question")):
                    disposition = "ambiguous_target_like"
                    classifications["ambiguous_target_like"] += 1
                    _record_target_error(
                        target_like_errors,
                        hour,
                        ordinal,
                        slug,
                        source_row.get("question"),
                        "target-like slug does not match frozen identity rule",
                    )
                else:
                    classifications["out_of_scope"] += 1
                if market is not None:
                    condition_rows.append(
                        {
                            "market": market,
                            "disposition": disposition,
                            "source_hour": hour,
                            "source_product_row_ordinal": ordinal,
                        }
                    )
                ordinal += 1
        parquet.close()
        path.unlink()
    rows.sort(
        key=lambda row: (
            row["market"],
            row["archive_receipt_us"],
            row["source_hour"],
            row["source_product_row_ordinal"],
        )
    )
    data = jsonl_gzip(rows)
    condition_rows.sort(
        key=lambda row: (
            row["market"],
            row["source_hour"],
            row["source_product_row_ordinal"],
        )
    )
    condition_data = jsonl_gzip(condition_rows)
    report = {
        "schema": MAPPING_PARTITION,
        "partition_identity": partition,
        "transform": TRANSFORM,
        "transform_implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        "implementation_commit": current_commit(),
        "inventory_generation": inventory["generation"],
        "hours": hours,
        "decoded_new_market_rows": decoded,
        "target_mapping_rows": len(rows),
        "condition_classification_rows": len(condition_rows),
        "target_like_errors": target_like_errors,
        "classification_counts": dict(classifications),
        "source_integrity": proofs,
        "downloaded_bytes": reader.downloaded,
        "network_seconds": sum(item["seconds"] for item in reader.measurements),
        "wall_seconds": time.monotonic() - started,
        "runner": {"os": platform.system(), "run_id": os.environ.get("GITHUB_RUN_ID")},
        "payload_assets": {
            "condition-classifications.jsonl.gz": {
                "sha256": sha(condition_data),
                "size": len(condition_data),
            },
            "mappings.jsonl.gz": {"sha256": sha(data), "size": len(data)},
        },
    }
    publish(
        tag,
        {
            "condition-classifications.jsonl.gz": condition_data,
            "mappings.jsonl.gz": data,
            "report.json": canonical(report),
        },
        current_commit(),
        "Observed v1 mapping staging " + partition[:12],
        "Durable content-addressed staging; no day authority.",
    )


def catalog(inventory_tag: str, inventory_sha: str, max_days: int) -> dict[str, Any]:
    inventory = _inventory(inventory_tag, inventory_sha)
    inventory_release = api(f"releases/tags/{inventory_tag}")
    if inventory_release is None or not inventory_release.get("immutable"):
        raise ValueError("catalog inventory release unavailable")
    hours = [item["hour"] for item in inventory["hours"]]
    partitions = _chunks(hours, MAPPING_CHUNK, "mapping", inventory)
    all_rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    condition_dispositions: dict[str, set[str]] = defaultdict(set)
    errors: list[dict[str, Any]] = []
    for part in partitions:
        tag = "observed-mapping-v1-" + part["id"]
        release, report_data = _release_asset(tag, "report.json")
        report = json.loads(report_data)
        if report.get("partition_identity") != part["id"] or report.get("hours") != part[
            "hours"
        ].split(","):
            raise ValueError("mapping partition report binding mismatch")
        _verify_partition_proofs(report, inventory, part["hours"].split(","), ("new_market",))
        expected_decoded = sum(
            next(item for item in inventory["hours"] if item["hour"] == hour)["manifest"][
                "products"
            ]["new_market"]["row_count"]
            for hour in part["hours"].split(",")
        )
        if report.get("decoded_new_market_rows") != expected_decoded:
            raise ValueError("new_market decoded row accounting mismatch")
        if sum(report.get("classification_counts", {}).values()) != report.get(
            "decoded_new_market_rows"
        ):
            raise ValueError("new_market classification accounting incomplete")
        if report.get("classification_counts", {}).get("ambiguous_target_like", 0):
            raise ValueError(
                "ambiguous target-like new_market classification: "
                + canonical(report.get("target_like_errors", [])[:5]).decode().strip()
            )
        _, rows_data = _release_asset(tag, "mappings.jsonl.gz")
        _, condition_data = _release_asset(tag, "condition-classifications.jsonl.gz")
        rows = read_jsonl_gzip(rows_data)
        for row in rows:
            validate_mapping(row)
        all_rows.extend(rows)
        classified_conditions = read_jsonl_gzip(condition_data)
        if len(classified_conditions) != report.get("condition_classification_rows"):
            raise ValueError("condition classification row accounting mismatch")
        for classified in classified_conditions:
            if (
                set(classified)
                != {
                    "market",
                    "disposition",
                    "source_hour",
                    "source_product_row_ordinal",
                }
                or not re.fullmatch(r"[0-9a-f]{64}", classified.get("market", ""))
                or classified.get("disposition")
                not in {"in_scope_target", "out_of_scope", "ambiguous_target_like"}
                or classified.get("source_hour") not in part["hours"].split(",")
                or type(classified.get("source_product_row_ordinal")) is not int
                or classified["source_product_row_ordinal"] < 0
            ):
                raise ValueError("invalid condition classification row")
            condition_dispositions[classified["market"]].add(classified["disposition"])
        errors.extend(report["target_like_errors"])
        sources.append(
            {
                "partition": part["id"],
                "release_id": release["id"],
                "rows_sha256": sha(rows_data),
                "condition_rows_sha256": sha(condition_data),
                "report_sha256": sha(report_data),
            }
        )
    if errors:
        raise ValueError("ambiguous target-like new_market rows in pinned inventory")
    contradictory_dispositions = sorted(
        market for market, dispositions in condition_dispositions.items() if len(dispositions) != 1
    )
    if contradictory_dispositions:
        raise ValueError("contradictory condition disposition in pinned inventory")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        grouped[row["market"]].append(row)
    selected: list[dict[str, Any]] = []
    conflicts: list[str] = []
    core = (
        "asset",
        "slug",
        "market",
        "venue_market_id",
        "start_us",
        "end_us",
        "up_token",
        "down_token",
        "interval_basis",
    )
    for market, rows in grouped.items():
        if len({tuple(row[name] for name in core) for row in rows}) != 1:
            conflicts.append(market)
            continue
        selected.append(
            min(
                rows,
                key=lambda row: (
                    row["archive_receipt_us"],
                    row["source_hour"],
                    row["source_product_row_ordinal"],
                ),
            )
        )
    if conflicts:
        raise ValueError("contradictory target mappings in pinned inventory")
    if {
        market
        for market, dispositions in condition_dispositions.items()
        if dispositions == {"in_scope_target"}
    } != set(grouped):
        raise ValueError("target mapping/condition disposition closure invalid")
    selected.sort(key=lambda row: (row["start_us"], row["asset"], row["market"]))
    day_counts = Counter(
        datetime.fromtimestamp(row["start_us"] / 1_000_000, UTC).date().isoformat()
        for row in selected
    )
    today = datetime.now(UTC).date().isoformat()
    days = sorted(day for day in day_counts if day < today)
    if max_days > 0:
        days = days[-max_days:]
    value = {
        "schema": CATALOG_SCHEMA,
        **profile_fields(),
        "transform": TRANSFORM,
        "transform_implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        "implementation_commit": current_commit(),
        "inventory_generation": inventory["generation"],
        "inventory_first_hour": hours[0],
        "inventory_last_hour": hours[-1],
        "inventory_tag": inventory_tag,
        "inventory_sha256": inventory_sha,
        "inventory_release_id": inventory_release["id"],
        "claim": (
            "all target new_market rows discovered in every receipt-hour "
            "of this pinned published V3 inventory"
        ),
        "claim_limit": "not proof of exhaustive historical Polymarket listings",
        "mapping_partition_sources": sources,
        "source_condition_classifications": [
            {"market": market, "disposition": next(iter(dispositions))}
            for market, dispositions in sorted(condition_dispositions.items())
        ],
        "mappings": selected,
        "duplicate_same_identity_rows_retained_in_partition_evidence": len(all_rows)
        - len(selected),
        "market_counts_by_start_day": dict(sorted(day_counts.items())),
    }
    payload = canonical(value)
    generation = sha(payload)
    value["generation"] = generation
    payload = canonical(value)
    tag = "observed-catalog-v1-" + generation
    release = publish(
        tag,
        {"catalog.json": payload},
        current_commit(),
        "Pinned V3 observed target catalog",
        "Source-inventory-scoped target lifecycle catalog; no venue completeness claim.",
    )
    for key, output in (
        ("catalog_tag", tag),
        ("catalog_sha256", sha(payload)),
        ("catalog_generation", generation),
        ("day_batches", _day_batches(days)),
    ):
        _output(key, output)
    return {
        "tag": tag,
        "sha256": sha(payload),
        "generation": generation,
        "days": days,
        "release_id": release["id"],
    }


def data_shard(
    inventory_tag: str,
    inventory_sha: str,
    catalog_tag: str,
    catalog_sha: str,
    chunk: str,
    partition: str,
) -> None:
    inventory = _inventory(inventory_tag, inventory_sha)
    _, catalog_value = _load_json(catalog_tag, catalog_sha, "catalog.json")
    mappings = {row["market"]: row for row in catalog_value["mappings"]}
    source_dispositions = {
        row["market"]: row["disposition"]
        for row in catalog_value["source_condition_classifications"]
    }
    hours = chunk.split(",")
    planned = _chunks([i["hour"] for i in inventory["hours"]], DATA_CHUNK, "data", inventory)
    _require_chunk(planned, partition, hours)
    _existing_partition(
        "observed-conditions-v1-" + partition,
        "pendulumflow-v3-encountered-condition-partition.v1",
        partition,
    )
    prior_encountered = _encountered(partition)
    if prior_encountered is not None:
        prior_dependency = _catalog_dependency(catalog_value, prior_encountered)
        prior_binding = sha(
            canonical(
                {
                    "partition": partition,
                    "catalog_dependency": prior_dependency,
                    "transform": TRANSFORM,
                    "transform_implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
                }
            )
        )
        if _existing_partition("observed-data-v1-" + prior_binding, DATA_PARTITION, prior_binding):
            return
    items = {item["hour"]: item for item in inventory["hours"]}
    reader = Reader(limit=5_000_000_000)
    writers: dict[str, gzip.GzipFile] = {}
    day_paths: dict[str, Path] = {}
    day_counts = Counter[str]()
    errors: list[dict[str, Any]] = []
    noneligible = Counter[str]()
    decoded = Counter[str]()
    proofs: dict[str, Any] = {}
    started = time.monotonic()
    work = Path("work") / partition
    encountered: set[str] = set()
    encountered_rows = Counter[str]()
    classification = Counter[str]()
    for hour in hours:
        item = items[hour]
        path = work / (hour.replace("/", "T") + ".parquet")
        parquet, proof = fetch_products(
            reader, item["manifest"], ("best_bid_ask", "market_resolved"), path
        )
        proofs[hour] = proof
        for product in ("best_bid_ask", "market_resolved"):
            ordinal = 0
            for batch in batches(parquet, item["manifest"], product):
                for source_row in batch.to_pylist():
                    decoded[product] += 1
                    if source_row.get("event_type") != product:
                        raise ValueError("decoded event type differs from data product")
                    market = (
                        source_row["market"].hex() if source_row.get("market") is not None else ""
                    )
                    if market:
                        encountered.add(market)
                        encountered_rows[product] += 1
                    else:
                        classification[product + ":missing_condition"] += 1
                    identity = mappings.get(market)
                    if identity is not None:
                        day = (
                            datetime.fromtimestamp(identity["start_us"] / 1_000_000, UTC)
                            .date()
                            .isoformat()
                        )
                        try:
                            if product == "best_bid_ask":
                                if source_row.get("timestamp") is None:
                                    raise ValueError("best ask missing source event time")
                                event_us = micros(source_row["timestamp"])
                                if not identity["start_us"] <= event_us < identity["end_us"]:
                                    noneligible[day] += 1
                                    classification[product + ":outside_market_interval"] += 1
                                    ordinal += 1
                                    continue
                                record = observation_record(
                                    source_row, identity, _source(item, product, ordinal)
                                )
                            else:
                                record = resolution_record(
                                    source_row, identity, _source(item, product, ordinal)
                                )
                            if day not in writers:
                                day_path = work / (day + ".jsonl.gz")
                                day_paths[day] = day_path
                                writers[day] = gzip.GzipFile(filename=day_path, mode="wb", mtime=0)
                            writers[day].write(canonical(record))
                            day_counts[day] += 1
                            classification[product + ":retained"] += 1
                        except (ValueError, TypeError, AttributeError, KeyError) as exc:
                            classification[product + ":target_error"] += 1
                            errors.append(
                                {
                                    "day": day,
                                    "market": market,
                                    "hour": hour,
                                    "product": product,
                                    "ordinal": ordinal,
                                    "reason": str(exc),
                                }
                            )
                    elif market:
                        disposition = source_dispositions.get(market)
                        if disposition == "out_of_scope":
                            classification[product + ":classified_out_of_scope"] += 1
                        elif disposition == "ambiguous_target_like":
                            classification[product + ":ambiguous_condition"] += 1
                        elif disposition == "in_scope_target":
                            raise ValueError("in-scope condition omitted from target catalog")
                        else:
                            classification[product + ":unresolved_condition"] += 1
                    ordinal += 1
        parquet.close()
        path.unlink()
    for writer in writers.values():
        writer.close()
    if prior_encountered is not None and prior_encountered != encountered:
        raise ValueError("encountered condition inventory changed for identical source partition")
    conditions = jsonl_gzip({"market": market} for market in sorted(encountered))
    condition_report = {
        "schema": "pendulumflow-v3-encountered-condition-partition.v1",
        "partition_identity": partition,
        "hours": hours,
        "condition_count": len(encountered),
        "encountered_rows_by_product": {
            product: encountered_rows[product] for product in ("best_bid_ask", "market_resolved")
        },
        "missing_condition_rows_by_product": {
            product: classification[product + ":missing_condition"]
            for product in ("best_bid_ask", "market_resolved")
        },
        "payload_assets": {
            "conditions.jsonl.gz": {"sha256": sha(conditions), "size": len(conditions)}
        },
    }
    publish(
        "observed-conditions-v1-" + partition,
        {"conditions.jsonl.gz": conditions, "report.json": canonical(condition_report)},
        current_commit(),
        "Encountered condition index " + partition[:12],
        "Exact condition identities seen in hashed products; staging evidence only.",
    )
    catalog_dependency = _catalog_dependency(catalog_value, encountered)
    binding = sha(
        canonical(
            {
                "partition": partition,
                "catalog_dependency": catalog_dependency,
                "transform": TRANSFORM,
                "transform_implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
            }
        )
    )
    tag = "observed-data-v1-" + binding
    payloads = {day + ".jsonl.gz": path.read_bytes() for day, path in sorted(day_paths.items())}
    report = {
        "schema": DATA_PARTITION,
        "partition_identity": binding,
        "source_partition_identity": partition,
        "transform": TRANSFORM,
        "transform_implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        "implementation_commit": current_commit(),
        "inventory_generation": inventory["generation"],
        "inventory_tag": inventory_tag,
        "inventory_sha256": inventory_sha,
        "catalog_generation": catalog_value["generation"],
        "catalog_tag": catalog_tag,
        "catalog_sha256": catalog_sha,
        "catalog_dependency": catalog_dependency,
        "hours": hours,
        "decoded_rows": dict(decoded),
        "classification_counts": dict(classification),
        "retained_rows_by_market_start_day": dict(day_counts),
        "target_errors": errors,
        "noneligible_target_rows_by_day": dict(noneligible),
        "source_integrity": proofs,
        "downloaded_bytes": reader.downloaded,
        "network_seconds": sum(item["seconds"] for item in reader.measurements),
        "wall_seconds": time.monotonic() - started,
        "payload_assets": {
            name: {"sha256": sha(data), "size": len(data)}
            for name, data in sorted(payloads.items())
        },
    }
    payloads["report.json"] = canonical(report)
    publish(
        tag,
        payloads,
        current_commit(),
        "Observed v1 data staging " + binding[:12],
        "Durable depth-free target projection staging; no day authority.",
    )


def data_index(
    inventory_tag: str, inventory_sha: str, catalog_tag: str, catalog_sha: str
) -> dict[str, Any]:
    inventory = _inventory(inventory_tag, inventory_sha)
    _, catalog_value = _load_json(catalog_tag, catalog_sha, "catalog.json")
    parts = _chunks([item["hour"] for item in inventory["hours"]], DATA_CHUNK, "data", inventory)
    entries: list[dict[str, Any]] = []
    totals = Counter[str]()
    classified_conditions = {
        row["market"] for row in catalog_value["source_condition_classifications"]
    }
    unresolved_conditions: set[str] = set()
    unresolved_conditionless_rows = Counter[str]()
    for part in parts:
        part_hours = part["hours"].split(",")
        encountered = _encountered(part["id"])
        if encountered is None:
            raise ValueError("encountered condition partition missing")
        catalog_dependency = _catalog_dependency(catalog_value, encountered)
        unresolved = sorted(encountered - classified_conditions)
        unresolved_conditions.update(unresolved)
        binding = sha(
            canonical(
                {
                    "partition": part["id"],
                    "catalog_dependency": catalog_dependency,
                    "transform": TRANSFORM,
                    "transform_implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
                }
            )
        )
        tag = "observed-data-v1-" + binding
        release, report_data = _release_asset(tag, "report.json")
        report = json.loads(report_data)
        for product in ("best_bid_ask", "market_resolved"):
            unresolved_conditionless_rows[product] += report.get("classification_counts", {}).get(
                product + ":missing_condition", 0
            )
        if (
            report.get("partition_identity") != binding
            or report.get("source_partition_identity") != part["id"]
            or report.get("hours") != part_hours
            or report.get("catalog_dependency") != catalog_dependency
        ):
            raise ValueError("data partition binding mismatch")
        _verify_partition_proofs(report, inventory, part_hours, ("best_bid_ask", "market_resolved"))
        item_by_hour = {item["hour"]: item for item in inventory["hours"]}
        for product in ("best_bid_ask", "market_resolved"):
            expected_decoded = sum(
                item_by_hour[hour]["manifest"]["products"][product]["row_count"]
                for hour in part_hours
            )
            if report.get("decoded_rows", {}).get(product) != expected_decoded:
                raise ValueError("data decoded row accounting mismatch")
        assets = []
        for asset in release["assets"]:
            if asset["state"] != "uploaded" or asset["digest"] != "sha256:" + asset["name"][:64]:
                raise ValueError("data partition release metadata invalid")
            assets.append(
                {
                    "id": asset["id"],
                    "name": asset["name"],
                    "size": asset["size"],
                    "digest": asset["digest"],
                    "browser_download_url": asset["browser_download_url"],
                }
            )
        entries.append(
            {
                "partition": binding,
                "source_partition": part["id"],
                "tag": tag,
                "release_id": release["id"],
                "report_sha256": sha(report_data),
                "assets": assets,
                "errors": report["target_errors"],
                "unresolved_condition_references": unresolved,
                "unresolved_conditionless_rows": {
                    product: report.get("classification_counts", {}).get(
                        product + ":missing_condition", 0
                    )
                    for product in ("best_bid_ask", "market_resolved")
                },
                "measurements": {
                    "downloaded_bytes": report["downloaded_bytes"],
                    "network_seconds": report["network_seconds"],
                    "wall_seconds": report["wall_seconds"],
                },
            }
        )
        totals["downloaded_bytes"] += report["downloaded_bytes"]
        totals["network_seconds_us"] += round(report["network_seconds"] * 1_000_000)
        totals["wall_seconds_us"] += round(report["wall_seconds"] * 1_000_000)
    value = {
        "schema": DATA_INDEX_SCHEMA,
        **profile_fields(),
        "transform": TRANSFORM,
        "transform_implementation_sha256": TRANSFORM_IMPLEMENTATION_SHA256,
        "inventory_generation": inventory["generation"],
        "inventory_tag": inventory_tag,
        "inventory_sha256": inventory_sha,
        "catalog_generation": catalog_value["generation"],
        "catalog_tag": catalog_tag,
        "catalog_sha256": catalog_sha,
        "complete_expected_partition_set": True,
        "target_membership_reconciled": not unresolved_conditions
        and not sum(unresolved_conditionless_rows.values()),
        "unresolved_condition_references": sorted(unresolved_conditions),
        "unresolved_conditionless_rows": dict(unresolved_conditionless_rows),
        "partitions": entries,
        "measurements": dict(totals),
    }
    generation = sha(canonical(value))
    value["generation"] = generation
    payload = canonical(value)
    tag = "observed-data-index-v1-" + generation
    release = publish(
        tag,
        {"data-index.json": payload},
        current_commit(),
        "Complete observed data partition index",
        "Authenticated reconciliation of every planned immutable data partition.",
    )
    for key, output in (
        ("data_index_tag", tag),
        ("data_index_sha256", sha(payload)),
        ("data_index_generation", generation),
    ):
        _output(key, output)
    print(canonical({"release_id": release["id"]}).decode(), end="")
    return value


def _resolution_evidence(
    markets: Iterable[str], winners: dict[str, set[tuple[str, str]]]
) -> tuple[list[str], list[str], int]:
    missing = sorted(market for market in markets if not winners.get(market))
    contradictory = sorted(market for market, values in winners.items() if len(values) > 1)
    count = sum(bool(values) for values in winners.values())
    return missing, contradictory, count


def certify_day(
    catalog_tag: str, catalog_sha: str, index_tag: str, index_sha: str, day: str
) -> dict[str, Any]:
    if day >= datetime.now(UTC).date().isoformat():
        raise ValueError("partial current or future UTC day is ineligible")
    _, catalog_value = _load_json(catalog_tag, catalog_sha, "catalog.json")
    _, index_value = _load_json(index_tag, index_sha, "data-index.json")
    if index_value["catalog_generation"] != catalog_value["generation"]:
        raise ValueError("catalog/data index mismatch")
    mappings = [
        row
        for row in catalog_value["mappings"]
        if datetime.fromtimestamp(row["start_us"] / 1_000_000, UTC).date().isoformat() == day
    ]
    market_map = {row["market"]: row for row in mappings}
    by_side = Counter[tuple[str, str]]()
    by_winner: dict[str, set[tuple[str, str]]] = defaultdict(set)
    observation_count = 0
    errors: list[dict[str, Any]] = []
    source_assets: list[dict[str, Any]] = []
    for part in index_value["partitions"]:
        errors.extend(error for error in part["errors"] if error["day"] == day)
        suffix = "--" + day + ".jsonl.gz"
        matches = [asset for asset in part["assets"] if asset["name"].endswith(suffix)]
        if len(matches) > 1:
            raise ValueError("duplicate day asset in partition")
        if not matches:
            continue
        asset = matches[0]
        data = read_asset(asset)
        source_assets.append(
            {
                "release_id": part["release_id"],
                "asset_id": asset["id"],
                "sha256": sha(data),
                "size": len(data),
                "partition": part["partition"],
            }
        )
        for row in iter_jsonl_gzip(data):
            if row["market"] not in market_map:
                raise ValueError("day partition contains unexpected market")
            if row["schema"] == OBSERVATION_SCHEMA:
                validate_observation(row)
                observation_count += 1
                if row["availability"] == "observed_ask":
                    by_side[(row["market"], row["outcome"])] += 1
            elif row["schema"] == RESOLUTION_SCHEMA:
                validate_resolution(row)
                by_winner[row["market"]].add((row["winning_token"], row["winning_outcome"]))
            else:
                raise ValueError("unexpected staged row schema")
    missing_sides = sorted(
        f"{market}:{side}"
        for market in market_map
        for side in ("UP", "DOWN")
        if not by_side[(market, side)]
    )
    missing_resolution, contradictory, resolution_count = _resolution_evidence(
        market_map, by_winner
    )
    reasons = []
    if index_value.get("complete_expected_partition_set") is not True:
        reasons.append("incomplete_expected_source_partition_set")
    if index_value.get("target_membership_reconciled") is not True:
        reasons.append("unresolved_source_condition_membership")
    if not mappings:
        reasons.append("no_in_scope_markets_in_pinned_inventory")
    if errors:
        reasons.append("malformed_in_scope_source_rows")
    if missing_sides:
        reasons.append("missing_recorded_best_ask_side_evidence")
    if contradictory:
        reasons.append("contradictory_official_resolution")
    status = (
        "PENDING"
        if missing_resolution and not reasons
        else "EXCLUDED"
        if reasons or missing_resolution
        else "CERTIFIED"
    )
    if missing_resolution:
        reasons.append("official_resolution_not_yet_present_in_pinned_inventory")
    mapping_data = jsonl_gzip(mappings) if status == "CERTIFIED" else b""
    manifest = {
        "schema": DAY_SCHEMA,
        **profile_fields(),
        "status": status,
        "day": day,
        "claim": (
            "complete deterministic projection of every in-scope target market present "
            "in the pinned published V3 inventory generation"
        ),
        "limitations": [
            "no historical venue-listing completeness",
            "no continuity or missed-excursion exclusion",
            "no synthetic or time-only crossings",
            "not sender execution reconstruction",
        ],
        "inventory_generation": catalog_value["inventory_generation"],
        "inventory_last_hour": catalog_value["inventory_last_hour"],
        "inventory_tag": catalog_value["inventory_tag"],
        "inventory_sha256": catalog_value["inventory_sha256"],
        "inventory_release_id": catalog_value["inventory_release_id"],
        "catalog_generation": catalog_value["generation"],
        "catalog_tag": catalog_tag,
        "catalog_sha256": catalog_sha,
        "data_index_generation": index_value["generation"],
        "data_index_tag": index_tag,
        "data_index_sha256": index_sha,
        "transform": TRANSFORM,
        "transform_implementation_sha256": catalog_value["transform_implementation_sha256"],
        "mapping_schema": MAPPING_SCHEMA,
        "observation_schema": OBSERVATION_SCHEMA,
        "resolution_schema": RESOLUTION_SCHEMA,
        "market_count": len(mappings),
        "observation_count": observation_count,
        "resolution_count": resolution_count,
        "missing_sides": missing_sides,
        "missing_resolutions": missing_resolution,
        "contradictory_resolutions": contradictory,
        "source_errors": errors,
        "certification_reasons": reasons,
        "best_ask_side_gate": "at_least_one_non_null_recorded_ask_per_outcome_token",
        "source_assets": source_assets,
        "mapping_data_sha256": sha(mapping_data) if mapping_data else None,
        "mapping_data_size": len(mapping_data),
        "canonical_observation_shards": source_assets,
        "research_import_allowed": status == "CERTIFIED",
    }
    generation = sha(canonical(manifest))
    manifest["generation"] = generation
    payloads = {"manifest.json": canonical(manifest)}
    if mapping_data:
        payloads["mappings.jsonl.gz"] = mapping_data
    tag = "observed-day-v1-" + generation
    release = publish(
        tag,
        payloads,
        current_commit(),
        f"Observed inventory-scoped day {day}: {status}",
        "Immutable observed-profile day assessment. Read manifest limitations before use.",
    )
    print(
        canonical(
            {
                "day": day,
                "status": status,
                "tag": tag,
                "release_id": release["id"],
                "generation": generation,
                "markets": len(mappings),
                "observations": observation_count,
                "reasons": reasons,
            }
        ).decode()
    )
    return manifest


def _all_releases() -> Iterable[dict[str, Any]]:
    for page in range(1, 101):
        values = api(f"releases?per_page=100&page={page}")
        if not values:
            return
        yield from values
        if len(values) < 100:
            return
    raise ValueError("release pagination exceeded")


def window(catalog_tag: str, catalog_sha: str, index_tag: str, index_sha: str) -> dict[str, Any]:
    _, catalog_value = _load_json(catalog_tag, catalog_sha, "catalog.json")
    _, index_value = _load_json(index_tag, index_sha, "data-index.json")
    certified: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    latest_assessments: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for release in _all_releases():
        if not str(release.get("tag_name", "")).startswith("observed-day-v1-") or not release.get(
            "immutable"
        ):
            continue
        matches = [
            asset for asset in release["assets"] if asset["name"].endswith("--manifest.json")
        ]
        if len(matches) != 1:
            continue
        value = json.loads(read_asset(matches[0]))
        if (
            value.get("schema") != DAY_SCHEMA
            or any(value.get(name) != expected for name, expected in profile_fields().items())
            or value.get("status") not in ("CERTIFIED", "EXCLUDED", "PENDING")
            or value.get("generation")
            != sha(canonical({key: item for key, item in value.items() if key != "generation"}))
            or type(value.get("inventory_release_id")) is not int
        ):
            raise ValueError("immutable observed-day manifest is malformed")
        try:
            assessed_day = datetime.strptime(value["day"], "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise ValueError("immutable observed-day identity is malformed") from exc
        if assessed_day >= datetime.now(UTC).date():
            raise ValueError("immutable observed-day assessment is not a complete past day")
        rank = (
            value.get("inventory_release_id", -1),
            value.get("inventory_last_hour", ""),
            release["id"],
        )
        prior = latest_assessments.get(value["day"])
        if prior is None or rank > (
            prior[1].get("inventory_release_id", -1),
            prior[1].get("inventory_last_hour", ""),
            prior[0]["id"],
        ):
            latest_assessments[value["day"]] = (release, value)
        if value.get("status") == "CERTIFIED":
            prior = certified.get(value["day"])
            if prior is None or rank > (
                prior[1].get("inventory_release_id", -1),
                prior[1].get("inventory_last_hour", ""),
                prior[0]["id"],
            ):
                certified[value["day"]] = (release, value)
    selected = select_window(value for _, value in certified.values())
    if not selected:
        raise ValueError("no certified day exists; current research authority unchanged")
    refs = []
    for value in selected:
        release, _ = certified[value["day"]]
        assets = {asset["name"].split("--", 1)[1]: asset for asset in release["assets"]}
        refs.append(
            {
                "day": value["day"],
                "generation": value["generation"],
                "tag": release["tag_name"],
                "release_id": release["id"],
                "manifest_sha256": next(
                    asset["name"].split("--", 1)[0]
                    for asset in release["assets"]
                    if asset["name"].endswith("--manifest.json")
                ),
                "mapping_data_sha256": value["mapping_data_sha256"],
                "mapping_data_size": value["mapping_data_size"],
                "market_count": value["market_count"],
                "observation_count": value["observation_count"],
                "mapping_asset_id": assets["mappings.jsonl.gz"]["id"],
            }
        )
    newest_certified = refs[-1]["day"]
    rollover_blocked_by = sorted(
        day
        for day, (_, assessment) in latest_assessments.items()
        if day > newest_certified and assessment["status"] != "CERTIFIED"
    )
    value = {
        "schema": WINDOW_SCHEMA,
        **profile_fields(),
        "research_import_allowed": True,
        "claim": "rolling authority over certified pinned-V3-inventory-scoped observed days only",
        "continuity_warning": (
            "continuity between observations is NOT certified; first means first "
            "qualifying RECORDED observation"
        ),
        "future_incompatible_profile": "OWN_RECORDER_EXACT",
        "inventory_generation": catalog_value["inventory_generation"],
        "inventory_last_hour": catalog_value["inventory_last_hour"],
        "inventory_release_id": catalog_value["inventory_release_id"],
        "inventory_tag": catalog_value["inventory_tag"],
        "inventory_sha256": catalog_value["inventory_sha256"],
        "catalog_generation": catalog_value["generation"],
        "catalog_tag": catalog_tag,
        "catalog_sha256": catalog_sha,
        "data_index_generation": index_value["generation"],
        "data_index_tag": index_tag,
        "data_index_sha256": index_sha,
        "transform": TRANSFORM,
        "transform_implementation_sha256": catalog_value["transform_implementation_sha256"],
        "included_certified_days": [item["day"] for item in refs],
        "day_generations": refs,
        "excluded_or_pending": [
            {
                "day": day,
                "status": value["status"],
                "reasons": value["certification_reasons"],
            }
            for day, (_, value) in sorted(latest_assessments.items())
            if value["status"] != "CERTIFIED"
        ],
        "current_rollover_blocked_by_failed_newer_days": rollover_blocked_by,
        "selection_rule": "all certified days when fewer than 30, otherwise latest 30 by UTC day",
        "verification": (
            "python -m pflow.production_consumer --tag <window_tag> --sha256 <handoff_sha256>"
        ),
        "repository": "atalaydor/polymarket-5m-seven-asset-price-time-canonical-data",
        "implementation_commit": current_commit(),
    }
    generation = sha(canonical(value))
    value["generation"] = generation
    payload = canonical(value)
    tag = "observed-window-v1-" + generation
    release = publish(
        tag,
        {"consumer-handoff.json": payload},
        current_commit(),
        "Observed bootstrap rolling window",
        "Immutable rolling manifest; source-inventory-scoped observations, "
        "no continuity authority.",
    )
    from pflow.production_consumer import verify as verify_window

    verify_window(tag, sha(payload))
    _update_current(tag, sha(payload), value, release["id"])
    _output("window_tag", tag)
    _output("handoff_sha256", sha(payload))
    print(
        canonical(
            {
                "tag": tag,
                "release_id": release["id"],
                "handoff_sha256": sha(payload),
                "generation": generation,
                "days": value["included_certified_days"],
            }
        ).decode()
    )
    return value


def _update_current(
    tag: str, digest: str, window_value: dict[str, Any], window_release_id: int
) -> None:
    pointer = canonical(
        {
            "schema": "pendulumflow-observed-current-reference.v1",
            "profile": PROFILE,
            "profile_version": PROFILE_VERSION,
            "certification_scope": CERTIFICATION_SCOPE,
            "window_tag": tag,
            "handoff_sha256": digest,
            "window_generation": window_value["generation"],
            "window_release_id": window_release_id,
            "included_certified_days": window_value["included_certified_days"],
            "inventory_last_hour": window_value["inventory_last_hour"],
            "inventory_release_id": window_value["inventory_release_id"],
            "updated_by_run_id": os.environ.get("GITHUB_RUN_ID"),
        }
    )
    branch = "observed-current"
    ref = api(f"git/ref/heads/{branch}")
    if ref:
        commit = api("git/commits/" + ref["object"]["sha"])
        try:
            _, current = _load_current_blob(commit["tree"]["sha"])
            old_days = current.get("included_certified_days", [])
            new_days = window_value["included_certified_days"]
            if window_value["current_rollover_blocked_by_failed_newer_days"]:
                print(
                    canonical(
                        {
                            "current_reference_updated": False,
                            "reason": "failed_newer_day_preserves_current",
                        }
                    ).decode()
                )
                return
            if not isinstance(old_days, list) or not all(isinstance(day, str) for day in old_days):
                raise ValueError("current day inventory invalid")
            regresses = not _rolling_day_set_advances(old_days, new_days)
            regresses = (
                regresses
                or current.get("inventory_release_id", -1) > window_value["inventory_release_id"]
            )
            unchanged_or_older = old_days == new_days and (
                current.get("inventory_release_id", -1),
                current.get("window_release_id", -1),
            ) >= (window_value["inventory_release_id"], window_release_id)
            if regresses or unchanged_or_older:
                print(
                    canonical(
                        {"current_reference_updated": False, "reason": "monotone_no_regression"}
                    ).decode()
                )
                return
        except ValueError as exc:
            raise ValueError("existing current reference is malformed") from exc
        parent = ref["object"]["sha"]
        base_tree = commit["tree"]["sha"]
    else:
        main = api("git/ref/heads/main")
        parent = main["object"]["sha"]
        base_tree = api("git/commits/" + parent)["tree"]["sha"]
    blob = api("git/blobs", "POST", {"content": pointer.decode(), "encoding": "utf-8"})
    tree = api(
        "git/trees",
        "POST",
        {
            "base_tree": base_tree,
            "tree": [
                {
                    "path": "authority/current-window.json",
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob["sha"],
                }
            ],
        },
    )
    commit = api(
        "git/commits",
        "POST",
        {
            "message": "Update observed current-window reference",
            "tree": tree["sha"],
            "parents": [parent],
        },
    )
    if ref:
        api(f"git/refs/heads/{branch}", "PATCH", {"sha": commit["sha"], "force": False})
    else:
        api("git/refs", "POST", {"ref": "refs/heads/" + branch, "sha": commit["sha"]})
    print(
        canonical(
            {"current_reference_updated": True, "branch": branch, "commit": commit["sha"]}
        ).decode()
    )


def _rolling_day_set_advances(old_days: list[str], new_days: list[str]) -> bool:
    if (
        len(old_days) > 30
        or not new_days
        or len(new_days) > 30
        or old_days != sorted(set(old_days))
        or new_days != sorted(set(new_days))
    ):
        return False
    return new_days == sorted(set(old_days) | set(new_days))[-30:]


def _load_current_blob(tree_sha: str) -> tuple[str, dict[str, Any]]:
    tree = api("git/trees/" + tree_sha + "?recursive=1")
    matches = [item for item in tree["tree"] if item["path"] == "authority/current-window.json"]
    if len(matches) != 1:
        raise ValueError("current pointer blob absent")
    blob = api("git/blobs/" + matches[0]["sha"])
    import base64

    data = base64.b64decode(blob["content"])
    return sha(data), json.loads(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    mapping_parser = sub.add_parser("mapping")
    data_parser = sub.add_parser("data")
    for item in (mapping_parser, data_parser):
        item.add_argument("--inventory-tag", required=True)
        item.add_argument("--inventory-sha", required=True)
        item.add_argument("--chunk", required=True)
        item.add_argument("--partition", required=True)
    data_parser.add_argument("--catalog-tag", required=True)
    data_parser.add_argument("--catalog-sha", required=True)
    mapping_batch_parser = sub.add_parser("mapping-batch")
    mapping_batch_parser.add_argument("--inventory-tag", required=True)
    mapping_batch_parser.add_argument("--inventory-sha", required=True)
    mapping_batch_parser.add_argument("--work", required=True)
    data_batch_parser = sub.add_parser("data-batch")
    data_batch_parser.add_argument("--inventory-tag", required=True)
    data_batch_parser.add_argument("--inventory-sha", required=True)
    data_batch_parser.add_argument("--catalog-tag", required=True)
    data_batch_parser.add_argument("--catalog-sha", required=True)
    data_batch_parser.add_argument("--work", required=True)
    catalog_parser = sub.add_parser("catalog")
    catalog_parser.add_argument("--inventory-tag", required=True)
    catalog_parser.add_argument("--inventory-sha", required=True)
    catalog_parser.add_argument("--max-days", type=int, default=0)
    certify_batch_parser = sub.add_parser("certify-batch")
    certify_batch_parser.add_argument("--catalog-tag", required=True)
    certify_batch_parser.add_argument("--catalog-sha", required=True)
    certify_batch_parser.add_argument("--index-tag", required=True)
    certify_batch_parser.add_argument("--index-sha", required=True)
    certify_batch_parser.add_argument("--days", required=True)
    for name in ("index", "certify", "window"):
        item = sub.add_parser(name)
        item.add_argument("--catalog-tag", required=True)
        item.add_argument("--catalog-sha", required=True)
        item.add_argument("--index-tag", required=name == "certify" or name == "window")
        item.add_argument("--index-sha", required=name == "certify" or name == "window")
        if name == "index":
            item.add_argument("--inventory-tag", required=True)
            item.add_argument("--inventory-sha", required=True)
        if name == "certify":
            item.add_argument("--day", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        plan()
    elif args.command == "mapping":
        mapping_shard(args.inventory_tag, args.inventory_sha, args.chunk, args.partition)
    elif args.command == "mapping-batch":
        for work in json.loads(args.work):
            mapping_shard(args.inventory_tag, args.inventory_sha, work["hours"], work["id"])
    elif args.command == "catalog":
        catalog(args.inventory_tag, args.inventory_sha, args.max_days)
    elif args.command == "data":
        data_shard(
            args.inventory_tag,
            args.inventory_sha,
            args.catalog_tag,
            args.catalog_sha,
            args.chunk,
            args.partition,
        )
    elif args.command == "data-batch":
        for work in json.loads(args.work):
            data_shard(
                args.inventory_tag,
                args.inventory_sha,
                args.catalog_tag,
                args.catalog_sha,
                work["hours"],
                work["id"],
            )
    elif args.command == "index":
        data_index(args.inventory_tag, args.inventory_sha, args.catalog_tag, args.catalog_sha)
    elif args.command == "certify":
        certify_day(args.catalog_tag, args.catalog_sha, args.index_tag, args.index_sha, args.day)
    elif args.command == "certify-batch":
        for day in json.loads(args.days):
            certify_day(args.catalog_tag, args.catalog_sha, args.index_tag, args.index_sha, day)
    elif args.command == "window":
        window(args.catalog_tag, args.catalog_sha, args.index_tag, args.index_sha)


if __name__ == "__main__":
    main()
