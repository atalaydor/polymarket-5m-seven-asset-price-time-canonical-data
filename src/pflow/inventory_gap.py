"""Compact, immutable evidence for unresolved native V3 condition identities."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from pflow.observed_v1 import (
    CERTIFICATION_SCOPE,
    CERTIFICATION_SCOPE_VERSION,
    PROFILE,
    PROFILE_VERSION,
    iter_jsonl_gzip,
)
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import canonical, sha

SCHEMA = "pendulumflow-v3-inventory-identity-gap.v1"
DATA_INDEX_SCHEMA = "pendulumflow-v3-observed-data-index.v1"


def summarize_index(value: dict[str, Any]) -> dict[str, Any]:
    generation = value.get("generation")
    base = {key: item for key, item in value.items() if key != "generation"}
    if value.get("schema") != DATA_INDEX_SCHEMA or generation != sha(canonical(base)):
        raise ValueError("data index schema/generation mismatch")
    unresolved = value.get("unresolved_condition_references")
    conditionless = value.get("unresolved_conditionless_rows")
    partitions = value.get("partitions")
    if not isinstance(unresolved, list) or not isinstance(conditionless, dict):
        raise ValueError("data index lacks unresolved identity accounting")
    if not isinstance(partitions, list) or not all(isinstance(row, dict) for row in partitions):
        raise ValueError("data index partition inventory malformed")
    if unresolved != sorted(set(unresolved)) or not all(
        isinstance(item, str) for item in unresolved
    ):
        raise ValueError("unresolved condition inventory is not a sorted unique string set")
    partition_sets: list[set[str]] = []
    for row in partitions:
        refs = row.get("unresolved_condition_references")
        if not isinstance(refs, list) or refs != sorted(set(refs)):
            raise ValueError("partition unresolved condition accounting malformed")
        partition_sets.append(set(refs))
    union = set().union(*partition_sets) if partition_sets else set()
    if union != set(unresolved):
        raise ValueError("global unresolved identity set differs from partition union")
    counts = {str(key): int(number) for key, number in conditionless.items()}
    if any(number < 0 for number in counts.values()):
        raise ValueError("negative conditionless row count")
    measurements = value.get("measurements", {})
    if not isinstance(measurements, dict):
        raise ValueError("data index measurements malformed")
    if (
        value.get("profile") != PROFILE
        or value.get("profile_version") != PROFILE_VERSION
        or value.get("certification_scope") != CERTIFICATION_SCOPE
        or value.get("certification_scope_version") != CERTIFICATION_SCOPE_VERSION
    ):
        raise ValueError("data index profile/scope mismatch")
    expected_reconciled = not unresolved and not sum(counts.values())
    if value.get("complete_expected_partition_set") is not True:
        raise ValueError("incomplete partition set cannot prove this capability gap")
    if value.get("target_membership_reconciled") is not expected_reconciled:
        raise ValueError("data index membership closure flag is inconsistent")
    if expected_reconciled:
        raise ValueError("no unresolved native condition identity exists")
    if not unresolved:
        raise ValueError("this report requires unresolved condition IDs")
    return {
        "schema": SCHEMA,
        "verdict": "BLOCKED_SOURCE_CAPABILITY",
        "profile": value["profile"],
        "profile_version": value["profile_version"],
        "certification_scope": value.get("certification_scope"),
        "certification_scope_version": value.get("certification_scope_version"),
        "inventory_generation": value.get("inventory_generation"),
        "inventory_tag": value.get("inventory_tag"),
        "inventory_sha256": value.get("inventory_sha256"),
        "catalog_generation": value.get("catalog_generation"),
        "catalog_tag": value.get("catalog_tag"),
        "catalog_sha256": value.get("catalog_sha256"),
        "data_index_generation": value.get("generation"),
        "complete_expected_partition_set": value.get("complete_expected_partition_set"),
        "target_membership_reconciled": value.get("target_membership_reconciled"),
        "partition_count": len(partitions),
        "partitions_with_unresolved_condition_references": sum(
            bool(items) for items in partition_sets
        ),
        "partition_condition_reference_count": sum(len(items) for items in partition_sets),
        "unresolved_unique_condition_count": len(unresolved),
        "unresolved_condition_set_sha256": sha(canonical(unresolved)),
        "unresolved_condition_first_five": unresolved[:5],
        "unresolved_condition_last_five": unresolved[-5:],
        "unresolved_conditionless_rows": counts,
        "downloaded_source_bytes": int(measurements.get("downloaded_bytes", 0)),
        "network_seconds_us": int(measurements.get("network_seconds_us", 0)),
        "wall_seconds_us": int(measurements.get("wall_seconds_us", 0)),
        "research_import_allowed": False,
        "certified_days": [],
        "current_window_generation": None,
        "limitation": (
            "best_bid_ask and/or market_resolved rows reference condition IDs for which the "
            "complete pinned native V3 inventory generation contains no new_market identity "
            "record; its currently published native evidence therefore cannot determine whether "
            "those conditions are in-scope targets"
        ),
        "continuation_condition": (
            "A content-bound native V3 identity/lifecycle mapping for every unresolved condition "
            "ID, or an evidence-backed native exclusion/day-bound for each relevant unresolved "
            "ID, must make the complete pinned inventory projection decidable; newly published "
            "mapping evidence requires a new pinned inventory generation."
        ),
    }


def _load_index(tag: str, expected_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    release = api("releases/tags/" + tag)
    if release is None or release.get("tag_name") != tag:
        raise ValueError("exact data-index release not found")
    verify_release(release)
    matches = [asset for asset in release["assets"] if asset["name"].endswith("--data-index.json")]
    if len(matches) != 1:
        raise ValueError("exactly one data-index asset required")
    data = read_asset(matches[0])
    if sha(data) != expected_sha or not matches[0]["name"].startswith(expected_sha + "--"):
        raise ValueError("data-index content pin mismatch")
    value = json.loads(data)
    if tag != "observed-data-index-v1-" + value.get("generation", ""):
        raise ValueError("data-index generation/tag mismatch")
    return dict(release), value


def _load_json_release(tag: str, expected_sha: str, suffix: str) -> dict[str, Any]:
    release = api("releases/tags/" + tag)
    if release is None or release.get("tag_name") != tag:
        raise ValueError("exact dependency release not found")
    verify_release(release)
    matches = [asset for asset in release["assets"] if asset["name"].endswith("--" + suffix)]
    if len(matches) != 1:
        raise ValueError("dependency release asset inventory mismatch")
    data = read_asset(matches[0])
    if sha(data) != expected_sha:
        raise ValueError("dependency release content pin mismatch")
    return dict(json.loads(data))


def verify_condition_closure(value: dict[str, Any]) -> None:
    catalog = _load_json_release(value["catalog_tag"], value["catalog_sha256"], "catalog.json")
    if catalog.get("generation") != value["catalog_generation"]:
        raise ValueError("catalog generation mismatch")
    classified = {row["market"] for row in catalog["source_condition_classifications"]}
    seen_partitions: set[str] = set()
    for part in value["partitions"]:
        source_partition = part.get("source_partition")
        if not isinstance(source_partition, str) or not re.fullmatch(
            r"[0-9a-f]{64}", source_partition
        ):
            raise ValueError("source partition identity malformed")
        if source_partition in seen_partitions:
            raise ValueError("duplicate source partition")
        seen_partitions.add(source_partition)
        tag = "observed-conditions-v1-" + source_partition
        release = api("releases/tags/" + tag)
        if release is None or release.get("tag_name") != tag:
            raise ValueError("encountered-condition release missing")
        verify_release(release)
        matches = [
            asset for asset in release["assets"] if asset["name"].endswith("--conditions.jsonl.gz")
        ]
        if len(matches) != 1:
            raise ValueError("encountered-condition asset inventory mismatch")
        encountered_data = read_asset(matches[0])
        encountered = {row["market"] for row in iter_jsonl_gzip(encountered_data)}
        expected = sorted(encountered - classified)
        if expected != part["unresolved_condition_references"]:
            raise ValueError("partition identity closure differs from immutable inputs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-tag", required=True)
    parser.add_argument("--index-sha256", required=True)
    args = parser.parse_args()
    index_release, value = _load_index(args.index_tag, args.index_sha256)
    summary = summarize_index(value)
    verify_condition_closure(value)
    summary["independently_recomputed_condition_partition_closure"] = True
    summary["data_index_tag"] = args.index_tag
    summary["data_index_sha256"] = args.index_sha256
    summary["data_index_release_id"] = index_release["id"]
    payload = canonical(summary)
    tag = "inventory-identity-gap-v1-" + sha(payload)
    release = publish(
        tag,
        {"inventory-identity-gap.json": payload},
        current_commit(),
        "Native V3 unresolved condition identity evidence",
        "Immutable source-capability evidence only. No certified research authority.",
    )
    print(
        canonical(
            {
                "tag": tag,
                "release_id": release["id"],
                "asset_id": release["assets"][0]["id"],
                "sha256": sha(payload),
                "size": len(payload),
                **summary,
            }
        ).decode()
    )


if __name__ == "__main__":
    main()
