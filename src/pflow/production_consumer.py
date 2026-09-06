"""Independent exact-generation verifier for observed bootstrap authority."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from functools import cache
from typing import Any

from pflow.inventory import validate_inventory
from pflow.observed_v1 import (
    CERTIFICATION_SCOPE,
    CERTIFICATION_SCOPE_VERSION,
    MAPPING_SCHEMA,
    OBSERVATION_SCHEMA,
    PROFILE,
    PROFILE_VERSION,
    RESOLUTION_SCHEMA,
    TRANSFORM,
    WINDOW_SCHEMA,
    iter_jsonl_gzip,
    validate_mapping,
    validate_observation,
    validate_resolution,
)
from pflow.release import api, read_asset
from pflow.source import canonical, sha

CATALOG_SCHEMA = "pendulumflow-v3-observed-inventory-catalog.v1"
DATA_INDEX_SCHEMA = "pendulumflow-v3-observed-data-index.v1"
DATA_PARTITION_SCHEMA = "pendulumflow-v3-observed-data-partition.v1"
DAY_SCHEMA = "pendulumflow-v3-observed-certified-day.v1"
DATA_CHUNK = 4
MAPPING_CHUNK = 8


def _asset(release: dict[str, Any], suffix: str) -> tuple[dict[str, Any], bytes]:
    matches = [item for item in release["assets"] if item["name"].endswith("--" + suffix)]
    if len(matches) != 1:
        raise ValueError("immutable generation asset inventory mismatch")
    data = read_asset(matches[0])
    return matches[0], data


@cache
def _release(tag: str) -> dict[str, Any]:
    value = api(f"releases/tags/{tag}")
    if value is None or value.get("draft") or not value.get("immutable"):
        raise ValueError("referenced release is not immutable")
    return dict(value)


def _json_release(tag: str, digest: str, suffix: str) -> tuple[dict[str, Any], dict[str, Any]]:
    release = _release(tag)
    _, data = _asset(release, suffix)
    if sha(data) != digest:
        raise ValueError("referenced JSON digest mismatch")
    value: dict[str, Any] = json.loads(data)
    return release, value


def _generation(value: dict[str, Any]) -> None:
    generation = value.get("generation")
    if not isinstance(generation, str) or re.fullmatch(r"[0-9a-f]{64}", generation) is None:
        raise ValueError("generation identity invalid")
    core = {key: item for key, item in value.items() if key != "generation"}
    if sha(canonical(core)) != generation:
        raise ValueError("generation is not content-derived")


def _profile(value: dict[str, Any]) -> None:
    if (
        value.get("profile") != PROFILE
        or type(value.get("profile_version")) is not int
        or value["profile_version"] != PROFILE_VERSION
        or value.get("certification_scope") != CERTIFICATION_SCOPE
        or type(value.get("certification_scope_version")) is not int
        or value["certification_scope_version"] != CERTIFICATION_SCOPE_VERSION
        or value.get("continuity_between_observations_certified") is not False
        or value.get("historical_polymarket_listing_completeness_claimed") is not False
    ):
        raise ValueError("unsupported or overclaimed profile/scope")


def _digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _source_parts(
    inventory: dict[str, Any], transform_implementation_sha256: str
) -> list[dict[str, Any]]:
    hours = [item["hour"] for item in inventory["hours"]]
    manifests = {item["hour"]: item for item in inventory["hours"]}
    result = []
    buckets: dict[int, list[str]] = defaultdict(list)
    for hour in hours:
        instant = datetime.strptime(hour, "%Y-%m-%d/%H").replace(tzinfo=UTC)
        buckets[int(instant.timestamp()) // 3600 // DATA_CHUNK].append(hour)
    for bucket in sorted(buckets):
        subset = buckets[bucket]
        identity = sha(
            canonical(
                {
                    "kind": "data",
                    "transform": TRANSFORM,
                    "transform_implementation_sha256": transform_implementation_sha256,
                    "sources": {
                        hour: {
                            "manifest_sha256": manifests[hour]["manifest_sha256"],
                            "product": manifests[hour]["manifest"]["products"]["best_bid_ask"],
                        }
                        for hour in subset
                    },
                    "resolution_sources": {
                        hour: {
                            "manifest_sha256": manifests[hour]["manifest_sha256"],
                            "product": manifests[hour]["manifest"]["products"]["market_resolved"],
                        }
                        for hour in subset
                    },
                }
            )
        )
        result.append({"id": identity, "hours": subset})
    return result


def _mapping_parts(
    inventory: dict[str, Any], transform_implementation_sha256: str
) -> list[dict[str, Any]]:
    hours = [item["hour"] for item in inventory["hours"]]
    manifests = {item["hour"]: item for item in inventory["hours"]}
    result = []
    buckets: dict[int, list[str]] = defaultdict(list)
    for hour in hours:
        instant = datetime.strptime(hour, "%Y-%m-%d/%H").replace(tzinfo=UTC)
        buckets[int(instant.timestamp()) // 3600 // MAPPING_CHUNK].append(hour)
    for bucket in sorted(buckets):
        subset = buckets[bucket]
        identity = sha(
            canonical(
                {
                    "kind": "mapping",
                    "transform": TRANSFORM,
                    "transform_implementation_sha256": transform_implementation_sha256,
                    "sources": {
                        hour: {
                            "manifest_sha256": manifests[hour]["manifest_sha256"],
                            "product": manifests[hour]["manifest"]["products"]["new_market"],
                        }
                        for hour in subset
                    },
                    "resolution_sources": None,
                }
            )
        )
        result.append({"id": identity, "hours": subset})
    return result


def _catalog_dependency(catalog: dict[str, Any], encountered: set[str]) -> str:
    fields = ("market", "asset", "start_us", "end_us", "up_token", "down_token")
    rows = [
        {name: row[name] for name in fields}
        for row in catalog["mappings"]
        if row["market"] in encountered
    ]
    return sha(canonical(rows))


def _verify_inventory_catalog(
    catalog_tag: str, catalog_sha: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    _, catalog = _json_release(catalog_tag, catalog_sha, "catalog.json")
    _profile(catalog)
    _generation(catalog)
    catalog_fields = {
        "schema",
        "profile",
        "profile_version",
        "certification_scope",
        "certification_scope_version",
        "continuity_between_observations_certified",
        "historical_polymarket_listing_completeness_claimed",
        "transform",
        "implementation_commit",
        "transform_implementation_sha256",
        "inventory_generation",
        "inventory_first_hour",
        "inventory_last_hour",
        "inventory_tag",
        "inventory_sha256",
        "inventory_release_id",
        "claim",
        "claim_limit",
        "mapping_partition_sources",
        "source_condition_classifications",
        "mappings",
        "duplicate_same_identity_rows_retained_in_partition_evidence",
        "market_counts_by_start_day",
        "generation",
    }
    if (
        set(catalog) != catalog_fields
        or catalog.get("schema") != CATALOG_SCHEMA
        or catalog.get("generation") != catalog_tag.removeprefix("observed-catalog-v1-")
        or catalog.get("transform") != TRANSFORM
        or not _digest(catalog.get("transform_implementation_sha256"))
        or not isinstance(catalog.get("mappings"), list)
        or type(catalog.get("inventory_release_id")) is not int
        or catalog["inventory_release_id"] <= 0
    ):
        raise ValueError("catalog contract invalid")
    inventory_release, inventory = _json_release(
        catalog["inventory_tag"], catalog["inventory_sha256"], "inventory.json"
    )
    validate_inventory(inventory)
    if (
        inventory["generation"] != catalog["inventory_generation"]
        or catalog["inventory_tag"] != "v3-inventory-v1-" + inventory["generation"]
        or inventory_release["id"] != catalog["inventory_release_id"]
        or catalog["inventory_first_hour"] != inventory["hours"][0]["hour"]
        or catalog["inventory_last_hour"] != inventory["hours"][-1]["hour"]
    ):
        raise ValueError("catalog/inventory binding mismatch")
    seen: set[str] = set()
    for row in catalog["mappings"]:
        validate_mapping(row)
        if row["market"] in seen:
            raise ValueError("catalog contains duplicate market")
        seen.add(row["market"])
    all_rows: list[dict[str, Any]] = []
    all_condition_dispositions: dict[str, set[str]] = defaultdict(set)
    sources = catalog.get("mapping_partition_sources")
    planned = _mapping_parts(inventory, catalog["transform_implementation_sha256"])
    if not isinstance(sources, list) or len(sources) != len(planned):
        raise ValueError("catalog mapping partition closure invalid")
    for expected, source in zip(planned, sources, strict=True):
        tag = "observed-mapping-v1-" + expected["id"]
        release = _release(tag)
        if release["id"] != source.get("release_id") or source.get("partition") != expected["id"]:
            raise ValueError("catalog mapping source release invalid")
        _, report_data = _asset(release, "report.json")
        _, rows_data = _asset(release, "mappings.jsonl.gz")
        _, condition_data = _asset(release, "condition-classifications.jsonl.gz")
        if (
            sha(report_data) != source.get("report_sha256")
            or sha(rows_data) != source.get("rows_sha256")
            or sha(condition_data) != source.get("condition_rows_sha256")
        ):
            raise ValueError("catalog mapping source digest invalid")
        report = json.loads(report_data)
        mapping_classifications = report.get("classification_counts")
        if (
            report.get("schema") != "pendulumflow-v3-observed-mapping-partition.v1"
            or report.get("partition_identity") != expected["id"]
            or report.get("hours") != expected["hours"]
            or report.get("target_like_errors")
            or mapping_classifications.get("ambiguous_target_like", 0)
            or report.get("transform") != TRANSFORM
            or report.get("transform_implementation_sha256")
            != catalog["transform_implementation_sha256"]
            or not isinstance(mapping_classifications, dict)
            or any(
                key not in {"in_scope_target", "ambiguous_target_like", "out_of_scope"}
                or type(count) is not int
                or count < 0
                for key, count in mapping_classifications.items()
            )
        ):
            raise ValueError("catalog mapping source report invalid")
        proofs = report.get("source_integrity")
        if not isinstance(proofs, dict) or set(proofs) != set(expected["hours"]):
            raise ValueError("catalog mapping proof closure invalid")
        item_by_hour = {item["hour"]: item for item in inventory["hours"]}
        decoded = 0
        for hour in expected["hours"]:
            product = proofs[hour].get("products", {}).get("new_market")
            source_product = item_by_hour[hour]["manifest"]["products"]["new_market"]
            if not isinstance(product, dict) or any(
                product.get(name) != source_product[name] for name in source_product
            ):
                raise ValueError("catalog mapping product proof invalid")
            if (
                product.get("range_sha256_verified") is not True
                or product.get("footer_binding_checked") is not True
            ):
                raise ValueError("catalog mapping source integrity unverified")
            decoded += source_product["row_count"]
        if (
            report.get("decoded_new_market_rows") != decoded
            or sum(report.get("classification_counts", {}).values()) != decoded
        ):
            raise ValueError("catalog mapping classification closure invalid")
        rows = list(iter_jsonl_gzip(rows_data))
        if len(rows) != report.get("target_mapping_rows") or mapping_classifications.get(
            "in_scope_target", 0
        ) != len(rows):
            raise ValueError("catalog mapping projected-row count invalid")
        for row in rows:
            validate_mapping(row)
            if row["source_hour"] not in expected["hours"]:
                raise ValueError("catalog mapping row outside source partition")
            source_item = item_by_hour[row["source_hour"]]
            source_product = source_item["manifest"]["products"]["new_market"]
            if (
                row["source_manifest_sha256"] != source_item["manifest_sha256"]
                or row["source_product_sha256"] != source_product["sha256"]
                or row["source_product_row_ordinal"] >= source_product["row_count"]
            ):
                raise ValueError("catalog mapping row source locator/proof mismatch")
        all_rows.extend(rows)
        condition_rows = list(iter_jsonl_gzip(condition_data))
        if len(condition_rows) != report.get("condition_classification_rows"):
            raise ValueError("catalog condition classification count invalid")
        for row in condition_rows:
            if (
                set(row)
                != {
                    "market",
                    "disposition",
                    "source_hour",
                    "source_product_row_ordinal",
                }
                or not _digest(row.get("market"))
                or row.get("disposition")
                not in {"in_scope_target", "out_of_scope", "ambiguous_target_like"}
                or row.get("source_hour") not in expected["hours"]
                or type(row.get("source_product_row_ordinal")) is not int
                or not 0
                <= row["source_product_row_ordinal"]
                < item_by_hour[row["source_hour"]]["manifest"]["products"]["new_market"][
                    "row_count"
                ]
            ):
                raise ValueError("catalog condition classification row invalid")
            all_condition_dispositions[row["market"]].add(row["disposition"])
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        grouped[row["market"]].append(row)
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
    selected = []
    for _market, rows in grouped.items():
        if len({tuple(row[name] for name in core) for row in rows}) != 1:
            raise ValueError("catalog mapping conflict was hidden")
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
    selected.sort(key=lambda row: (row["start_us"], row["asset"], row["market"]))
    if selected != catalog["mappings"]:
        raise ValueError("catalog does not exhaust mapped source inventory")
    if any(len(dispositions) != 1 for dispositions in all_condition_dispositions.values()):
        raise ValueError("catalog condition disposition conflict was hidden")
    if any(
        dispositions == {"ambiguous_target_like"}
        for dispositions in all_condition_dispositions.values()
    ):
        raise ValueError("catalog contains ambiguous target-like condition")
    if {
        market
        for market, dispositions in all_condition_dispositions.items()
        if dispositions == {"in_scope_target"}
    } != set(grouped):
        raise ValueError("catalog target mapping/disposition closure invalid")
    expected_condition_classifications = [
        {"market": market, "disposition": next(iter(dispositions))}
        for market, dispositions in sorted(all_condition_dispositions.items())
    ]
    if expected_condition_classifications != catalog["source_condition_classifications"]:
        raise ValueError("catalog does not exhaust source condition classifications")
    expected_day_counts = Counter(
        datetime.fromtimestamp(row["start_us"] / 1_000_000, UTC).date().isoformat()
        for row in selected
    )
    if dict(sorted(expected_day_counts.items())) != catalog.get("market_counts_by_start_day"):
        raise ValueError("catalog day-count closure invalid")
    return inventory, catalog


def _verify_source_proofs(
    report: dict[str, Any], inventory: dict[str, Any], hours: list[str]
) -> None:
    proofs = report.get("source_integrity")
    items = {item["hour"]: item for item in inventory["hours"]}
    if not isinstance(proofs, dict) or set(proofs) != set(hours):
        raise ValueError("data source-hour proof closure invalid")
    for hour in hours:
        products = proofs[hour].get("products")
        if not isinstance(products, dict) or set(products) != {"best_bid_ask", "market_resolved"}:
            raise ValueError("data source-product proof closure invalid")
        for product in products:
            expected = items[hour]["manifest"]["products"][product]
            if any(products[product].get(name) != expected[name] for name in expected):
                raise ValueError("data source-product binding mismatch")
            if (
                products[product].get("range_sha256_verified") is not True
                or products[product].get("footer_binding_checked") is not True
            ):
                raise ValueError("data source-product integrity unverified")


def _verify_index(
    index_tag: str,
    index_sha: str,
    catalog_tag: str,
    catalog_sha: str,
    inventory: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    _, index = _json_release(index_tag, index_sha, "data-index.json")
    _profile(index)
    _generation(index)
    index_fields = {
        "schema",
        "profile",
        "profile_version",
        "certification_scope",
        "certification_scope_version",
        "continuity_between_observations_certified",
        "historical_polymarket_listing_completeness_claimed",
        "transform",
        "inventory_generation",
        "transform_implementation_sha256",
        "inventory_tag",
        "inventory_sha256",
        "catalog_generation",
        "catalog_tag",
        "catalog_sha256",
        "complete_expected_partition_set",
        "target_membership_reconciled",
        "unresolved_condition_references",
        "unresolved_conditionless_rows",
        "partitions",
        "measurements",
        "generation",
    }
    if (
        set(index) != index_fields
        or index.get("schema") != DATA_INDEX_SCHEMA
        or index.get("generation") != index_tag.removeprefix("observed-data-index-v1-")
        or index.get("transform") != TRANSFORM
        or index.get("transform_implementation_sha256")
        != catalog["transform_implementation_sha256"]
        or index.get("complete_expected_partition_set") is not True
        or type(index.get("target_membership_reconciled")) is not bool
        or index.get("inventory_generation") != inventory["generation"]
        or index.get("inventory_tag") != catalog["inventory_tag"]
        or index.get("inventory_sha256") != catalog["inventory_sha256"]
        or index.get("catalog_generation") != catalog["generation"]
        or index.get("catalog_tag") != catalog_tag
        or index.get("catalog_sha256") != catalog_sha
    ):
        raise ValueError("data index contract/binding invalid")
    planned = _source_parts(inventory, catalog["transform_implementation_sha256"])
    entries = index.get("partitions")
    if not isinstance(entries, list) or len(entries) != len(planned):
        raise ValueError("data index partition cardinality invalid")
    classified_conditions = {row["market"] for row in catalog["source_condition_classifications"]}
    unresolved_all: set[str] = set()
    unresolved_conditionless = Counter[str]()
    for expected, entry in zip(planned, entries, strict=True):
        source_id = expected["id"]
        condition_tag = "observed-conditions-v1-" + source_id
        condition_release = _release(condition_tag)
        _, conditions_data = _asset(condition_release, "conditions.jsonl.gz")
        _, condition_report_data = _asset(condition_release, "report.json")
        condition_report = json.loads(condition_report_data)
        condition_rows = list(iter_jsonl_gzip(conditions_data))
        conditions = {
            str(row["market"])
            for row in condition_rows
            if set(row) == {"market"} and isinstance(row["market"], str)
        }
        if len(conditions) != len(condition_rows) or any(
            not _digest(market) for market in conditions
        ):
            raise ValueError("encountered condition index invalid")
        unresolved = sorted(conditions - classified_conditions)
        unresolved_all.update(unresolved)
        if entry.get("unresolved_condition_references") != unresolved:
            raise ValueError("data index unresolved condition ledger invalid")
        encountered_counts = condition_report.get("encountered_rows_by_product")
        missing_counts = condition_report.get("missing_condition_rows_by_product")
        if (
            not isinstance(encountered_counts, dict)
            or not isinstance(missing_counts, dict)
            or set(encountered_counts) != {"best_bid_ask", "market_resolved"}
            or set(missing_counts) != {"best_bid_ask", "market_resolved"}
            or any(
                type(count) is not int or count < 0
                for count in (*encountered_counts.values(), *missing_counts.values())
            )
        ):
            raise ValueError("encountered condition row accounting invalid")
        expected_conditionless = {
            product: missing_counts[product] for product in ("best_bid_ask", "market_resolved")
        }
        if entry.get("unresolved_conditionless_rows") != expected_conditionless:
            raise ValueError("data index conditionless row ledger invalid")
        unresolved_conditionless.update(expected_conditionless)
        if (
            condition_report.get("schema") != "pendulumflow-v3-encountered-condition-partition.v1"
            or condition_report.get("partition_identity") != source_id
            or condition_report.get("hours") != expected["hours"]
            or condition_report.get("condition_count") != len(conditions)
            or condition_report.get("payload_assets")
            != {
                "conditions.jsonl.gz": {
                    "sha256": sha(conditions_data),
                    "size": len(conditions_data),
                }
            }
        ):
            raise ValueError("encountered condition report invalid")
        dependency = _catalog_dependency(catalog, conditions)
        binding = sha(
            canonical(
                {
                    "partition": source_id,
                    "catalog_dependency": dependency,
                    "transform": TRANSFORM,
                    "transform_implementation_sha256": catalog["transform_implementation_sha256"],
                }
            )
        )
        if entry.get("source_partition") != source_id or entry.get("partition") != binding:
            raise ValueError("data index partition ordering/binding invalid")
        release = _release(entry["tag"])
        if release["id"] != entry["release_id"] or entry["tag"] != "observed-data-v1-" + binding:
            raise ValueError("data partition release binding invalid")
        _, report_data = _asset(release, "report.json")
        if sha(report_data) != entry["report_sha256"]:
            raise ValueError("data partition report digest invalid")
        report = json.loads(report_data)
        if (
            report.get("schema") != DATA_PARTITION_SCHEMA
            or report.get("partition_identity") != binding
            or report.get("source_partition_identity") != source_id
            or report.get("catalog_dependency") != dependency
            or report.get("hours") != expected["hours"]
            or report.get("transform") != TRANSFORM
            or report.get("transform_implementation_sha256")
            != catalog["transform_implementation_sha256"]
        ):
            raise ValueError("data partition report invalid")
        _verify_source_proofs(report, inventory, expected["hours"])
        expected_decoded = {
            product: sum(
                next(item for item in inventory["hours"] if item["hour"] == hour)["manifest"][
                    "products"
                ][product]["row_count"]
                for hour in expected["hours"]
            )
            for product in ("best_bid_ask", "market_resolved")
        }
        if report.get("decoded_rows") != expected_decoded:
            raise ValueError("data partition decoded-row closure invalid")
        classification = report.get("classification_counts")
        if not isinstance(classification, dict):
            raise ValueError("data partition classification ledger absent")
        allowed_classifications = {
            product + ":" + disposition
            for product in ("best_bid_ask", "market_resolved")
            for disposition in (
                "missing_condition",
                "classified_out_of_scope",
                "unresolved_condition",
                "ambiguous_condition",
                "outside_market_interval",
                "retained",
                "target_error",
            )
        }
        if any(
            key not in allowed_classifications or type(count) is not int or count < 0
            for key, count in classification.items()
        ):
            raise ValueError("data partition classification entry invalid")
        for product, total in expected_decoded.items():
            classified = sum(
                count
                for key, count in classification.items()
                if isinstance(key, str)
                and key.startswith(product + ":")
                and type(count) is int
                and count >= 0
            )
            if classified != total:
                raise ValueError("data partition classification accounting mismatch")
            missing = classification.get(product + ":missing_condition", 0)
            if (
                condition_report.get("encountered_rows_by_product", {}).get(product, 0)
                != (total - missing)
                or condition_report.get("missing_condition_rows_by_product", {}).get(product, 0)
                != missing
            ):
                raise ValueError("condition/data row accounting mismatch")
        actual_assets = {
            asset["name"]: {
                "id": asset["id"],
                "name": asset["name"],
                "size": asset["size"],
                "digest": asset["digest"],
                "browser_download_url": asset["browser_download_url"],
            }
            for asset in release["assets"]
        }
        if actual_assets != {asset["name"]: asset for asset in entry["assets"]}:
            raise ValueError("data index release-asset inventory invalid")
        payload_actual = {
            asset["name"].split("--", 1)[1]: {
                "sha256": asset["name"].split("--", 1)[0],
                "size": asset["size"],
            }
            for asset in release["assets"]
            if not asset["name"].endswith("--report.json")
        }
        if payload_actual != report.get("payload_assets"):
            raise ValueError("data partition payload closure invalid")
        if entry.get("errors") != report.get("target_errors"):
            raise ValueError("data partition error ledger mismatch")
        retained = Counter[str]()
        inventory_hours = {item["hour"]: item for item in inventory["hours"]}
        mappings = {row["market"]: row for row in catalog["mappings"]}
        for asset in release["assets"]:
            suffix = asset["name"].split("--", 1)[1]
            if suffix == "report.json":
                continue
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\.jsonl\.gz", suffix) is None:
                raise ValueError("unexpected data partition asset name")
            day = suffix.removesuffix(".jsonl.gz")
            data = read_asset(asset)
            for row in iter_jsonl_gzip(data):
                mapped = mappings.get(row.get("market"))
                if mapped is None or row["market"] not in conditions:
                    raise ValueError("partition row not bound to catalog/condition index")
                if row.get("schema") == OBSERVATION_SCHEMA:
                    validate_observation(row)
                    product = "best_bid_ask"
                    token = mapped["up_token"] if row["outcome"] == "UP" else mapped["down_token"]
                    if row["token"] != token or row["asset"] != mapped["asset"]:
                        raise ValueError("partition observation/mapping relation invalid")
                elif row.get("schema") == RESOLUTION_SCHEMA:
                    validate_resolution(row)
                    product = "market_resolved"
                    token = (
                        mapped["up_token"]
                        if row["winning_outcome"] == "UP"
                        else mapped["down_token"]
                    )
                    if row["winning_token"] != token or row["asset"] != mapped["asset"]:
                        raise ValueError("partition resolution/mapping relation invalid")
                else:
                    raise ValueError("forbidden partition row schema")
                expected_day = datetime.fromtimestamp(mapped["start_us"] / 1_000_000, UTC).date()
                if expected_day.isoformat() != day:
                    raise ValueError("partition row market-start day mismatch")
                source_hour = row["source_hour"]
                if source_hour not in expected["hours"]:
                    raise ValueError("partition row source hour outside source partition")
                source_item = inventory_hours[source_hour]
                source_product = source_item["manifest"]["products"][product]
                if (
                    row["source_manifest_sha256"] != source_item["manifest_sha256"]
                    or row["source_product_sha256"] != source_product["sha256"]
                    or row["source_product_row_ordinal"] >= source_product["row_count"]
                ):
                    raise ValueError("partition row source locator/proof mismatch")
                retained[day] += 1
        if dict(retained) != report.get("retained_rows_by_market_start_day"):
            raise ValueError("data partition retained-row accounting mismatch")
    if (
        index["unresolved_condition_references"] != sorted(unresolved_all)
        or index["unresolved_conditionless_rows"] != dict(unresolved_conditionless)
        or index["target_membership_reconciled"]
        != (not unresolved_all and not sum(unresolved_conditionless.values()))
        or not index["target_membership_reconciled"]
    ):
        raise ValueError("unresolved source condition membership blocks authority")
    return index


def _validate_day(
    value: dict[str, Any], reference: dict[str, Any], release: dict[str, Any]
) -> None:
    _profile(value)
    _generation(value)
    required = {
        "schema",
        "profile",
        "profile_version",
        "certification_scope",
        "certification_scope_version",
        "continuity_between_observations_certified",
        "historical_polymarket_listing_completeness_claimed",
        "status",
        "day",
        "claim",
        "limitations",
        "inventory_generation",
        "inventory_last_hour",
        "inventory_tag",
        "inventory_sha256",
        "inventory_release_id",
        "catalog_generation",
        "catalog_tag",
        "catalog_sha256",
        "data_index_generation",
        "data_index_tag",
        "data_index_sha256",
        "transform",
        "transform_implementation_sha256",
        "mapping_schema",
        "observation_schema",
        "resolution_schema",
        "market_count",
        "observation_count",
        "resolution_count",
        "missing_sides",
        "missing_resolutions",
        "contradictory_resolutions",
        "source_errors",
        "certification_reasons",
        "best_ask_side_gate",
        "source_assets",
        "mapping_data_sha256",
        "mapping_data_size",
        "canonical_observation_shards",
        "research_import_allowed",
        "generation",
    }
    if set(value) != required:
        raise ValueError("day manifest field allowlist invalid")
    try:
        parsed_day = datetime.strptime(value["day"], "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError("day identity invalid") from exc
    if (
        value["schema"] != DAY_SCHEMA
        or value["status"] != "CERTIFIED"
        or value["research_import_allowed"] is not True
        or parsed_day >= datetime.now(UTC).date()
        or value["generation"] != reference.get("generation")
        or release["tag_name"] != reference.get("tag")
        or release["id"] != reference.get("release_id")
        or value["transform"] != TRANSFORM
        or not _digest(value["transform_implementation_sha256"])
        or value["mapping_schema"] != MAPPING_SCHEMA
        or value["observation_schema"] != OBSERVATION_SCHEMA
        or value["resolution_schema"] != RESOLUTION_SCHEMA
        or value["certification_reasons"]
        or value["missing_sides"]
        or value["missing_resolutions"]
        or value["contradictory_resolutions"]
        or value["source_errors"]
        or value["day"] != reference.get("day")
        or value["source_assets"] != value["canonical_observation_shards"]
        or not value["source_assets"]
        or value["limitations"]
        != [
            "no historical venue-listing completeness",
            "no continuity or missed-excursion exclusion",
            "no synthetic or time-only crossings",
            "not sender execution reconstruction",
        ]
        or any(
            type(value.get(name)) is not int or value[name] <= 0
            for name in (
                "inventory_release_id",
                "market_count",
                "observation_count",
                "resolution_count",
                "mapping_data_size",
            )
        )
        or any(
            not _digest(value.get(name))
            for name in (
                "inventory_generation",
                "inventory_sha256",
                "catalog_generation",
                "catalog_sha256",
                "data_index_generation",
                "data_index_sha256",
                "mapping_data_sha256",
            )
        )
    ):
        raise ValueError("referenced day is not compatible certified authority")


def verify(tag: str, digest: str) -> dict[str, Any]:
    if not re.fullmatch(r"observed-window-v1-[0-9a-f]{64}", tag) or not _digest(digest):
        raise ValueError("exact observed window tag and SHA-256 required")
    release, value = _json_release(tag, digest, "consumer-handoff.json")
    _profile(value)
    _generation(value)
    window_fields = {
        "schema",
        "profile",
        "profile_version",
        "certification_scope",
        "certification_scope_version",
        "continuity_between_observations_certified",
        "historical_polymarket_listing_completeness_claimed",
        "research_import_allowed",
        "claim",
        "continuity_warning",
        "future_incompatible_profile",
        "inventory_generation",
        "inventory_last_hour",
        "inventory_release_id",
        "inventory_tag",
        "inventory_sha256",
        "catalog_generation",
        "catalog_tag",
        "catalog_sha256",
        "data_index_generation",
        "data_index_tag",
        "data_index_sha256",
        "transform",
        "transform_implementation_sha256",
        "included_certified_days",
        "day_generations",
        "excluded_or_pending",
        "current_rollover_blocked_by_failed_newer_days",
        "selection_rule",
        "verification",
        "repository",
        "implementation_commit",
        "generation",
    }
    if (
        set(value) != window_fields
        or value.get("schema") != WINDOW_SCHEMA
        or value.get("generation") != tag.removeprefix("observed-window-v1-")
        or value.get("future_incompatible_profile") != "OWN_RECORDER_EXACT"
        or value.get("research_import_allowed") is not True
        or value.get("transform") != TRANSFORM
        or not _digest(value.get("transform_implementation_sha256"))
        or value.get("continuity_warning")
        != (
            "continuity between observations is NOT certified; first means first "
            "qualifying RECORDED observation"
        )
        or value.get("selection_rule")
        != "all certified days when fewer than 30, otherwise latest 30 by UTC day"
    ):
        raise ValueError("window contract invalid")
    days = value.get("day_generations")
    if not isinstance(days, list) or not days or len(days) > 30:
        raise ValueError("window day set invalid")
    names = [item.get("day") for item in days]
    if names != sorted(set(names)) or names != value.get("included_certified_days"):
        raise ValueError("window day ordering invalid")
    reference_fields = {
        "day",
        "generation",
        "tag",
        "release_id",
        "manifest_sha256",
        "mapping_data_sha256",
        "mapping_data_size",
        "market_count",
        "observation_count",
        "mapping_asset_id",
    }
    if any(
        not isinstance(item, dict)
        or set(item) != reference_fields
        or any(
            type(item[name]) is not int or item[name] <= 0
            for name in (
                "release_id",
                "mapping_data_size",
                "market_count",
                "observation_count",
                "mapping_asset_id",
            )
        )
        for item in days
    ):
        raise ValueError("window day reference contract invalid")
    closure_cache: dict[
        tuple[str, str, str, str], tuple[dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = {}

    def closure(
        catalog_tag: str, catalog_sha: str, index_tag: str, index_sha: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        key = (catalog_tag, catalog_sha, index_tag, index_sha)
        if key not in closure_cache:
            found_inventory, found_catalog = _verify_inventory_catalog(catalog_tag, catalog_sha)
            found_index = _verify_index(
                index_tag, index_sha, catalog_tag, catalog_sha, found_inventory, found_catalog
            )
            closure_cache[key] = (found_inventory, found_catalog, found_index)
        return closure_cache[key]

    inventory, catalog, index = closure(
        value["catalog_tag"],
        value["catalog_sha256"],
        value["data_index_tag"],
        value["data_index_sha256"],
    )
    if (
        value["inventory_generation"] != inventory["generation"]
        or value["inventory_tag"] != catalog["inventory_tag"]
        or value["inventory_sha256"] != catalog["inventory_sha256"]
        or value["inventory_release_id"] != catalog["inventory_release_id"]
        or value["inventory_last_hour"] != catalog["inventory_last_hour"]
        or value["catalog_generation"] != catalog["generation"]
        or value["catalog_tag"] != "observed-catalog-v1-" + catalog["generation"]
        or value["data_index_generation"] != index["generation"]
        or value["data_index_tag"] != "observed-data-index-v1-" + index["generation"]
        or value["transform_implementation_sha256"] != catalog["transform_implementation_sha256"]
    ):
        raise ValueError("window upstream generation mismatch")

    counts = Counter[str]()
    for reference in days:
        day_release = _release(reference["tag"])
        _, manifest_data = _asset(day_release, "manifest.json")
        if sha(manifest_data) != reference.get("manifest_sha256"):
            raise ValueError("day manifest digest mismatch")
        manifest = json.loads(manifest_data)
        _validate_day(manifest, reference, day_release)
        day_inventory, day_catalog, day_index = closure(
            manifest["catalog_tag"],
            manifest["catalog_sha256"],
            manifest["data_index_tag"],
            manifest["data_index_sha256"],
        )
        if (
            manifest["inventory_generation"] != day_inventory["generation"]
            or manifest["inventory_tag"] != day_catalog["inventory_tag"]
            or manifest["inventory_sha256"] != day_catalog["inventory_sha256"]
            or manifest["inventory_release_id"] != day_catalog["inventory_release_id"]
            or manifest["inventory_last_hour"] != day_catalog["inventory_last_hour"]
            or manifest["catalog_generation"] != day_catalog["generation"]
            or manifest["catalog_tag"] != "observed-catalog-v1-" + day_catalog["generation"]
            or manifest["data_index_generation"] != day_index["generation"]
            or manifest["data_index_tag"] != "observed-data-index-v1-" + day_index["generation"]
            or manifest["transform_implementation_sha256"]
            != day_catalog["transform_implementation_sha256"]
        ):
            raise ValueError("day upstream generation mismatch")
        mapping_asset, mapping_data = _asset(day_release, "mappings.jsonl.gz")
        if (
            mapping_asset["id"] != reference.get("mapping_asset_id")
            or sha(mapping_data) != reference.get("mapping_data_sha256")
            or len(mapping_data) != reference.get("mapping_data_size")
            or sha(mapping_data) != manifest["mapping_data_sha256"]
        ):
            raise ValueError("day mapping content mismatch")
        mappings: dict[str, dict[str, Any]] = {}
        for row in iter_jsonl_gzip(mapping_data):
            validate_mapping(row)
            if row["market"] in mappings:
                raise ValueError("duplicate mapping in certified day")
            mappings[row["market"]] = row
        expected_mappings = {
            row["market"]: row
            for row in day_catalog["mappings"]
            if datetime.fromtimestamp(row["start_us"] / 1_000_000, UTC).date().isoformat()
            == manifest["day"]
        }
        if mappings != expected_mappings or not mappings:
            raise ValueError("day does not exhaust its pinned catalog membership")
        expected_shards = []
        for part in day_index["partitions"]:
            matches = [
                asset
                for asset in part["assets"]
                if asset["name"].endswith("--" + manifest["day"] + ".jsonl.gz")
            ]
            if len(matches) > 1:
                raise ValueError("duplicate indexed day shard")
            for asset in matches:
                expected_shards.append(
                    {
                        "release_id": part["release_id"],
                        "asset_id": asset["id"],
                        "sha256": asset["name"].split("--", 1)[0],
                        "size": asset["size"],
                        "partition": part["partition"],
                    }
                )
        if manifest["canonical_observation_shards"] != expected_shards:
            raise ValueError("day shard set does not exhaust data index")
        expected_errors = [
            error
            for part in day_index["partitions"]
            for error in part["errors"]
            if error["day"] == manifest["day"]
        ]
        if manifest["source_errors"] != expected_errors:
            raise ValueError("day source-error closure mismatch")
        by_side: dict[str, set[str]] = defaultdict(set)
        winners: dict[str, set[tuple[str, str]]] = defaultdict(set)
        observations = 0
        for source in expected_shards:
            shard_release = api(f"releases/{source['release_id']}")
            if shard_release is None or not shard_release.get("immutable"):
                raise ValueError("canonical shard release unavailable")
            matches = [item for item in shard_release["assets"] if item["id"] == source["asset_id"]]
            if len(matches) != 1:
                raise ValueError("canonical shard asset unavailable")
            data = read_asset(matches[0])
            if sha(data) != source["sha256"] or len(data) != source["size"]:
                raise ValueError("canonical shard content mismatch")
            for row in iter_jsonl_gzip(data):
                market = row.get("market")
                if not isinstance(market, str):
                    raise ValueError("canonical shard market identity invalid")
                mapped = mappings.get(market)
                if mapped is None:
                    raise ValueError("canonical shard contains unmapped market")
                if row.get("schema") == OBSERVATION_SCHEMA:
                    validate_observation(row)
                    expected_token = (
                        mapped["up_token"] if row["outcome"] == "UP" else mapped["down_token"]
                    )
                    if (
                        row["asset"] != mapped["asset"]
                        or row["token"] != expected_token
                        or row["start_us"] != mapped["start_us"]
                        or row["end_us"] != mapped["end_us"]
                    ):
                        raise ValueError("observation/mapping relation invalid")
                    if row["availability"] == "observed_ask":
                        by_side[row["market"]].add(row["outcome"])
                    observations += 1
                elif row.get("schema") == RESOLUTION_SCHEMA:
                    validate_resolution(row)
                    expected_token = (
                        mapped["up_token"]
                        if row["winning_outcome"] == "UP"
                        else mapped["down_token"]
                    )
                    if row["asset"] != mapped["asset"] or row["winning_token"] != expected_token:
                        raise ValueError("resolution/mapping relation invalid")
                    winners[row["market"]].add((row["winning_token"], row["winning_outcome"]))
                else:
                    raise ValueError("forbidden canonical row schema")
            counts["bytes"] += len(data)
        if any(by_side[market] != {"UP", "DOWN"} for market in mappings):
            raise ValueError("certified day missing side observations")
        if set(winners) != set(mappings) or any(len(items) != 1 for items in winners.values()):
            raise ValueError("certified day resolution completeness mismatch")
        if (
            len(mappings) != manifest["market_count"]
            or len(mappings) != reference.get("market_count")
            or observations != manifest["observation_count"]
            or observations != reference.get("observation_count")
            or len(winners) != manifest["resolution_count"]
        ):
            raise ValueError("certified day declared counts mismatch")
        counts["markets"] += len(mappings)
        counts["observations"] += observations
        counts["resolutions"] += len(winners)
        counts["bytes"] += len(mapping_data)
    return {
        "verified": True,
        "research_import_allowed": True,
        "profile": PROFILE,
        "profile_version": PROFILE_VERSION,
        "certification_scope": CERTIFICATION_SCOPE,
        "certification_scope_version": CERTIFICATION_SCOPE_VERSION,
        "continuity_between_observations_certified": False,
        "tag": tag,
        "sha256": digest,
        "release_id": release["id"],
        "days": names,
        "counts": dict(counts),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    print(canonical(verify(args.tag, args.sha256)).decode(), end="")


if __name__ == "__main__":
    main()
