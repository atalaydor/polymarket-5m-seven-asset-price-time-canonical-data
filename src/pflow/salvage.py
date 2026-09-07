"""Exhaustive certification of the retained bounded V3 generation.

This module never reads PendulumFlow.  It operates only on the immutable inventory,
catalog, data index, and canonical projection Releases produced by the accepted
historical acquisition.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from pflow.bounded_v1 import (
    DAY_PREFIX,
    PROFILE,
    _assess_day,
    _digest_from_name,
    _generation,
    _load_day_release,
    _load_dependencies,
    _output,
    _release_payload,
    _strict_day_assets,
    certify_day,
    profile_fields,
    publish_window,
    verify_window,
)
from pflow.production import _all_releases
from pflow.release import api, current_commit, publish
from pflow.source import canonical, sha

CATALOG_TAG = "observed-catalog-v1-305b1e9b81cea2a844f9d9aa48c4a1b70cc7d9dc0d53a7bee369c3423c79a9de"
CATALOG_SHA256 = "0e49bd231274d0389aa40bf72d1d99c4a033c719f27b936c882fd8887b74f639"
INVENTORY_TAG = "v3-inventory-v1-ead9a909a8c4fa5ad638a111040087609f6e7ac88c95b3f4596786810586bcc0"
INDEX_TAG = (
    "observed-data-index-v1-24254f9fc394e161f916285cd8ddbac6644cdb7de1f7524d2f9c323b0d38070f"
)
INDEX_SHA256 = "85c6f7afeb6c19cd8ed891564f04e1adcd5da1058f9e9c4ee30995bc46cc780f"
EXPECTED_PARTITIONS = 116
EXPECTED_HOURS = 460
EXPECTED_SOURCE_BYTES = 40_488_664_657
SALVAGE_SCHEMA = "pendulumflow-v3-observed-bounded-salvage.v1"
SALVAGE_PREFIX = "bounded-salvage-v1-"
SALVAGE_DAY_ELIGIBILITY_RULE = "past UTC day with all 24 pinned V3 receipt-hour objects present"
PARTIAL_DAY_DISPOSITION = "OUTSIDE_THIS_SALVAGE_PASS_NOT_PROVEN_NON_CERTIFIABLE"
RECOVERED_RUN_ID = 34054404836
RECOVERY_DISPOSITION = (
    "retained 179 successful jobs from the later-generation run; its failed unsealed "
    "partial-day data shard was not retried or admitted into the accepted retained "
    "historical generation"
)


def coverage_summary(inventory: dict[str, Any]) -> dict[str, Any]:
    """Describe exact receipt-hour coverage and identify only full UTC days."""
    hours = [item["hour"] for item in inventory["hours"]]
    if hours != sorted(set(hours)):
        raise ValueError("inventory hours are not a unique sorted set")
    hour_set = set(hours)
    parsed = {datetime.strptime(hour, "%Y-%m-%d/%H").replace(tzinfo=UTC): hour for hour in hours}
    first = min(parsed)
    last = max(parsed)
    complete: list[str] = []
    partial: list[dict[str, Any]] = []
    day = first.date()
    while day <= last.date():
        expected = [f"{day.isoformat()}/{hour:02d}" for hour in range(24)]
        present = [hour for hour in expected if hour in hour_set]
        missing = [hour for hour in expected if hour not in hour_set]
        if not missing:
            complete.append(day.isoformat())
        elif present:
            partial.append(
                {
                    "day": day.isoformat(),
                    "present_hour_count": len(present),
                    "first_present_hour": present[0],
                    "last_present_hour": present[-1],
                    "missing_hours": missing,
                }
            )
        day += timedelta(days=1)
    return {
        "salvage_day_eligibility_rule": SALVAGE_DAY_ELIGIBILITY_RULE,
        "partial_utc_day_disposition": PARTIAL_DAY_DISPOSITION,
        "first_hour": hours[0],
        "last_hour": hours[-1],
        "published_receipt_hours": len(hours),
        "advertised_full_object_bytes": sum(
            item["manifest"]["bytes"] for item in inventory["hours"]
        ),
        "complete_utc_days": complete,
        "partial_utc_days": partial,
    }


def _day_batches(days: list[str], width: int = 3) -> list[dict[str, list[str]]]:
    if width < 1:
        raise ValueError("batch width must be positive")
    return [{"days": days[start : start + width]} for start in range(0, len(days), width)]


def _terminal_days(
    complete_days: Iterable[str], catalog_tag: str, catalog_sha: str, index_tag: str, index_sha: str
) -> dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    eligible = set(complete_days)
    latest: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {}
    for release in _all_releases():
        if (
            not str(release.get("tag_name", "")).startswith(DAY_PREFIX)
            or not release.get("immutable")
            or release.get("draft")
            or release.get("prerelease")
        ):
            continue
        manifest_asset, manifest = _load_day_release(release)
        if (
            manifest["day"] not in eligible
            or manifest["catalog_tag"] != catalog_tag
            or manifest["catalog_sha256"] != catalog_sha
            or manifest["data_index_tag"] != index_tag
            or manifest["data_index_sha256"] != index_sha
        ):
            continue
        prior = latest.get(manifest["day"])
        if prior is None or release["id"] > prior[0]["id"]:
            latest[manifest["day"]] = (release, manifest_asset, manifest)
    return latest


def _load_retained() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    inventory, catalog, index = _load_dependencies(
        CATALOG_TAG, CATALOG_SHA256, INDEX_TAG, INDEX_SHA256
    )
    coverage = coverage_summary(inventory)
    if (
        coverage["published_receipt_hours"] != EXPECTED_HOURS
        or len(index["partitions"]) != EXPECTED_PARTITIONS
        or index.get("measurements", {}).get("downloaded_bytes") != EXPECTED_SOURCE_BYTES
    ):
        raise ValueError("retained historical generation differs from accepted acquisition")
    return inventory, catalog, index, coverage


def plan() -> dict[str, Any]:
    _, _, _, coverage = _load_retained()
    complete = coverage["complete_utc_days"]
    terminal = _terminal_days(complete, CATALOG_TAG, CATALOG_SHA256, INDEX_TAG, INDEX_SHA256)
    remaining = [day for day in complete if day not in terminal]
    batches = _day_batches(remaining)
    result = {
        "schema": "pendulumflow-v3-observed-bounded-salvage-plan.v1",
        **profile_fields(),
        "coverage": coverage,
        "retained_partitions": EXPECTED_PARTITIONS,
        "v3_historical_source_reacquisition_bytes": 0,
        "terminal_days_before_run": sorted(terminal),
        "remaining_days": remaining,
        "day_batches": batches,
    }
    _output("has_work", bool(remaining))
    _output("day_batches", batches or [{"days": []}])
    print(canonical(result).decode(), end="")
    return result


def certify_missing_days(days: list[str]) -> None:
    """Reconcile each day immediately so retries preserve completed siblings."""
    existing = _terminal_days(days, CATALOG_TAG, CATALOG_SHA256, INDEX_TAG, INDEX_SHA256)
    for day in days:
        if day in existing:
            print(canonical({"day": day, "terminal_checkpoint_reused": True}).decode(), end="")
            continue
        certify_day(CATALOG_TAG, CATALOG_SHA256, INDEX_TAG, INDEX_SHA256, day)


def _terminal_refs(
    terminal: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> list[dict[str, Any]]:
    refs = []
    for day, (release, asset, manifest) in sorted(terminal.items()):
        refs.append(
            {
                "day": day,
                "terminal_status": (
                    "CERTIFIED" if manifest["status"] == "CERTIFIED" else "PROVEN_NON_CERTIFIABLE"
                ),
                "reasons": manifest["certification_reasons"],
                "generation": manifest["generation"],
                "tag": release["tag_name"],
                "release_id": release["id"],
                "manifest_asset_id": asset["id"],
                "manifest_sha256": _digest_from_name(asset),
                "admitted_target_markets": manifest["admitted_target_markets"],
                "rejected_target_markets": manifest["rejected_target_markets"],
                "admitted_observation_and_resolution_rows": manifest[
                    "admitted_observation_and_resolution_rows"
                ],
                "rejected_observation_and_resolution_rows": manifest[
                    "rejected_observation_and_resolution_rows"
                ],
            }
        )
    return refs


def finalize() -> dict[str, Any]:
    _, _, _, coverage = _load_retained()
    complete = coverage["complete_utc_days"]
    terminal = _terminal_days(complete, CATALOG_TAG, CATALOG_SHA256, INDEX_TAG, INDEX_SHA256)
    missing = sorted(set(complete) - set(terminal))
    if missing:
        raise ValueError("complete acquired days lack terminal assessment: " + ",".join(missing))
    certified = sorted(
        day for day, (_, _, manifest) in terminal.items() if manifest["status"] == "CERTIFIED"
    )
    expected_window = certified if len(certified) < 30 else certified[-30:]
    window = publish_window(
        CATALOG_TAG,
        CATALOG_SHA256,
        INDEX_TAG,
        INDEX_SHA256,
        exact_dependency_days=set(complete),
    )
    if window["included_certified_days"] != expected_window:
        raise ValueError("published window is not maximum across eligible full-receipt days")
    window_tag = "bounded-window-v1-" + window["generation"]
    window_payload_sha = sha(canonical(window))
    window_release = api("releases/tags/" + window_tag)
    if window_release is None or not window_release.get("immutable"):
        raise ValueError("published maximum window is unavailable or mutable")
    refs = _terminal_refs(terminal)
    totals: Counter[str] = Counter()
    for ref in refs:
        totals["admitted_target_markets"] += ref["admitted_target_markets"]
        totals["rejected_target_markets"] += ref["rejected_target_markets"]
    ledger = {
        "schema": SALVAGE_SCHEMA,
        **profile_fields(),
        "repository": "atalaydor/polymarket-5m-seven-asset-price-time-canonical-data",
        "coverage": coverage,
        "retained_partitions": EXPECTED_PARTITIONS,
        "authenticated_partition_report_source_bytes": EXPECTED_SOURCE_BYTES,
        "inventory_tag": INVENTORY_TAG,
        "catalog_tag": CATALOG_TAG,
        "catalog_sha256": CATALOG_SHA256,
        "data_index_tag": INDEX_TAG,
        "data_index_sha256": INDEX_SHA256,
        "complete_assessable_day_count": len(complete),
        "terminal_days": refs,
        "certified_days": certified,
        "proven_non_certifiable_days": [
            {"day": ref["day"], "reasons": ref["reasons"]}
            for ref in refs
            if ref["terminal_status"] == "PROVEN_NON_CERTIFIABLE"
        ],
        "admitted_target_markets": totals["admitted_target_markets"],
        "rejected_target_markets": totals["rejected_target_markets"],
        "window_tag": window_tag,
        "window_release_id": window_release["id"],
        "consumer_handoff_sha256": window_payload_sha,
        "research_import_allowed": True,
        "v3_historical_source_reacquisition_bytes": 0,
        "recovered_run_id": RECOVERED_RUN_ID,
        "recovery_disposition": RECOVERY_DISPOSITION,
        "implementation_commit": current_commit(),
    }
    ledger["generation"] = sha(canonical(ledger))
    payload = canonical(ledger)
    tag = SALVAGE_PREFIX + ledger["generation"]
    release = publish(
        tag,
        {"salvage-ledger.json": payload},
        current_commit(),
        "Exhaustive retained V3 bounded salvage",
        "Terminal assessment of every eligible full-receipt UTC day in the retained generation.",
    )
    _output("salvage_tag", tag)
    _output("salvage_sha256", sha(payload))
    _output("window_tag", window_tag)
    _output("consumer_handoff_sha256", window_payload_sha)
    print(canonical({"release_id": release["id"], "certified_days": certified}).decode())
    return ledger


def verify_salvage(tag: str, digest: str, window_tag: str, handoff_sha: str) -> dict[str, Any]:
    if not tag.startswith(SALVAGE_PREFIX):
        raise ValueError("exact bounded salvage tag required")
    release = api("releases/tags/" + tag)
    if release is None or not release.get("immutable") or len(release.get("assets", [])) != 1:
        raise ValueError("immutable bounded salvage release unavailable")
    asset, raw = _release_payload(release, "salvage-ledger.json")
    if sha(raw) != digest or _digest_from_name(asset) != digest:
        raise ValueError("salvage ledger digest mismatch")
    ledger = json.loads(raw)
    required_fields = {
        "schema",
        *profile_fields(),
        "repository",
        "coverage",
        "retained_partitions",
        "authenticated_partition_report_source_bytes",
        "inventory_tag",
        "catalog_tag",
        "catalog_sha256",
        "data_index_tag",
        "data_index_sha256",
        "complete_assessable_day_count",
        "terminal_days",
        "certified_days",
        "proven_non_certifiable_days",
        "admitted_target_markets",
        "rejected_target_markets",
        "window_tag",
        "window_release_id",
        "consumer_handoff_sha256",
        "research_import_allowed",
        "v3_historical_source_reacquisition_bytes",
        "recovered_run_id",
        "recovery_disposition",
        "implementation_commit",
        "generation",
    }
    if (
        set(ledger) != required_fields
        or ledger.get("schema") != SALVAGE_SCHEMA
        or any(ledger.get(key) != value for key, value in profile_fields().items())
        or _generation(ledger) != tag.removeprefix(SALVAGE_PREFIX)
        or ledger.get("implementation_commit") != release.get("target_commitish")
        or ledger.get("window_tag") != window_tag
        or ledger.get("consumer_handoff_sha256") != handoff_sha
        or ledger.get("research_import_allowed") is not True
        or ledger.get("v3_historical_source_reacquisition_bytes") != 0
        or ledger.get("inventory_tag") != INVENTORY_TAG
        or ledger.get("catalog_tag") != CATALOG_TAG
        or ledger.get("catalog_sha256") != CATALOG_SHA256
        or ledger.get("data_index_tag") != INDEX_TAG
        or ledger.get("data_index_sha256") != INDEX_SHA256
        or ledger.get("authenticated_partition_report_source_bytes") != EXPECTED_SOURCE_BYTES
        or ledger.get("recovered_run_id") != RECOVERED_RUN_ID
        or ledger.get("recovery_disposition") != RECOVERY_DISPOSITION
    ):
        raise ValueError("salvage ledger contract invalid")
    inventory, catalog, index, coverage = _load_retained()
    if ledger.get("coverage") != coverage or ledger.get("retained_partitions") != len(
        index["partitions"]
    ):
        raise ValueError("salvage coverage does not reproduce")
    refs = ledger.get("terminal_days")
    if not isinstance(refs, list):
        raise ValueError("salvage terminal-day ledger invalid")
    terminal: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {}
    for ref in refs:
        if not isinstance(ref, dict) or ref.get("day") in terminal:
            raise ValueError("salvage terminal-day ledger invalid")
        day_release = api("releases/" + str(ref.get("release_id")))
        if day_release is None or day_release.get("tag_name") != ref.get("tag"):
            raise ValueError("salvage terminal release unavailable")
        manifest_asset, manifest = _load_day_release(day_release)
        expected_ref = _terminal_refs({manifest["day"]: (day_release, manifest_asset, manifest)})[0]
        if (
            ref != expected_ref
            or manifest["day"] != ref.get("day")
            or manifest["catalog_tag"] != CATALOG_TAG
            or manifest["catalog_sha256"] != CATALOG_SHA256
            or manifest["data_index_tag"] != INDEX_TAG
            or manifest["data_index_sha256"] != INDEX_SHA256
        ):
            raise ValueError("salvage terminal release binding invalid")
        terminal[manifest["day"]] = (day_release, manifest_asset, manifest)
    if set(terminal) != set(coverage["complete_utc_days"]):
        raise ValueError("salvage terminal-day closure invalid")
    certified = sorted(
        day for day, (_, _, manifest) in terminal.items() if manifest["status"] == "CERTIFIED"
    )
    excluded = [
        {"day": day, "reasons": manifest["certification_reasons"]}
        for day, (_, _, manifest) in sorted(terminal.items())
        if manifest["status"] == "EXCLUDED"
    ]
    totals: Counter[str] = Counter()
    for _, _, manifest in terminal.values():
        totals["admitted_target_markets"] += manifest["admitted_target_markets"]
        totals["rejected_target_markets"] += manifest["rejected_target_markets"]
    window_release = api("releases/tags/" + window_tag)
    if (
        ledger.get("complete_assessable_day_count") != len(terminal)
        or ledger.get("certified_days") != certified
        or ledger.get("proven_non_certifiable_days") != excluded
        or ledger.get("admitted_target_markets") != totals["admitted_target_markets"]
        or ledger.get("rejected_target_markets") != totals["rejected_target_markets"]
        or window_release is None
        or not window_release.get("immutable")
        or ledger.get("window_release_id") != window_release.get("id")
    ):
        raise ValueError("salvage aggregate or window binding invalid")
    for day, (_, _, manifest) in terminal.items():
        if manifest["status"] == "EXCLUDED":
            day_release = terminal[day][0]
            admitted, rejected = _strict_day_assets(day_release, manifest, index)
            recomputed_admitted, recomputed_rejected, recomputed_counts, sources = _assess_day(
                inventory, catalog, index, day
            )
            if (
                admitted
                or recomputed_admitted
                or admitted != recomputed_admitted
                or rejected != recomputed_rejected
                or manifest["source_assets"] != sources
                or any(manifest.get(name) != count for name, count in recomputed_counts.items())
            ):
                raise ValueError("non-certifiable day does not reproduce from pinned rows")
    verified = verify_window(window_tag, handoff_sha)
    expected = certified if len(certified) < 30 else certified[-30:]
    _, window_raw = _release_payload(window_release, "consumer-handoff.json")
    window_value = json.loads(window_raw)
    window_refs = {item["day"]: item for item in window_value["day_generations"]}
    for day in expected:
        day_release, _, manifest = terminal[day]
        ref = window_refs.get(day)
        if (
            ref is None
            or ref.get("tag") != day_release["tag_name"]
            or ref.get("release_id") != day_release["id"]
            or ref.get("generation") != manifest["generation"]
        ):
            raise ValueError("window does not pin exact terminal certified generation")
    if (
        verified["days"] != expected
        or sorted(window_refs) != expected
        or ledger.get("certified_days") != certified
    ):
        raise ValueError("maximum certified window closure invalid")
    return {
        "verified": True,
        "profile": PROFILE,
        "salvage_tag": tag,
        "window_tag": window_tag,
        "complete_assessable_days": len(terminal),
        "certified_days": len(certified),
        "research_import_allowed": True,
        "v3_historical_source_reacquisition_bytes": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    batch = sub.add_parser("certify-batch")
    batch.add_argument("--days", required=True)
    sub.add_parser("finalize")
    verify = sub.add_parser("verify")
    verify.add_argument("--tag", required=True)
    verify.add_argument("--sha256", required=True)
    verify.add_argument("--window-tag", required=True)
    verify.add_argument("--handoff-sha256", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        plan()
    elif args.command == "certify-batch":
        days = json.loads(args.days)
        if not isinstance(days, list) or not all(isinstance(day, str) for day in days):
            raise ValueError("day batch must be a JSON string array")
        certify_missing_days(days)
    elif args.command == "finalize":
        finalize()
    else:
        print(
            canonical(
                verify_salvage(args.tag, args.sha256, args.window_tag, args.handoff_sha256)
            ).decode(),
            end="",
        )


if __name__ == "__main__":
    main()
