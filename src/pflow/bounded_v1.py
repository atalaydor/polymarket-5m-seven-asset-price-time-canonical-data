"""Bounded-population authority over authenticated V3 observed projections.

The bounded profile admits only positively mapped markets that pass every individual
evidence gate.  Unresolved source conditions are retained as an explicit count and
digest and are never interpreted as out of scope.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from pflow.observed_v1 import (
    MAPPING_SCHEMA,
    OBSERVATION_SCHEMA,
    RESOLUTION_SCHEMA,
    TRANSFORM,
    iter_jsonl_gzip,
    jsonl_gzip,
    select_window,
    validate_mapping,
    validate_observation,
    validate_resolution,
)
from pflow.observed_v1 import (
    PROFILE as ROW_PROFILE,
)
from pflow.observed_v1 import (
    PROFILE_VERSION as ROW_PROFILE_VERSION,
)
from pflow.production import (
    DATA_PARTITION,
    _all_releases,
    _load_current_blob,
    _load_json,
    _rolling_day_set_advances,
)
from pflow.production_consumer import (
    _catalog_dependency,
    _source_parts,
    _verify_inventory_catalog,
    _verify_source_proofs,
)
from pflow.release import api, current_commit, publish, read_asset
from pflow.source import canonical, sha

PROFILE = "PENDULUMFLOW_V3_OBSERVED_BOUNDED_V1"
PROFILE_VERSION = 1
SCOPE = "POSITIVE_TARGET_EVIDENCE_ADMISSION_FROM_PINNED_PENDULUMFLOW_V3"
SCOPE_VERSION = 1
DAY_SCHEMA = "pendulumflow-v3-observed-bounded-day.v1"
WINDOW_SCHEMA = "pendulumflow-v3-observed-bounded-window.v1"
REJECTION_SCHEMA = "pendulumflow-v3-observed-bounded-rejection.v1"
CURRENT_SCHEMA = "pendulumflow-v3-observed-bounded-current-reference.v1"
DAY_PREFIX = "bounded-day-v1-"
WINDOW_PREFIX = "bounded-window-v1-"

POPULATION_CLAIM = (
    "The generation contains the positively and authoritatively identified, individually "
    "valid Polymarket 5-minute Up/Down BTC/ETH/SOL/XRP/DOGE/BNB/HYPE markets admitted "
    "from the pinned PendulumFlow V3 evidence under this contract. Unidentified retained "
    "V3 conditions remain unresolved/not-admitted. The generation makes no claim that "
    "those conditions are out-of-scope, and no claim that the admitted population "
    "exhausts every target market historically listed by Polymarket."
)

LIMITATIONS = [
    "admitted population is not exhaustive historical Polymarket coverage",
    "unidentified retained V3 conditions are unresolved and not admitted",
    "continuity and persistence between recorded observations are not certified",
    "missed excursions and time-only crossings are not excluded or synthesized",
    "first means first qualifying lawfully ordered recorded observation",
    "archive collector receipts are not sender HTTP receipts or executions",
]
RECORDED_OBSERVATION_SEMANTICS = {
    "predicate": "0 < remaining_time < T AND price > m*remaining_time + b",
    "arithmetic": "exact_integer_microseconds_and_decimal_rationals",
    "first": "earliest_lawfully_ordered_qualifying_recorded_observation",
    "ties": "fail_closed",
    "result_changing_order_ambiguity": "INDETERMINATE",
    "maximum_signals_per_market": 1,
    "continuity_or_interpolation": False,
}
DAY_METRICS_POPULATION = "only admitted_target_markets in this exact generation"
PROVEN_OPTIMAL_MEANING = (
    "optimal only over the affine strategy space for this exact dataset generation, "
    "admitted evidence population and objective"
)
WINDOW_METRIC_POPULATION = (
    "OBSERVED_LOSS_COUNT, SIGNAL_MARKET_COUNT and MEAN_GROSS_PROFIT_PER_SIGNAL "
    "use only the exact admitted bounded evidence population"
)
REPOSITORY = "atalaydor/polymarket-5m-seven-asset-price-time-canonical-data"
DAY_STATUS_REASONS = {
    "CERTIFIED": [],
    "EXCLUDED": ["no_individually_valid_positively_identified_target_market"],
}


def profile_fields() -> dict[str, Any]:
    return {
        "profile": PROFILE,
        "profile_version": PROFILE_VERSION,
        "certification_scope": SCOPE,
        "certification_scope_version": SCOPE_VERSION,
        "population_exhaustive": False,
        "unresolved_conditions_out_of_scope": False,
        "continuity_between_observations_certified": False,
        "time_only_crossings_permitted": False,
        "canonical_depth_fields_permitted": False,
    }


def _is_canonical_day(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat() == value
    except ValueError:
        return False


def require_import_profile(expected_profile: str) -> None:
    """Reject any attempt to consume bounded authority as a stronger profile."""
    if expected_profile != PROFILE:
        raise ValueError("bounded authority cannot satisfy requested profile: " + expected_profile)


def _output(name: str, value: Any) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={rendered}\n")
    print(canonical({name: value}).decode(), end="")


def _generation(value: dict[str, Any]) -> str:
    core = {key: item for key, item in value.items() if key != "generation"}
    digest = sha(canonical(core))
    if value.get("generation") != digest:
        raise ValueError("content generation mismatch")
    return digest


def _digest_from_name(asset: dict[str, Any]) -> str:
    name = asset.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[0-9a-f]{64}--.+", name):
        raise ValueError("content-addressed asset name required")
    digest = name.split("--", 1)[0]
    if asset.get("digest") != "sha256:" + digest:
        raise ValueError("asset digest/name mismatch")
    return digest


@lru_cache(maxsize=16)
def _load_dependencies(
    catalog_tag: str, catalog_sha: str, index_tag: str, index_sha: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inventory, catalog = _verify_inventory_catalog(catalog_tag, catalog_sha)
    catalog_release = api("releases/tags/" + catalog_tag)
    index_release, index = _load_json(index_tag, index_sha, "data-index.json")
    if (
        catalog_release is None
        or not catalog_release.get("immutable")
        or not index_release.get("immutable")
        or catalog.get("generation") != catalog_tag.removeprefix("observed-catalog-v1-")
        or index.get("generation") != index_tag.removeprefix("observed-data-index-v1-")
        or index.get("catalog_generation") != catalog.get("generation")
        or index.get("catalog_tag") != catalog_tag
        or index.get("catalog_sha256") != catalog_sha
        or index.get("inventory_generation") != catalog.get("inventory_generation")
        or index.get("inventory_tag") != catalog.get("inventory_tag")
        or index.get("inventory_sha256") != catalog.get("inventory_sha256")
        or index.get("complete_expected_partition_set") is not True
        or not isinstance(index.get("partitions"), list)
        or not index["partitions"]
    ):
        raise ValueError("pinned catalog/data-index binding invalid")
    _generation(index)
    expected_source_parts = _source_parts(inventory, catalog["transform_implementation_sha256"])
    actual_source_ids = [part.get("source_partition") for part in index["partitions"]]
    if actual_source_ids != [part["id"] for part in expected_source_parts]:
        raise ValueError("data index does not exhaust deterministic source partitions")
    _verify_index_metadata(inventory, catalog, index, expected_source_parts)
    mappings = catalog.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("catalog mappings absent")
    seen: set[str] = set()
    for mapping in mappings:
        validate_mapping(mapping)
        if mapping["market"] in seen:
            raise ValueError("duplicate catalog market identity")
        seen.add(mapping["market"])
    unresolved = index.get("unresolved_condition_references")
    if (
        not isinstance(unresolved, list)
        or unresolved != sorted(set(unresolved))
        or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in unresolved)
    ):
        raise ValueError("unresolved-condition ledger invalid")
    return inventory, catalog, index


def _verify_index_metadata(
    inventory: dict[str, Any],
    catalog: dict[str, Any],
    index: dict[str, Any],
    expected_parts: list[dict[str, Any]],
) -> None:
    """Reconcile every partition report and payload inventory without source reacquisition."""
    classified = {row["market"] for row in catalog["source_condition_classifications"]}
    inventory_hours = {item["hour"]: item for item in inventory["hours"]}
    unresolved_all: set[str] = set()
    conditionless = Counter[str]()
    for expected, entry in zip(expected_parts, index["partitions"], strict=True):
        condition_release = api("releases/tags/observed-conditions-v1-" + expected["id"])
        if condition_release is None or not condition_release.get("immutable"):
            raise ValueError("encountered-condition partition unavailable or mutable")
        condition_assets = [
            asset
            for asset in condition_release["assets"]
            if asset["name"].endswith("--conditions.jsonl.gz")
        ]
        condition_reports = [
            asset
            for asset in condition_release["assets"]
            if asset["name"].endswith("--report.json")
        ]
        if len(condition_assets) != 1 or len(condition_reports) != 1:
            raise ValueError("encountered-condition partition inventory invalid")
        conditions_data = read_asset(condition_assets[0])
        condition_report_data = read_asset(condition_reports[0])
        condition_report = json.loads(condition_report_data)
        condition_rows = list(iter_jsonl_gzip(conditions_data))
        conditions = {
            row["market"]
            for row in condition_rows
            if set(row) == {"market"} and isinstance(row["market"], str)
        }
        if len(conditions) != len(condition_rows):
            raise ValueError("encountered-condition identity ledger invalid")
        unresolved = sorted(conditions - classified)
        unresolved_all.update(unresolved)
        if unresolved != entry.get("unresolved_condition_references"):
            raise ValueError("indexed unresolved-condition partition ledger invalid")
        missing = condition_report.get("missing_condition_rows_by_product")
        encountered = condition_report.get("encountered_rows_by_product")
        if (
            condition_report.get("schema") != "pendulumflow-v3-encountered-condition-partition.v1"
            or condition_report.get("partition_identity") != expected["id"]
            or condition_report.get("hours") != expected["hours"]
            or condition_report.get("condition_count") != len(conditions)
            or condition_report.get("payload_assets")
            != {
                "conditions.jsonl.gz": {
                    "sha256": sha(conditions_data),
                    "size": len(conditions_data),
                }
            }
            or not isinstance(missing, dict)
            or not isinstance(encountered, dict)
        ):
            raise ValueError("encountered-condition report binding invalid")
        for product in ("best_bid_ask", "market_resolved"):
            missing_count = missing.get(product)
            encountered_count = encountered.get(product)
            if (
                type(missing_count) is not int
                or missing_count < 0
                or type(encountered_count) is not int
                or encountered_count < 0
                or entry.get("unresolved_conditionless_rows", {}).get(product) != missing_count
            ):
                raise ValueError("conditionless source-row accounting invalid")
            conditionless[product] += missing_count
        dependency = _catalog_dependency(catalog, conditions)
        release = api("releases/" + str(entry.get("release_id")))
        if (
            release is None
            or not release.get("immutable")
            or release.get("tag_name") != entry.get("tag")
        ):
            raise ValueError("indexed data partition release unavailable or mutable")
        report_matches = [
            asset for asset in release["assets"] if asset["name"].endswith("--report.json")
        ]
        if len(report_matches) != 1:
            raise ValueError("indexed data partition report missing or duplicate")
        report_data = read_asset(report_matches[0])
        report = json.loads(report_data)
        if (
            sha(report_data) != entry.get("report_sha256")
            or report.get("schema") != DATA_PARTITION
            or report.get("partition_identity") != entry.get("partition")
            or report.get("source_partition_identity") != expected["id"]
            or report.get("catalog_dependency") != dependency
            or report.get("hours") != expected["hours"]
            or report.get("transform") != TRANSFORM
            or report.get("transform_implementation_sha256")
            != catalog["transform_implementation_sha256"]
            or report.get("target_errors") != entry.get("errors")
        ):
            raise ValueError("indexed data partition report binding invalid")
        binding = sha(
            canonical(
                {
                    "partition": expected["id"],
                    "catalog_dependency": dependency,
                    "transform": TRANSFORM,
                    "transform_implementation_sha256": catalog["transform_implementation_sha256"],
                }
            )
        )
        if entry.get("partition") != binding or entry.get("tag") != "observed-data-v1-" + binding:
            raise ValueError("indexed data partition identity invalid")
        _verify_source_proofs(report, inventory, expected["hours"])
        expected_decoded = {
            product: sum(
                inventory_hours[hour]["manifest"]["products"][product]["row_count"]
                for hour in expected["hours"]
            )
            for product in ("best_bid_ask", "market_resolved")
        }
        if report.get("decoded_rows") != expected_decoded:
            raise ValueError("indexed data partition decoded-row accounting invalid")
        classifications = report.get("classification_counts")
        if not isinstance(classifications, dict):
            raise ValueError("indexed data partition classification ledger absent")
        for product, count in expected_decoded.items():
            actual = sum(
                value
                for key, value in classifications.items()
                if isinstance(key, str)
                and key.startswith(product + ":")
                and type(value) is int
                and value >= 0
            )
            if actual != count:
                raise ValueError("indexed data partition classification accounting invalid")
        actual_assets = {
            asset["name"]: {
                key: asset.get(key)
                for key in ("id", "name", "size", "digest", "browser_download_url")
            }
            for asset in release["assets"]
        }
        indexed_assets = {asset["name"]: asset for asset in entry.get("assets", [])}
        if actual_assets != indexed_assets:
            raise ValueError("indexed data partition payload inventory diverged")
        payloads = {
            asset["name"].split("--", 1)[1]: {
                "sha256": _digest_from_name(asset),
                "size": asset["size"],
            }
            for asset in release["assets"]
            if not asset["name"].endswith("--report.json")
        }
        if report.get("payload_assets") != payloads:
            raise ValueError("indexed data partition report payload closure invalid")
    if index["unresolved_condition_references"] != sorted(unresolved_all) or index.get(
        "unresolved_conditionless_rows"
    ) != dict(conditionless):
        raise ValueError("inventory-wide unresolved ledger does not reconcile")


def _day_sources(index: dict[str, Any], day: str) -> list[dict[str, Any]]:
    result = []
    suffix = "--" + day + ".jsonl.gz"
    partitions: set[str] = set()
    for part in index["partitions"]:
        partition = part.get("partition")
        if not isinstance(partition, str) or partition in partitions:
            raise ValueError("duplicate/invalid retained partition identity")
        partitions.add(partition)
        assets = part.get("assets")
        if not isinstance(assets, list):
            raise ValueError("retained partition asset inventory absent")
        matches = [asset for asset in assets if str(asset.get("name", "")).endswith(suffix)]
        if len(matches) > 1:
            raise ValueError("duplicate retained day asset")
        if not matches:
            continue
        asset = matches[0]
        digest = _digest_from_name(asset)
        result.append(
            {
                "partition": partition,
                "source_partition": part.get("source_partition"),
                "release_id": part.get("release_id"),
                "release_tag": part.get("tag"),
                "asset_id": asset.get("id"),
                "asset_name": asset.get("name"),
                "sha256": digest,
                "size": asset.get("size"),
                "browser_download_url": asset.get("browser_download_url"),
            }
        )
    result.sort(key=lambda item: item["partition"])
    return result


def _source_errors(index: dict[str, Any], day: str) -> list[dict[str, Any]]:
    errors = []
    for part in index["partitions"]:
        for item in part.get("errors", []):
            if item.get("day") == day:
                errors.append(item)
    return sorted(errors, key=lambda item: canonical(item))


def _mapping_relation(row: dict[str, Any], mapping: dict[str, Any]) -> bool:
    outcome = row.get("outcome")
    expected = (
        {"UP": mapping["up_token"], "DOWN": mapping["down_token"]}.get(outcome)
        if isinstance(outcome, str)
        else None
    )
    return (
        row.get("asset") == mapping["asset"]
        and row.get("start_us") == mapping["start_us"]
        and row.get("end_us") == mapping["end_us"]
        and row.get("token") == expected
    )


def _resolution_relation(row: dict[str, Any], mapping: dict[str, Any]) -> bool:
    outcome = row.get("winning_outcome")
    expected = (
        {"UP": mapping["up_token"], "DOWN": mapping["down_token"]}.get(outcome)
        if isinstance(outcome, str)
        else None
    )
    return row.get("asset") == mapping["asset"] and row.get("winning_token") == expected


def _validate_source_metadata(source: dict[str, Any]) -> dict[str, Any]:
    release = api("releases/" + str(source["release_id"]))
    if (
        release is None
        or not release.get("immutable")
        or release.get("tag_name") != source["release_tag"]
    ):
        raise ValueError("retained canonical release unavailable or mutable")
    matches = [asset for asset in release["assets"] if asset.get("id") == source["asset_id"]]
    if len(matches) != 1:
        raise ValueError("retained canonical asset unavailable")
    asset: dict[str, Any] = matches[0]
    if (
        asset.get("name") != source["asset_name"]
        or asset.get("size") != source["size"]
        or _digest_from_name(asset) != source["sha256"]
    ):
        raise ValueError("retained canonical asset metadata diverged")
    return asset


def _assess_day(
    inventory: dict[str, Any], catalog: dict[str, Any], index: dict[str, Any], day: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    mappings = [
        row
        for row in catalog["mappings"]
        if datetime.fromtimestamp(row["start_us"] / 1_000_000, UTC).date().isoformat() == day
    ]
    market_map = {row["market"]: row for row in mappings}
    if len(market_map) != len(mappings):
        raise ValueError("duplicate daily market identity")
    sides: dict[str, Counter[str]] = defaultdict(Counter)
    winners: dict[str, set[tuple[str, str]]] = defaultdict(set)
    row_counts: Counter[str] = Counter()
    invalid: dict[str, set[str]] = defaultdict(set)
    source_assets = _day_sources(index, day)
    source_parts = {
        item["id"]: set(item["hours"])
        for item in _source_parts(inventory, catalog["transform_implementation_sha256"])
    }
    inventory_hours = {item["hour"]: item for item in inventory["hours"]}
    for source in source_assets:
        allowed_hours = source_parts.get(source["source_partition"])
        if allowed_hours is None:
            raise ValueError("retained data partition has unknown source partition")
        asset = _validate_source_metadata(source)
        data = read_asset(asset)
        if sha(data) != source["sha256"] or len(data) != source["size"]:
            raise ValueError("retained canonical object failed read-back")
        for row in iter_jsonl_gzip(data):
            market = row.get("market")
            if not isinstance(market, str) or market not in market_map:
                raise ValueError("retained day row is not positively mapped by pinned catalog")
            mapping = market_map[market]
            row_counts[market] += 1
            if row.get("schema") == OBSERVATION_SCHEMA:
                try:
                    validate_observation(row)
                except ValueError:
                    invalid[market].add("malformed_recorded_observation")
                    continue
                if not _mapping_relation(row, mapping):
                    invalid[market].add("observation_identity_or_orientation_mismatch")
                elif row["availability"] == "observed_ask":
                    sides[market][row["outcome"]] += 1
                product = "best_bid_ask"
            elif row.get("schema") == RESOLUTION_SCHEMA:
                try:
                    validate_resolution(row)
                except ValueError:
                    invalid[market].add("malformed_official_resolution")
                    continue
                if not _resolution_relation(row, mapping):
                    invalid[market].add("resolution_identity_or_orientation_mismatch")
                else:
                    winners[market].add((row["winning_token"], row["winning_outcome"]))
                product = "market_resolved"
            else:
                invalid[market].add("forbidden_or_unknown_canonical_row_schema")
                continue
            source_hour = row.get("source_hour")
            if source_hour not in allowed_hours or source_hour not in inventory_hours:
                invalid[market].add("source_hour_outside_authenticated_partition")
                continue
            source_item = inventory_hours[source_hour]
            source_product = source_item["manifest"]["products"][product]
            ordinal = row.get("source_product_row_ordinal")
            if (
                row.get("source_manifest_sha256") != source_item["manifest_sha256"]
                or row.get("source_product_sha256") != source_product["sha256"]
                or type(ordinal) is not int
                or not 0 <= ordinal < source_product["row_count"]
            ):
                invalid[market].add("source_product_locator_or_integrity_mismatch")
    for error in _source_errors(index, day):
        market = error.get("market")
        if isinstance(market, str) and market in market_map:
            invalid[market].add("retained_target_source_error")
    admitted = []
    rejected = []
    for mapping in mappings:
        market = mapping["market"]
        reasons = invalid[market]
        for side in ("UP", "DOWN"):
            if not sides[market][side]:
                reasons.add("missing_recorded_best_ask_" + side.lower())
        if not winners[market]:
            reasons.add("missing_official_resolution")
        elif len(winners[market]) != 1:
            reasons.add("contradictory_official_resolution")
        if reasons:
            rejected.append(
                {
                    "schema": REJECTION_SCHEMA,
                    **profile_fields(),
                    "market": market,
                    "asset": mapping["asset"],
                    "start_us": mapping["start_us"],
                    "end_us": mapping["end_us"],
                    "reasons": sorted(reasons),
                    "record_count": row_counts[market],
                    "observed_up_ask_count": sides[market]["UP"],
                    "observed_down_ask_count": sides[market]["DOWN"],
                    "resolution_evidence_count": len(winners[market]),
                }
            )
        else:
            admitted.append(mapping)
    admitted.sort(key=lambda row: (row["start_us"], row["asset"], row["market"]))
    rejected.sort(key=lambda row: (row["start_us"], row["asset"], row["market"]))
    counts = {
        "positively_identified_target_markets": len(mappings),
        "admitted_target_markets": len(admitted),
        "rejected_target_markets": len(rejected),
        "admitted_observation_and_resolution_rows": sum(row_counts[m["market"]] for m in admitted),
        "rejected_observation_and_resolution_rows": sum(row_counts[r["market"]] for r in rejected),
    }
    return admitted, rejected, counts, source_assets


def certify_day(
    catalog_tag: str, catalog_sha: str, index_tag: str, index_sha: str, day: str
) -> dict[str, Any]:
    if day >= datetime.now(UTC).date().isoformat():
        raise ValueError("partial current or future UTC day is ineligible")
    inventory, catalog, index = _load_dependencies(catalog_tag, catalog_sha, index_tag, index_sha)
    admitted, rejected, counts, sources = _assess_day(inventory, catalog, index, day)
    unresolved = index["unresolved_condition_references"]
    admitted_data = jsonl_gzip(admitted)
    rejected_data = jsonl_gzip(rejected)
    status = "CERTIFIED" if admitted else "EXCLUDED"
    reasons = [] if admitted else ["no_individually_valid_positively_identified_target_market"]
    projection = {
        "row_profile": ROW_PROFILE,
        "row_profile_version": ROW_PROFILE_VERSION,
        "row_filter": "market_identity_in_admitted-markets.jsonl.gz",
        "source_assets": sources,
        "admitted_mapping_sha256": sha(admitted_data),
    }
    manifest = {
        "schema": DAY_SCHEMA,
        **profile_fields(),
        "status": status,
        "day": day,
        "population_claim": POPULATION_CLAIM,
        "limitations": LIMITATIONS,
        "research_metrics_population": DAY_METRICS_POPULATION,
        "proven_optimal_meaning": PROVEN_OPTIMAL_MEANING,
        "inventory_generation": catalog["inventory_generation"],
        "inventory_last_hour": catalog["inventory_last_hour"],
        "inventory_tag": catalog["inventory_tag"],
        "inventory_sha256": catalog["inventory_sha256"],
        "inventory_release_id": catalog["inventory_release_id"],
        "catalog_generation": catalog["generation"],
        "catalog_tag": catalog_tag,
        "catalog_sha256": catalog_sha,
        "data_index_generation": index["generation"],
        "data_index_tag": index_tag,
        "data_index_sha256": index_sha,
        "source_transform": TRANSFORM,
        "canonical_mapping_schema": MAPPING_SCHEMA,
        "canonical_observation_schema": OBSERVATION_SCHEMA,
        "canonical_resolution_schema": RESOLUTION_SCHEMA,
        "canonical_projection": projection,
        **counts,
        "admitted_market_set_sha256": sha(canonical([m["market"] for m in admitted])),
        "admitted_mapping_sha256": sha(admitted_data),
        "admitted_mapping_size": len(admitted_data),
        "rejected_target_set_sha256": sha(canonical([r["market"] for r in rejected])),
        "rejected_evidence_sha256": sha(rejected_data),
        "rejected_evidence_size": len(rejected_data),
        "inventory_wide_unresolved_not_admitted_count": len(unresolved),
        "inventory_wide_unresolved_not_admitted_set_sha256": sha(canonical(unresolved)),
        "unresolved_condition_day_membership_known": False,
        "unresolved_conditionless_rows": index.get("unresolved_conditionless_rows", {}),
        "unresolved_conditions_classified_out_of_scope": 0,
        "certification_reasons": reasons,
        "source_assets": sources,
        "source_errors_not_joined_to_admitted_identity_count": sum(
            1
            for error in _source_errors(index, day)
            if error.get("market") not in {m["market"] for m in admitted}
        ),
        "v3_historical_source_reacquisition_bytes": 0,
        "research_import_allowed": status == "CERTIFIED",
        "implementation_commit": current_commit(),
    }
    manifest["canonical_projection_sha256"] = sha(canonical(projection))
    manifest["generation"] = sha(canonical(manifest))
    payloads = {
        "manifest.json": canonical(manifest),
        "admitted-markets.jsonl.gz": admitted_data,
        "rejected-target-evidence.jsonl.gz": rejected_data,
    }
    tag = DAY_PREFIX + manifest["generation"]
    release = publish(
        tag,
        payloads,
        current_commit(),
        f"Bounded observed bootstrap day {day}: {status}",
        "Bounded, non-exhaustive V3 recorded-observation authority. Read limitations.",
    )
    _output("bounded_day_tag", tag)
    print(
        canonical(
            {
                "release_id": release["id"],
                "day": day,
                "status": status,
                **counts,
                "inventory_wide_unresolved_not_admitted_count": len(unresolved),
            }
        ).decode(),
        end="",
    )
    return manifest


def _release_payload(release: dict[str, Any], suffix: str) -> tuple[dict[str, Any], bytes]:
    matches = [asset for asset in release["assets"] if asset["name"].endswith("--" + suffix)]
    if len(matches) != 1:
        raise ValueError("unique release asset required: " + suffix)
    return matches[0], read_asset(matches[0])


def _load_day_release(release: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    suffixes = {asset["name"].split("--", 1)[-1] for asset in release.get("assets", [])}
    if suffixes != {
        "manifest.json",
        "admitted-markets.jsonl.gz",
        "rejected-target-evidence.jsonl.gz",
    }:
        raise ValueError("bounded day release asset inventory invalid")
    manifest_asset, raw = _release_payload(release, "manifest.json")
    manifest = json.loads(raw)
    required_fields = {
        "schema",
        *profile_fields(),
        "status",
        "day",
        "population_claim",
        "limitations",
        "research_metrics_population",
        "proven_optimal_meaning",
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
        "source_transform",
        "canonical_mapping_schema",
        "canonical_observation_schema",
        "canonical_resolution_schema",
        "canonical_projection",
        "positively_identified_target_markets",
        "admitted_target_markets",
        "rejected_target_markets",
        "admitted_observation_and_resolution_rows",
        "rejected_observation_and_resolution_rows",
        "admitted_market_set_sha256",
        "admitted_mapping_sha256",
        "admitted_mapping_size",
        "rejected_target_set_sha256",
        "rejected_evidence_sha256",
        "rejected_evidence_size",
        "inventory_wide_unresolved_not_admitted_count",
        "inventory_wide_unresolved_not_admitted_set_sha256",
        "unresolved_condition_day_membership_known",
        "unresolved_conditionless_rows",
        "unresolved_conditions_classified_out_of_scope",
        "certification_reasons",
        "source_assets",
        "source_errors_not_joined_to_admitted_identity_count",
        "v3_historical_source_reacquisition_bytes",
        "research_import_allowed",
        "implementation_commit",
        "canonical_projection_sha256",
        "generation",
    }
    if not _is_canonical_day(manifest.get("day")):
        raise ValueError("bounded day identity invalid")
    assessed_day = datetime.strptime(manifest["day"], "%Y-%m-%d").date()
    if (
        not release.get("immutable")
        or set(manifest) != required_fields
        or manifest.get("schema") != DAY_SCHEMA
        or any(manifest.get(k) != v for k, v in profile_fields().items())
        or _generation(manifest) != release["tag_name"].removeprefix(DAY_PREFIX)
        or _digest_from_name(manifest_asset) != sha(raw)
        or release.get("target_commitish") != manifest.get("implementation_commit")
        or assessed_day >= datetime.now(UTC).date()
        or manifest.get("population_claim") != POPULATION_CLAIM
        or manifest.get("limitations") != LIMITATIONS
        or manifest.get("research_metrics_population") != DAY_METRICS_POPULATION
        or manifest.get("proven_optimal_meaning") != PROVEN_OPTIMAL_MEANING
        or manifest.get("source_transform") != TRANSFORM
        or manifest.get("canonical_mapping_schema") != MAPPING_SCHEMA
        or manifest.get("canonical_observation_schema") != OBSERVATION_SCHEMA
        or manifest.get("canonical_resolution_schema") != RESOLUTION_SCHEMA
        or manifest.get("status") not in DAY_STATUS_REASONS
        or manifest.get("certification_reasons") != DAY_STATUS_REASONS.get(manifest.get("status"))
        or manifest.get("research_import_allowed") is not (manifest.get("status") == "CERTIFIED")
        or type(manifest.get("admitted_target_markets")) is not int
        or manifest["admitted_target_markets"] < 0
        or type(manifest.get("rejected_target_markets")) is not int
        or manifest["rejected_target_markets"] < 0
        or manifest.get("unresolved_conditions_classified_out_of_scope") != 0
        or manifest.get("unresolved_condition_day_membership_known") is not False
        or manifest.get("v3_historical_source_reacquisition_bytes") != 0
    ):
        raise ValueError("bounded day release identity invalid")
    return manifest_asset, manifest


def publish_window(
    catalog_tag: str, catalog_sha: str, index_tag: str, index_sha: str
) -> dict[str, Any]:
    _, catalog, index = _load_dependencies(catalog_tag, catalog_sha, index_tag, index_sha)
    latest: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    certified: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for release in _all_releases():
        if (
            not str(release.get("tag_name", "")).startswith(DAY_PREFIX)
            or not release.get("immutable")
            or release.get("draft")
            or release.get("prerelease")
        ):
            continue
        _, manifest = _load_day_release(release)
        prior = latest.get(manifest["day"])
        rank = (manifest["inventory_release_id"], manifest["inventory_last_hour"], release["id"])
        if prior is None or rank > (
            prior[1]["inventory_release_id"],
            prior[1]["inventory_last_hour"],
            prior[0]["id"],
        ):
            latest[manifest["day"]] = (release, manifest)
        if manifest["status"] == "CERTIFIED":
            prior_certified = certified.get(manifest["day"])
            if prior_certified is None or rank > (
                prior_certified[1]["inventory_release_id"],
                prior_certified[1]["inventory_last_hour"],
                prior_certified[0]["id"],
            ):
                certified[manifest["day"]] = (release, manifest)
    selected = select_window(m for _, m in certified.values())
    if not selected:
        raise ValueError("no certified bounded day exists")
    refs = []
    for manifest in selected:
        release, _ = certified[manifest["day"]]
        manifest_asset, _ = _release_payload(release, "manifest.json")
        admitted_asset, _ = _release_payload(release, "admitted-markets.jsonl.gz")
        rejected_asset, _ = _release_payload(release, "rejected-target-evidence.jsonl.gz")
        refs.append(
            {
                "day": manifest["day"],
                "generation": manifest["generation"],
                "tag": release["tag_name"],
                "release_id": release["id"],
                "manifest_asset_id": manifest_asset["id"],
                "manifest_sha256": _digest_from_name(manifest_asset),
                "admitted_asset_id": admitted_asset["id"],
                "admitted_mapping_sha256": manifest["admitted_mapping_sha256"],
                "admitted_mapping_size": manifest["admitted_mapping_size"],
                "rejected_asset_id": rejected_asset["id"],
                "rejected_evidence_sha256": manifest["rejected_evidence_sha256"],
                "rejected_evidence_size": manifest["rejected_evidence_size"],
                "admitted_target_markets": manifest["admitted_target_markets"],
                "rejected_target_markets": manifest["rejected_target_markets"],
                "admitted_observation_and_resolution_rows": manifest[
                    "admitted_observation_and_resolution_rows"
                ],
                "rejected_observation_and_resolution_rows": manifest[
                    "rejected_observation_and_resolution_rows"
                ],
                "inventory_wide_unresolved_not_admitted_count": manifest[
                    "inventory_wide_unresolved_not_admitted_count"
                ],
            }
        )
    totals = Counter[str]()
    for ref in refs:
        totals["admitted_target_markets"] += ref["admitted_target_markets"]
        totals["rejected_target_markets"] += ref["rejected_target_markets"]
    newest_certified = refs[-1]["day"]
    rollover_blocked_by = sorted(
        day
        for day, (_, manifest) in latest.items()
        if manifest["status"] != "CERTIFIED"
        and (
            day > newest_certified
            or (
                day in certified
                and (
                    manifest["inventory_release_id"],
                    manifest["inventory_last_hour"],
                )
                > (
                    certified[day][1]["inventory_release_id"],
                    certified[day][1]["inventory_last_hour"],
                )
            )
        )
    )
    value = {
        "schema": WINDOW_SCHEMA,
        **profile_fields(),
        "research_import_allowed": True,
        "research_import_allowed_profile": PROFILE,
        "population_claim": POPULATION_CLAIM,
        "limitations": LIMITATIONS,
        "metric_population_rule": WINDOW_METRIC_POPULATION,
        "proven_optimal_meaning": PROVEN_OPTIMAL_MEANING,
        "rejected_import_profiles": ["PENDULUMFLOW_V3_OBSERVED", "OWN_RECORDER_EXACT"],
        "row_profile": ROW_PROFILE,
        "row_profile_version": ROW_PROFILE_VERSION,
        "recorded_observation_semantics": RECORDED_OBSERVATION_SEMANTICS,
        "inventory_generation": catalog["inventory_generation"],
        "inventory_last_hour": catalog["inventory_last_hour"],
        "inventory_release_id": catalog["inventory_release_id"],
        "inventory_tag": catalog["inventory_tag"],
        "inventory_sha256": catalog["inventory_sha256"],
        "catalog_generation": catalog["generation"],
        "catalog_tag": catalog_tag,
        "catalog_sha256": catalog_sha,
        "data_index_generation": index["generation"],
        "data_index_tag": index_tag,
        "data_index_sha256": index_sha,
        "included_certified_days": [r["day"] for r in refs],
        "day_generations": refs,
        "excluded_or_pending": [
            {
                "day": day,
                "status": manifest["status"],
                "reasons": manifest["certification_reasons"],
                "generation": manifest["generation"],
                "tag": release["tag_name"],
                "release_id": release["id"],
                "inventory_release_id": manifest["inventory_release_id"],
                "inventory_last_hour": manifest["inventory_last_hour"],
            }
            for day, (release, manifest) in sorted(latest.items())
            if manifest["status"] != "CERTIFIED"
        ],
        "current_rollover_blocked_by_failed_newer_days": rollover_blocked_by,
        "admitted_target_markets": totals["admitted_target_markets"],
        "rejected_target_markets": totals["rejected_target_markets"],
        "inventory_wide_unresolved_not_admitted_count": len(
            index["unresolved_condition_references"]
        ),
        "inventory_wide_unresolved_not_admitted_set_sha256": sha(
            canonical(index["unresolved_condition_references"])
        ),
        "unresolved_condition_day_membership_known": False,
        "selection_rule": "all certified days when fewer than 30, otherwise latest 30 by UTC day",
        "verification": "python -m pflow.bounded_v1 verify --tag <tag> --sha256 <sha256>",
        "repository": REPOSITORY,
        "v3_historical_source_reacquisition_bytes": 0,
        "implementation_commit": current_commit(),
    }
    value["generation"] = sha(canonical(value))
    payload = canonical(value)
    tag = WINDOW_PREFIX + value["generation"]
    release = publish(
        tag,
        {"consumer-handoff.json": payload},
        current_commit(),
        "PendulumFlow V3 observed bounded bootstrap window",
        "Factory-usable only as PENDULUMFLOW_V3_OBSERVED_BOUNDED_V1.",
    )
    verify_window(tag, sha(payload))
    _update_current(tag, sha(payload), value, release["id"])
    _output("bounded_window_tag", tag)
    _output("consumer_handoff_sha256", sha(payload))
    print(
        canonical({"release_id": release["id"], "days": value["included_certified_days"]}).decode(),
        end="",
    )
    return value


def _strict_day_assets(
    release: dict[str, Any], manifest: dict[str, Any], index: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    admitted_asset, admitted_data = _release_payload(release, "admitted-markets.jsonl.gz")
    rejected_asset, rejected_data = _release_payload(release, "rejected-target-evidence.jsonl.gz")
    if (
        sha(admitted_data) != manifest["admitted_mapping_sha256"]
        or len(admitted_data) != manifest["admitted_mapping_size"]
        or _digest_from_name(admitted_asset) != manifest["admitted_mapping_sha256"]
        or sha(rejected_data) != manifest["rejected_evidence_sha256"]
        or len(rejected_data) != manifest["rejected_evidence_size"]
        or _digest_from_name(rejected_asset) != manifest["rejected_evidence_sha256"]
    ):
        raise ValueError("bounded day payload digest mismatch")
    admitted = list(iter_jsonl_gzip(admitted_data))
    rejected = list(iter_jsonl_gzip(rejected_data))
    seen: set[str] = set()
    for row in admitted:
        validate_mapping(row)
        if row["market"] in seen:
            raise ValueError("duplicate admitted market")
        seen.add(row["market"])
    for row in rejected:
        expected_fields = {
            "schema",
            *profile_fields(),
            "market",
            "asset",
            "start_us",
            "end_us",
            "reasons",
            "record_count",
            "observed_up_ask_count",
            "observed_down_ask_count",
            "resolution_evidence_count",
        }
        if (
            set(row) != expected_fields
            or row.get("schema") != REJECTION_SCHEMA
            or any(row.get(k) != v for k, v in profile_fields().items())
            or row.get("market") in seen
            or not isinstance(row.get("reasons"), list)
            or not row["reasons"]
        ):
            raise ValueError("rejected target evidence malformed")
        seen.add(row["market"])
    if (
        len(admitted) != manifest["admitted_target_markets"]
        or len(rejected) != manifest["rejected_target_markets"]
        or sha(canonical([m["market"] for m in admitted])) != manifest["admitted_market_set_sha256"]
        or sha(canonical([r["market"] for r in rejected])) != manifest["rejected_target_set_sha256"]
        or manifest["source_assets"] != _day_sources(index, manifest["day"])
    ):
        raise ValueError("bounded day population/source closure invalid")
    for source in manifest["source_assets"]:
        _validate_source_metadata(source)
    return admitted, rejected


def verify_window(tag: str, digest: str, expected_profile: str = PROFILE) -> dict[str, Any]:
    require_import_profile(expected_profile)
    if not re.fullmatch(r"bounded-window-v1-[0-9a-f]{64}", tag):
        raise ValueError("exact bounded window tag required")
    release = api("releases/tags/" + tag)
    if release is None or not release.get("immutable"):
        raise ValueError("immutable bounded window unavailable")
    if release.get("draft") or release.get("prerelease") or len(release.get("assets", [])) != 1:
        raise ValueError("bounded window release inventory invalid")
    asset, raw = _release_payload(release, "consumer-handoff.json")
    value = json.loads(raw)
    required_fields = {
        "schema",
        *profile_fields(),
        "research_import_allowed",
        "research_import_allowed_profile",
        "population_claim",
        "limitations",
        "metric_population_rule",
        "proven_optimal_meaning",
        "rejected_import_profiles",
        "row_profile",
        "row_profile_version",
        "recorded_observation_semantics",
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
        "included_certified_days",
        "day_generations",
        "excluded_or_pending",
        "current_rollover_blocked_by_failed_newer_days",
        "admitted_target_markets",
        "rejected_target_markets",
        "inventory_wide_unresolved_not_admitted_count",
        "inventory_wide_unresolved_not_admitted_set_sha256",
        "unresolved_condition_day_membership_known",
        "selection_rule",
        "verification",
        "repository",
        "v3_historical_source_reacquisition_bytes",
        "implementation_commit",
        "generation",
    }
    if (
        sha(raw) != digest
        or _digest_from_name(asset) != digest
        or set(value) != required_fields
        or value.get("schema") != WINDOW_SCHEMA
        or any(value.get(k) != v for k, v in profile_fields().items())
        or _generation(value) != tag.removeprefix(WINDOW_PREFIX)
        or value.get("research_import_allowed") is not True
        or value.get("research_import_allowed_profile") != PROFILE
        or value.get("rejected_import_profiles")
        != ["PENDULUMFLOW_V3_OBSERVED", "OWN_RECORDER_EXACT"]
        or value.get("population_claim") != POPULATION_CLAIM
        or value.get("limitations") != LIMITATIONS
        or value.get("v3_historical_source_reacquisition_bytes") != 0
        or release.get("target_commitish") != value.get("implementation_commit")
        or value.get("row_profile") != ROW_PROFILE
        or value.get("row_profile_version") != ROW_PROFILE_VERSION
        or value.get("recorded_observation_semantics") != RECORDED_OBSERVATION_SEMANTICS
        or value.get("metric_population_rule") != WINDOW_METRIC_POPULATION
        or value.get("proven_optimal_meaning") != PROVEN_OPTIMAL_MEANING
        or value.get("repository") != REPOSITORY
        or value.get("selection_rule")
        != "all certified days when fewer than 30, otherwise latest 30 by UTC day"
    ):
        raise ValueError("bounded consumer handoff contract invalid")
    inventory, catalog, index = _load_dependencies(
        value["catalog_tag"],
        value["catalog_sha256"],
        value["data_index_tag"],
        value["data_index_sha256"],
    )
    if (
        catalog["generation"] != value["catalog_generation"]
        or index["generation"] != value["data_index_generation"]
        or value["inventory_generation"] != catalog["inventory_generation"]
        or value["inventory_last_hour"] != catalog["inventory_last_hour"]
        or value["inventory_release_id"] != catalog["inventory_release_id"]
        or value["inventory_tag"] != catalog["inventory_tag"]
        or value["inventory_sha256"] != catalog["inventory_sha256"]
        or value["inventory_wide_unresolved_not_admitted_count"]
        != len(index["unresolved_condition_references"])
        or value["inventory_wide_unresolved_not_admitted_set_sha256"]
        != sha(canonical(index["unresolved_condition_references"]))
        or value.get("unresolved_condition_day_membership_known") is not False
    ):
        raise ValueError("bounded upstream generation mismatch")
    refs = value.get("day_generations")
    if not isinstance(refs, list) or not refs or len(refs) > 30:
        raise ValueError("bounded window day set invalid")
    names = [ref.get("day") for ref in refs]
    if (
        not all(_is_canonical_day(name) for name in names)
        or names != sorted(set(names))
        or names != value.get("included_certified_days")
    ):
        raise ValueError("bounded window day ordering invalid")
    excluded = value.get("excluded_or_pending")
    if not isinstance(excluded, list):
        raise ValueError("bounded window exclusion ledger invalid")
    excluded_days: list[str] = []
    for item in excluded:
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "day",
                "status",
                "reasons",
                "generation",
                "tag",
                "release_id",
                "inventory_release_id",
                "inventory_last_hour",
            }
            or not _is_canonical_day(item.get("day"))
            or item.get("status") != "EXCLUDED"
            or item.get("reasons") != DAY_STATUS_REASONS["EXCLUDED"]
        ):
            raise ValueError("bounded window exclusion ledger invalid")
        excluded_release = api("releases/" + str(item["release_id"]))
        if excluded_release is None or excluded_release.get("tag_name") != item["tag"]:
            raise ValueError("bounded excluded day release unavailable")
        _, excluded_manifest = _load_day_release(excluded_release)
        if (
            any(
                excluded_manifest[field] != item[field]
                for field in (
                    "day",
                    "status",
                    "generation",
                    "inventory_release_id",
                    "inventory_last_hour",
                )
            )
            or excluded_manifest["certification_reasons"] != item["reasons"]
        ):
            raise ValueError("bounded window exclusion binding invalid")
        excluded_days.append(item["day"])
    if excluded_days != sorted(set(excluded_days)):
        raise ValueError("bounded window exclusion ledger invalid")
    rollover = value.get("current_rollover_blocked_by_failed_newer_days")
    if (
        not isinstance(rollover, list)
        or not all(_is_canonical_day(day) for day in rollover)
        or rollover != sorted(set(rollover))
        or not set(rollover).issubset(excluded_days)
        or not (set(excluded_days) & set(names)).issubset(rollover)
    ):
        raise ValueError("bounded window rollover ledger invalid")
    totals = Counter[str]()
    for ref in refs:
        if set(ref) != {
            "day",
            "generation",
            "tag",
            "release_id",
            "manifest_asset_id",
            "manifest_sha256",
            "admitted_asset_id",
            "admitted_mapping_sha256",
            "admitted_mapping_size",
            "rejected_asset_id",
            "rejected_evidence_sha256",
            "rejected_evidence_size",
            "admitted_target_markets",
            "rejected_target_markets",
            "admitted_observation_and_resolution_rows",
            "rejected_observation_and_resolution_rows",
            "inventory_wide_unresolved_not_admitted_count",
        }:
            raise ValueError("bounded day reference field allowlist invalid")
        day_release = api("releases/" + str(ref["release_id"]))
        if day_release is None or day_release.get("tag_name") != ref["tag"]:
            raise ValueError("bounded day release unavailable")
        manifest_asset, manifest = _load_day_release(day_release)
        day_inventory, day_catalog, day_index = _load_dependencies(
            manifest["catalog_tag"],
            manifest["catalog_sha256"],
            manifest["data_index_tag"],
            manifest["data_index_sha256"],
        )
        if (
            manifest["status"] != "CERTIFIED"
            or manifest["research_import_allowed"] is not True
            or manifest["admitted_target_markets"] <= 0
            or manifest["day"] != ref["day"]
            or manifest["generation"] != ref["generation"]
            or manifest_asset["id"] != ref["manifest_asset_id"]
            or _digest_from_name(manifest_asset) != ref["manifest_sha256"]
            or manifest["data_index_generation"] != day_index["generation"]
            or manifest["catalog_generation"] != day_catalog["generation"]
            or manifest["inventory_generation"] != day_catalog["inventory_generation"]
            or manifest["inventory_last_hour"] != day_catalog["inventory_last_hour"]
            or manifest["inventory_release_id"] != day_catalog["inventory_release_id"]
            or manifest["inventory_tag"] != day_catalog["inventory_tag"]
            or manifest["inventory_sha256"] != day_catalog["inventory_sha256"]
            or manifest["inventory_wide_unresolved_not_admitted_count"]
            != len(day_index["unresolved_condition_references"])
            or manifest["inventory_wide_unresolved_not_admitted_set_sha256"]
            != sha(canonical(day_index["unresolved_condition_references"]))
            or manifest["unresolved_conditionless_rows"]
            != day_index["unresolved_conditionless_rows"]
            or manifest["unresolved_conditions_classified_out_of_scope"] != 0
            or manifest["population_claim"] != POPULATION_CLAIM
            or manifest["v3_historical_source_reacquisition_bytes"] != 0
            or manifest["canonical_projection_sha256"]
            != sha(canonical(manifest["canonical_projection"]))
            or manifest["canonical_projection"]
            != {
                "row_profile": ROW_PROFILE,
                "row_profile_version": ROW_PROFILE_VERSION,
                "row_filter": "market_identity_in_admitted-markets.jsonl.gz",
                "source_assets": manifest["source_assets"],
                "admitted_mapping_sha256": manifest["admitted_mapping_sha256"],
            }
        ):
            raise ValueError("referenced bounded day is not importable authority")
        admitted, rejected = _strict_day_assets(day_release, manifest, day_index)
        recomputed_admitted, recomputed_rejected, recomputed_counts, recomputed_sources = (
            _assess_day(day_inventory, day_catalog, day_index, manifest["day"])
        )
        if (
            admitted != recomputed_admitted
            or rejected != recomputed_rejected
            or manifest["source_assets"] != recomputed_sources
            or any(manifest.get(name) != count for name, count in recomputed_counts.items())
        ):
            raise ValueError("bounded admission/rejection does not reproduce from pinned rows")
        if (
            ref["admitted_asset_id"]
            != next(
                a["id"]
                for a in day_release["assets"]
                if a["name"].endswith("--admitted-markets.jsonl.gz")
            )
            or ref["rejected_asset_id"]
            != next(
                a["id"]
                for a in day_release["assets"]
                if a["name"].endswith("--rejected-target-evidence.jsonl.gz")
            )
            or ref["admitted_target_markets"] != len(admitted)
            or ref["rejected_target_markets"] != len(rejected)
            or ref["admitted_observation_and_resolution_rows"]
            != manifest["admitted_observation_and_resolution_rows"]
            or ref["rejected_observation_and_resolution_rows"]
            != manifest["rejected_observation_and_resolution_rows"]
            or ref["admitted_mapping_sha256"] != manifest["admitted_mapping_sha256"]
            or ref["admitted_mapping_size"] != manifest["admitted_mapping_size"]
            or ref["rejected_evidence_sha256"] != manifest["rejected_evidence_sha256"]
            or ref["rejected_evidence_size"] != manifest["rejected_evidence_size"]
            or ref["inventory_wide_unresolved_not_admitted_count"]
            != manifest["inventory_wide_unresolved_not_admitted_count"]
        ):
            raise ValueError("bounded day/window reference mismatch")
        totals["admitted_target_markets"] += len(admitted)
        totals["rejected_target_markets"] += len(rejected)
    if (
        totals["admitted_target_markets"] != value["admitted_target_markets"]
        or totals["rejected_target_markets"] != value["rejected_target_markets"]
    ):
        raise ValueError("bounded window population totals mismatch")
    return {
        "verified": True,
        "research_import_allowed": True,
        "research_import_allowed_profile": PROFILE,
        "profile": PROFILE,
        "population_exhaustive": False,
        "continuity_between_observations_certified": False,
        "tag": tag,
        "sha256": digest,
        "release_id": release["id"],
        "days": names,
        "counts": dict(totals),
    }


def _update_current(tag: str, digest: str, value: dict[str, Any], release_id: int) -> None:
    if value["current_rollover_blocked_by_failed_newer_days"]:
        print(
            canonical(
                {
                    "current_reference_updated": False,
                    "reason": "failed_newer_day_preserves_current",
                }
            ).decode(),
            end="",
        )
        return
    pointer = canonical(
        {
            "schema": CURRENT_SCHEMA,
            **profile_fields(),
            "research_import_allowed": True,
            "research_import_allowed_profile": PROFILE,
            "window_tag": tag,
            "consumer_handoff_sha256": digest,
            "window_generation": value["generation"],
            "window_release_id": release_id,
            "included_certified_days": value["included_certified_days"],
            "inventory_generation": value["inventory_generation"],
            "inventory_release_id": value["inventory_release_id"],
            "updated_by_run_id": os.environ.get("GITHUB_RUN_ID"),
        }
    )
    branch = "bounded-current"
    ref = api("git/ref/heads/" + branch)
    if ref:
        commit = api("git/commits/" + ref["object"]["sha"])
        _, old = _load_current_blob(commit["tree"]["sha"])
        old_days = old.get("included_certified_days", [])
        if (
            old.get("schema") != CURRENT_SCHEMA
            or old.get("profile") != PROFILE
            or old.get("research_import_allowed_profile") != PROFILE
        ):
            raise ValueError("existing bounded current reference is incompatible")
        if old.get("inventory_release_id", -1) > value["inventory_release_id"]:
            return
        if not isinstance(old_days, list):
            raise ValueError("bounded current day set is malformed")
        if old_days == value["included_certified_days"]:
            if old.get("window_release_id", -1) >= release_id:
                return
        elif not _rolling_day_set_advances(old_days, value["included_certified_days"]):
            raise ValueError("bounded current reference would regress")
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
            "message": "Update bounded observed current window",
            "tree": tree["sha"],
            "parents": [parent],
        },
    )
    if ref:
        api("git/refs/heads/" + branch, "PATCH", {"sha": commit["sha"], "force": False})
    else:
        api("git/refs", "POST", {"ref": "refs/heads/" + branch, "sha": commit["sha"]})
    check = api("git/blobs/" + blob["sha"])
    if base64.b64decode(check["content"]) != pointer:
        raise ValueError("bounded current reference read-after-write failed")


def certify_batch(
    catalog_tag: str, catalog_sha: str, index_tag: str, index_sha: str, days: Iterable[str]
) -> None:
    for day in days:
        certify_day(catalog_tag, catalog_sha, index_tag, index_sha, day)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    certify = sub.add_parser("certify")
    batch = sub.add_parser("certify-batch")
    for item in (certify, batch):
        item.add_argument("--catalog-tag", required=True)
        item.add_argument("--catalog-sha", required=True)
        item.add_argument("--index-tag", required=True)
        item.add_argument("--index-sha", required=True)
    certify.add_argument("--day", required=True)
    batch.add_argument("--days", required=True)
    window = sub.add_parser("window")
    for name in ("catalog-tag", "catalog-sha", "index-tag", "index-sha"):
        window.add_argument("--" + name, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--tag", required=True)
    verify.add_argument("--sha256", required=True)
    verify.add_argument("--expected-profile", default=PROFILE)
    args = parser.parse_args()
    if args.command == "certify":
        certify_day(args.catalog_tag, args.catalog_sha, args.index_tag, args.index_sha, args.day)
    elif args.command == "certify-batch":
        days = json.loads(args.days)
        if not isinstance(days, list) or not all(isinstance(day, str) for day in days):
            raise ValueError("day batch must be a JSON string array")
        certify_batch(args.catalog_tag, args.catalog_sha, args.index_tag, args.index_sha, days)
    elif args.command == "window":
        publish_window(args.catalog_tag, args.catalog_sha, args.index_tag, args.index_sha)
    else:
        print(
            canonical(verify_window(args.tag, args.sha256, args.expected_profile)).decode(),
            end="",
        )


if __name__ == "__main__":
    main()
