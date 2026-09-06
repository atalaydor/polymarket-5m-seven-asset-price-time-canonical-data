"""Seal the reviewed current-generation native identity blocker checkpoint."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pflow.release import REPO, REPO_ID, api, current_commit, publish, read_asset, verify_release
from pflow.source import canonical, sha

TAG = "run-1-v3-inventory-identity-blocked-v0.5.0"
PRIOR = {
    "run-1-source-proof-blocked-v0.1.0": ("7c313b1e31f73cbba20465d0ed05d12b52a19bce", 383485962),
    "run-1-continuity-blocked-v0.2.0": ("2c0062d90f6839516859368542ba3167cc41eadc", 383513515),
    "run-1-observed-catalog-blocked-v0.3.0": (
        "2a95c0d32344a413e17cca863d9dad6ac80474bf",
        383529513,
    ),
    "run-1-historical-catalog-blocked-v0.4.0": (
        "2b51b798c9cd7d689b94957ba2c775e00f95e8d3",
        383556471,
    ),
}


def _metadata_release(tag: str, release_id: int, asset_id: int, digest: str, size: int) -> None:
    release = api("releases/" + str(release_id))
    if (
        release is None
        or release.get("tag_name") != tag
        or release.get("immutable") is not True
        or release.get("draft")
        or len(release.get("assets", [])) != 1
    ):
        raise ValueError("immutable dependency release mismatch")
    asset = release["assets"][0]
    if (
        asset.get("id") != asset_id
        or asset.get("digest") != "sha256:" + digest
        or asset.get("size") != size
        or not asset.get("name", "").startswith(digest + "--")
    ):
        raise ValueError("dependency asset metadata mismatch")


def _no_window_releases() -> bool:
    page = 1
    while True:
        releases = api(f"releases?per_page=100&page={page}")
        if not releases:
            return True
        if any(item["tag_name"].startswith("observed-window-v1-") for item in releases):
            return False
        page += 1


def main() -> None:
    commit = current_commit()
    if subprocess.check_output(["git", "status", "--porcelain"]):
        raise ValueError("clean committed checkpoint required")
    repository = json.loads(subprocess.check_output(["gh", "api", "repos/" + REPO]))
    if repository["id"] != REPO_ID or repository["full_name"] != REPO:
        raise ValueError("repository identity mismatch")
    if (
        api("immutable-releases")["enabled"] is not True
        or api("git/ref/heads/main")["object"]["sha"] != commit
    ):
        raise ValueError("remote commit/immutability mismatch")
    for tag, (old_commit, release_id) in PRIOR.items():
        ref = api("git/ref/tags/" + tag)
        release = api("releases/" + str(release_id))
        if (
            ref["object"]["type"] != "commit"
            or ref["object"]["sha"] != old_commit
            or release["immutable"] is not True
            or release["draft"]
            or release["tag_name"] != tag
        ):
            raise ValueError("prior checkpoint changed")

    checks = api("actions/workflows/check.yml/runs?per_page=20")["workflow_runs"]
    check = next(
        (
            run
            for run in checks
            if run["head_sha"] == commit and run["event"] == "push" and run["head_branch"] == "main"
        ),
        None,
    )
    if check is None or check["status"] != "completed":
        print(
            canonical(
                {
                    "ready": False,
                    "reason": "final_commit_CI_pending",
                    "run_id": check and check["id"],
                }
            ).decode()
        )
        return
    if check["conclusion"] != "success":
        raise ValueError("final commit CI failed")

    status_raw = subprocess.check_output(
        ["git", "show", commit + ":docs/inventory-identity-status.json"]
    )
    handoff_raw = subprocess.check_output(
        ["git", "show", commit + ":docs/inventory-identity-consumer-handoff.json"]
    )
    status = json.loads(status_raw)
    handoff = json.loads(handoff_raw)
    if (
        status["verdict"] != "BLOCKED_SOURCE_CAPABILITY"
        or status["research_import_allowed"] is not False
        or status["certified_days"]
        or status["current_window_generation"] is not None
        or status["accumulation_running"]
        or status["scheduled_accumulation"]
        or handoff["research_import_allowed"] is not False
        or handoff["included_certified_utc_days"]
    ):
        raise ValueError("blocked checkpoint carries research authority")
    shared_fields = (
        "profile",
        "profile_version",
        "certification_scope",
        "certification_scope_version",
        "research_import_allowed",
        "continuity_between_observations_certified",
        "historical_polymarket_listing_completeness_claimed",
        "current_window_generation",
        "accumulation_running",
        "scheduled_accumulation",
    )
    if (
        any(handoff.get(field) != status.get(field) for field in shared_fields)
        or handoff.get("status") != status["verdict"]
        or handoff.get("included_certified_utc_days") != status["certified_days"]
        or handoff.get("excluded_utc_days") != [day["day"] for day in status["excluded_days"]]
        or handoff.get("continuation_condition") != status["continuation_condition"]
    ):
        raise ValueError("consumer handoff/status authority mismatch")
    for name in ("inventory", "catalog", "data_index", "identity_gap"):
        handoff_pin = handoff["pinned_evidence"][name]
        status_pin = status[name]
        if any(handoff_pin.get(field) != status_pin.get(field) for field in handoff_pin):
            raise ValueError("consumer handoff evidence pin mismatch")

    workflow = subprocess.check_output(
        ["git", "show", commit + ":.github/workflows/observed-production.yml"]
    )
    if b"schedule:" in workflow or b"workflow_dispatch:" not in workflow:
        raise ValueError("blocked checkpoint must disable scheduled production")
    production_runs = api("actions/workflows/observed-production.yml/runs?per_page=20")[
        "workflow_runs"
    ]
    if any(run["status"] != "completed" for run in production_runs):
        raise ValueError("production workflow still active")
    production = api("actions/runs/34036701676")
    if (
        production["head_sha"] != "bc18255ce620507a4eda4ffa0b3ae73c7baf4225"
        or production["status"] != "completed"
        or production["conclusion"] != "failure"
    ):
        raise ValueError("production proof run changed")
    gap_run = api("actions/runs/34044977198")
    if (
        gap_run["head_sha"] != "9fc8aab3712fcf69a8131c4608423369d7ae8d73"
        or gap_run["status"] != "completed"
        or gap_run["conclusion"] != "success"
    ):
        raise ValueError("identity-gap verification run changed")
    if api("git/ref/heads/observed-current") is not None or not _no_window_releases():
        raise ValueError("unexpected current/window authority exists")

    for name in ("inventory", "catalog", "data_index"):
        item = status[name]
        _metadata_release(
            item["tag"], item["release_id"], item["asset_id"], item["sha256"], item["asset_size"]
        )
    gap = status["identity_gap"]
    gap_release = api("releases/" + str(gap["release_id"]))
    verify_release(gap_release)
    gap_asset = gap_release["assets"][0]
    gap_data = read_asset(gap_asset)
    gap_value = json.loads(gap_data)
    if (
        gap_release["tag_name"] != gap["tag"]
        or gap_asset["id"] != gap["asset_id"]
        or sha(gap_data) != gap["sha256"]
        or len(gap_data) != gap["asset_size"]
        or gap_value["unresolved_unique_condition_count"] != 170369
        or gap_value["unresolved_unique_condition_count"] != gap["unresolved_unique_conditions"]
        or gap_value["unresolved_condition_set_sha256"] != gap["unresolved_condition_set_sha256"]
        or gap_value["partitions_with_unresolved_condition_references"]
        != gap["partitions_affected"]
        or gap_value["partition_condition_reference_count"] != gap["summed_partition_references"]
        or gap_value["unresolved_conditionless_rows"]
        != {
            "best_bid_ask": gap["conditionless_best_bid_ask_rows"],
            "market_resolved": gap["conditionless_market_resolved_rows"],
        }
        or gap_value["inventory_generation"] != status["inventory"]["generation"]
        or gap_value["inventory_tag"] != status["inventory"]["tag"]
        or gap_value["inventory_sha256"] != status["inventory"]["sha256"]
        or gap_value["catalog_generation"] != status["catalog"]["generation"]
        or gap_value["catalog_tag"] != status["catalog"]["tag"]
        or gap_value["catalog_sha256"] != status["catalog"]["sha256"]
        or gap_value["data_index_generation"] != status["data_index"]["generation"]
        or gap_value["data_index_tag"] != status["data_index"]["tag"]
        or gap_value["data_index_sha256"] != status["data_index"]["sha256"]
        or gap_value["data_index_release_id"] != status["data_index"]["release_id"]
        or gap_value["partition_count"] != status["data_index"]["partition_count"]
        or gap_value["complete_expected_partition_set"]
        != status["data_index"]["complete_expected_partition_set"]
        or gap_value["target_membership_reconciled"] is not False
        or gap_value["target_membership_reconciled"]
        != status["data_index"]["target_membership_reconciled"]
        or gap_value["profile"] != status["profile"]
        or gap_value["profile_version"] != status["profile_version"]
        or gap_value["certification_scope"] != status["certification_scope"]
        or gap_value["certification_scope_version"] != status["certification_scope_version"]
        or not all(
            gap_value[field] is True
            for field in (
                "independently_verified_catalog_mapping_partition_closure",
                "independently_verified_expected_data_partition_set",
                "independently_recomputed_condition_partition_differences",
            )
        )
    ):
        raise ValueError("identity-gap evidence mismatch")

    for day in status["excluded_days"]:
        release = api("releases/" + str(day["release_id"]))
        verify_release(release)
        asset = release["assets"][0]
        day_data = read_asset(asset)
        day_manifest = json.loads(day_data)
        if (
            release["tag_name"] != "observed-day-v1-" + day["generation"]
            or asset["id"] != day["asset_id"]
            or sha(day_data) != day["manifest_sha256"]
            or day_manifest["day"] != day["day"]
            or day_manifest["generation"] != day["generation"]
            or day_manifest["market_count"] != day["market_count"]
            or day_manifest["observation_count"] != day["observation_count"]
            or day_manifest["certification_reasons"] != day["reasons"]
            or day_manifest["status"] != "EXCLUDED"
            or day_manifest["research_import_allowed"] is not False
        ):
            raise ValueError("excluded-day evidence mismatch")

    names = (
        "inventory-scope-policy-v1.json",
        "inventory-scope-v1.md",
        "observed-profile-policy-v1.json",
        "observed-profile-v1.md",
        "historical-catalog-capability-gap.md",
        "inventory-identity-capability-gap.md",
        "inventory-scope-source-review.md",
        "inventory-scope-implementation-review.md",
        "inventory-identity-status.json",
        "inventory-identity-consumer-handoff.json",
    )
    payloads = {
        name: subprocess.check_output(["git", "show", commit + ":docs/" + name]) for name in names
    }
    manifest: dict[str, Any] = {
        "schema": "pendulumflow-v3-inventory-identity-blocked-checkpoint.v1",
        "repository": REPO,
        "repository_id": REPO_ID,
        "commit": commit,
        "tag": TAG,
        "verdict": "BLOCKED_SOURCE_CAPABILITY",
        "profile": "PENDULUMFLOW_V3_OBSERVED",
        "profile_version": 1,
        "certification_scope": "PINNED_PUBLISHED_PENDULUMFLOW_V3_INVENTORY",
        "certification_scope_version": 1,
        "research_import_allowed": False,
        "certified_days": [],
        "current_window_generation": None,
        "accumulation_running": False,
        "scheduled_accumulation": False,
        "identity_gap_release": {
            key: gap[key] for key in ("tag", "release_id", "asset_id", "sha256", "asset_size")
        },
        "excluded_days": [day["day"] for day in status["excluded_days"]],
        "preserved_checkpoints": [
            {"tag": tag, "commit": value[0], "release_id": value[1]} for tag, value in PRIOR.items()
        ],
        "continuation_condition": status["continuation_condition"],
        "validation_run": {key: check[key] for key in ("id", "head_sha", "conclusion", "html_url")},
        "assets": [
            {"logical_name": name, "sha256": sha(data), "bytes": len(data)}
            for name, data in sorted(payloads.items())
        ],
    }
    payloads["checkpoint-manifest.json"] = canonical(manifest)
    release = publish(
        TAG, payloads, commit, "Run 1: pinned V3 inventory identity closure blocked (v0.5.0)"
    )
    ref = api("git/ref/tags/" + TAG)
    if ref["object"]["type"] != "commit" or ref["object"]["sha"] != commit:
        raise ValueError("sealed checkpoint tag mismatch")
    result = {
        "release_id": release["id"],
        "tag": TAG,
        "commit": commit,
        "immutable": release["immutable"],
        "manifest_sha256": sha(payloads["checkpoint-manifest.json"]),
        "assets": [
            {key: asset[key] for key in ("id", "name", "size", "digest")}
            for asset in release["assets"]
        ],
        "check_run_id": check["id"],
        "verified_all_checkpoint_asset_bytes_before_and_after_seal": True,
        "research_import_allowed": False,
    }
    Path("work/inventory-identity-checkpoint-verified.json").write_bytes(canonical(result))
    print(canonical(result).decode())


if __name__ == "__main__":
    main()
