"""Target-first certification over the already-sealed V3 observed projection."""

from __future__ import annotations

import argparse
import base64
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from pflow.catalog_targets import DAYS, SERIES, interval
from pflow.catalog_targets import validate as validate_target_report
from pflow.observed_v1 import (
    MAPPING_SCHEMA,
    OBSERVATION_SCHEMA,
    PROFILE,
    PROFILE_VERSION,
    RESOLUTION_SCHEMA,
    TRANSFORM,
    iter_jsonl_gzip,
    jsonl_gzip,
    select_window,
    validate_mapping,
    validate_observation,
    validate_resolution,
)
from pflow.production import (
    _all_releases,
    _load_current_blob,
    _resolution_evidence,
    _rolling_day_set_advances,
)
from pflow.production_consumer import (
    _asset,
    _json_release,
    _release,
    _verify_inventory_catalog,
    _verify_source_proofs,
)
from pflow.release import api, current_commit, publish, read_asset
from pflow.source import canonical, sha

TARGET_SCOPE = "PINNED_FIRST_PARTY_TARGET_SERIES_JOINED_TO_EXISTING_V3"
TARGET_SCOPE_VERSION = 1
TARGET_CATALOG_SCHEMA = "polymarket-seven-asset-5m-target-catalog.v1"
TARGET_DAY_SCHEMA = "pendulumflow-v3-observed-target-certified-day.v1"
TARGET_WINDOW_SCHEMA = "pendulumflow-v3-observed-target-window.v1"

V3_CATALOG_TAG = (
    "observed-catalog-v1-305b1e9b81cea2a844f9d9aa48c4a1b70cc7d9dc0d53a7bee369c3423c79a9de"
)
V3_CATALOG_SHA = "0e49bd231274d0389aa40bf72d1d99c4a033c719f27b936c882fd8887b74f639"
V3_INDEX_TAG = (
    "observed-data-index-v1-24254f9fc394e161f916285cd8ddbac6644cdb7de1f7524d2f9c323b0d38070f"
)
V3_INDEX_SHA = "85c6f7afeb6c19cd8ed891564f04e1adcd5da1058f9e9c4ee30995bc46cc780f"
V3_INDEX_RELEASE_ID = 383639220
UNRESOLVED_SET_SHA = "11c7ae4f3732a232dbb07c183b73a7b7fa655a7e52af211231514020bfea3984"

TARGET_PINS: dict[str, dict[str, Any]] = {
    "BTC": {
        "tag": "catalog-targets-537a1de71f435bed033ac1343f38ec524b1f5b1dd5e151a9f1dff6b71f0f8786",
        "release_id": 383548088,
        "report_sha256": "5cf3abbcbbcb8e537d00c32735cfcb3c273062a561e8acf46e852c73e58874b9",
    },
    "ETH": {
        "tag": "catalog-targets-cec376a71017f65590a0eacbcc4ae680260f99622bfddd1651f1bf57b5689253",
        "release_id": 383548111,
        "report_sha256": "642a56cb6dc1ed2a82ec0619b98e12a1010800ddb6cd324506c9b29c35166022",
    },
    "SOL": {
        "tag": "catalog-targets-60a158da35341f65e9dddad274ce9e6921557a91480b7ef73d10063cbc9f2876",
        "release_id": 383548184,
        "report_sha256": "e302dc2b9b3d6e99c12425167d0f0753320d4651ee2c14b816a1a7d645a3c142",
    },
    "XRP": {
        "tag": "catalog-targets-fc9fd8de84370a604c6dbf46f11ee6c8562370449c3dbcc240f21165ce13c058",
        "release_id": 383548224,
        "report_sha256": "608239b2e3b98853fe804921411f5cb0b622bedc420c3fa697c438f4be51544d",
    },
    "DOGE": {
        "tag": "catalog-targets-35daa283d99bbc146639840f0b6303c77fbe219ad3b8434b0c179ec314ba7bd0",
        "release_id": 383548283,
        "report_sha256": "4d68177a622b63b28a91bdea1ad7f7c5278ccce4110a2f8dbf37aebe5556116c",
    },
    "BNB": {
        "tag": "catalog-targets-413d5ddc6e9f25197acdd34f03c5e13eed543983ed7eac103d439f2dfca3f272",
        "release_id": 383548320,
        "report_sha256": "0373dcbd1d83db8a7aef7ca91de271aab1e78cb610fe6bf96bcd40370f880fdc",
    },
    "HYPE": {
        "tag": "catalog-targets-22b534ca89cfc8cfebd3e998e491c523438b7004ef3c4ec6a237524b99bdb6f7",
        "release_id": 383548375,
        "report_sha256": "554622969833cf73965dbb6771833b9fe8b5765bc60b166f27a2b82add12dc16",
    },
}


def scope_fields() -> dict[str, Any]:
    return {
        "profile": PROFILE,
        "profile_version": PROFILE_VERSION,
        "certification_scope": TARGET_SCOPE,
        "certification_scope_version": TARGET_SCOPE_VERSION,
        "continuity_between_observations_certified": False,
        "historical_deleted_listing_completeness_claimed": False,
    }


def _output(name: str, value: Any) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={rendered}\n")
    print(canonical({name: value}).decode(), end="")


def _generation(value: dict[str, Any]) -> str:
    core = {key: item for key, item in value.items() if key != "generation"}
    expected = sha(canonical(core))
    if value.get("generation") != expected:
        raise ValueError("content generation mismatch")
    return expected


def _target_source(asset: str) -> tuple[dict[str, Any], dict[str, Any]]:
    pin = TARGET_PINS[asset]
    release = _release(pin["tag"])
    if (
        release["id"] != pin["release_id"]
        or release["target_commitish"] != "c4df60f9bfaa2ae1ea4f5d8838c33f73d6025e0b"
    ):
        raise ValueError("first-party target release identity mismatch")
    report_asset, raw = _asset(release, "target-series.json")
    if sha(raw) != pin["report_sha256"] or report_asset["size"] != len(raw):
        raise ValueError("first-party target report digest mismatch")
    report = json.loads(raw)
    validate_target_report(report, asset, report["commit"])
    return report, {
        "asset": asset,
        "series_id": SERIES[asset],
        "tag": pin["tag"],
        "release_id": release["id"],
        "asset_id": report_asset["id"],
        "sha256": sha(raw),
        "size": len(raw),
        "workflow_run_id": report["evidence"]["workflow_run_id"],
        "observed_at_first": report["evidence"]["requests"][0]["observed_at"],
        "observed_at_last": report["evidence"]["requests"][-1]["observed_at"],
    }


def _day_entries(report: dict[str, Any], asset: str, day: str) -> list[dict[str, Any]]:
    begin = datetime.fromisoformat(day).replace(tzinfo=UTC)
    begin_us = int(begin.timestamp()) * 1_000_000
    end_us = begin_us + 86_400_000_000
    selected_scans = [
        scan
        for scan in report["evidence"]["scans"]
        if scan["parameters"].get("end_date_min") == day + "T00:00:00Z"
    ]
    if len(selected_scans) != 2 or {s["parameters"]["closed"] for s in selected_scans} != {
        "true",
        "false",
    }:
        raise ValueError("day does not have both first-party lifecycle enumerations")
    values: list[dict[str, Any]] = []
    for scan in selected_scans:
        if scan["error"] is not None or not scan["terminal_observed"] or scan["duplicate_ids"]:
            raise ValueError("first-party target day enumeration did not close")
        for row in scan["rows"]:
            item = interval(row, asset)
            if item["start_us"] is None or not begin_us <= item["start_us"] < end_us:
                continue
            if item["errors"]:
                raise ValueError("first-party target identity is ambiguous")
            orientation = dict(zip(item["outcomes"], item["tokens"], strict=True))
            values.append(
                {
                    "asset": asset,
                    "start_us": item["start_us"],
                    "end_us": item["end_us"],
                    "market": item["condition"].removeprefix("0x"),
                    "venue_market_id": item["market_id"],
                    "event_id": item["event_id"],
                    "slug": item["slug"],
                    "up_token": orientation["Up"],
                    "down_token": orientation["Down"],
                    "lifecycle_state_at_capture": "closed"
                    if scan["parameters"]["closed"] == "true"
                    else "open",
                }
            )
    identities = {(item["event_id"], item["venue_market_id"], item["market"]) for item in values}
    if len(identities) != len(values):
        raise ValueError("duplicate first-party target identity across lifecycle enumerations")
    values.sort(key=lambda item: (item["start_us"], item["market"]))
    if len({item["start_us"] for item in values}) != len(values):
        raise ValueError("multiple target identities share one asset/interval")
    if len(values) != 288:
        raise ValueError("measured full-day target series result is not 288 aligned intervals")
    if [item["start_us"] for item in values] != list(range(begin_us, end_us, 300_000_000)):
        raise ValueError("measured target catalog has an interval gap")
    return values


def build_catalog() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    sources = []
    for asset in SERIES:
        report, source = _target_source(asset)
        sources.append(source)
        for day in DAYS:
            entries.extend(_day_entries(report, asset, day))
    expected = len(SERIES) * len(DAYS) * 288
    if len(entries) != expected or len({item["market"] for item in entries}) != expected:
        raise ValueError("target catalog identity closure failed")
    entries.sort(key=lambda item: (item["start_us"], item["asset"], item["market"]))
    value = {
        "schema": TARGET_CATALOG_SCHEMA,
        **scope_fields(),
        "claim": (
            "complete terminal first-party target-series result for both lifecycle states "
            "for each named UTC day, independently of V3 observation presence"
        ),
        "claim_limitations": [
            "does not claim retention of historically deleted listings",
            "does not use V3 observations to define expected target membership",
            "288 intervals per asset/day is a verified result, not a universal schedule rule",
        ],
        "days": list(DAYS),
        "assets": list(SERIES),
        "market_count": len(entries),
        "markets": entries,
        "source_evidence": sources,
        "source_network_bytes_reused": sum(report["size"] for report in sources),
        "new_first_party_identity_bytes": 0,
        "v3_source_reacquisition_bytes": 0,
        "implementation_commit": current_commit(),
    }
    value["generation"] = sha(canonical(value))
    payload = canonical(value)
    tag = "target-catalog-v1-" + value["generation"]
    release = publish(
        tag,
        {"target-catalog.json": payload},
        current_commit(),
        "Pinned seven-asset target-first catalog",
        "Identity-only first-party evidence; no research prices or outcomes.",
    )
    _output("target_catalog_tag", tag)
    _output("target_catalog_sha256", sha(payload))
    _output("days", list(DAYS))
    print(canonical({"release_id": release["id"], "markets": len(entries)}).decode())
    return value


def _verify_catalog_sources(value: dict[str, Any]) -> None:
    entries: list[dict[str, Any]] = []
    sources = []
    for asset in SERIES:
        report, source = _target_source(asset)
        sources.append(source)
        for day in DAYS:
            entries.extend(_day_entries(report, asset, day))
    entries.sort(key=lambda item: (item["start_us"], item["asset"], item["market"]))
    if entries != value.get("markets") or sources != value.get("source_evidence"):
        raise ValueError("target catalog differs from pinned first-party evidence")


def _load_target_catalog(tag: str, digest: str) -> dict[str, Any]:
    _, value = _json_release(tag, digest, "target-catalog.json")
    if value.get("schema") != TARGET_CATALOG_SCHEMA or tag != "target-catalog-v1-" + _generation(
        value
    ):
        raise ValueError("target catalog contract invalid")
    if any(value.get(key) != expected for key, expected in scope_fields().items()):
        raise ValueError("target catalog profile/scope mismatch")
    if (
        value.get("v3_source_reacquisition_bytes") != 0
        or value.get("new_first_party_identity_bytes") != 0
    ):
        raise ValueError("target catalog violated zero acquisition contract")
    if len(value.get("markets", [])) != len(SERIES) * len(DAYS) * 288:
        raise ValueError("target catalog cardinality invalid")
    _verify_catalog_sources(value)
    return value


def _load_index() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inventory, v3_catalog = _verify_inventory_catalog(V3_CATALOG_TAG, V3_CATALOG_SHA)
    release, index = _json_release(V3_INDEX_TAG, V3_INDEX_SHA, "data-index.json")
    if (
        release["id"] != V3_INDEX_RELEASE_ID
        or index.get("generation") != V3_INDEX_TAG.removeprefix("observed-data-index-v1-")
        or index.get("catalog_tag") != V3_CATALOG_TAG
        or index.get("catalog_sha256") != V3_CATALOG_SHA
        or index.get("complete_expected_partition_set") is not True
        or len(index.get("partitions", [])) != 116
        or len(index.get("unresolved_condition_references", [])) != 170369
        or sha(canonical(index["unresolved_condition_references"])) != UNRESOLVED_SET_SHA
    ):
        raise ValueError("retained V3 index pin/closure mismatch")
    return inventory, v3_catalog, index


def _mapping_relation(target: dict[str, Any], mapping: dict[str, Any]) -> bool:
    return all(
        target[name] == mapping[name]
        for name in ("asset", "start_us", "end_us", "market", "up_token", "down_token")
    )


def certify_day(target_tag: str, target_sha: str, day: str) -> dict[str, Any]:
    target_catalog = _load_target_catalog(target_tag, target_sha)
    inventory, v3_catalog, index = _load_index()
    expected = [
        item
        for item in target_catalog["markets"]
        if datetime.fromtimestamp(item["start_us"] / 1_000_000, UTC).date().isoformat() == day
    ]
    expected_by_market = {item["market"]: item for item in expected}
    v3_day = [
        item
        for item in v3_catalog["mappings"]
        if datetime.fromtimestamp(item["start_us"] / 1_000_000, UTC).date().isoformat() == day
    ]
    v3_by_market = {item["market"]: item for item in v3_day}
    missing = sorted(set(expected_by_market) - set(v3_by_market))
    unexpected = sorted(set(v3_by_market) - set(expected_by_market))
    mismatched = sorted(
        market
        for market in set(expected_by_market) & set(v3_by_market)
        if not _mapping_relation(expected_by_market[market], v3_by_market[market])
    )
    valid_mappings = [
        v3_by_market[market] for market in sorted(expected_by_market) if market in v3_by_market
    ]

    by_side = Counter[tuple[str, str]]()
    winners: dict[str, set[tuple[str, str]]] = defaultdict(set)
    observations = 0
    source_errors: list[dict[str, Any]] = []
    sources = []
    for part in index["partitions"]:
        source_errors.extend(error for error in part["errors"] if error["day"] == day)
        release = _release(part["tag"])
        _, report_data = _asset(release, "report.json")
        if sha(report_data) != part["report_sha256"]:
            raise ValueError("retained partition report digest mismatch")
        report = json.loads(report_data)
        _verify_source_proofs(report, inventory, report["hours"])
        matches = [
            asset for asset in release["assets"] if asset["name"].endswith("--" + day + ".jsonl.gz")
        ]
        if len(matches) > 1:
            raise ValueError("duplicate retained day shard")
        if not matches:
            continue
        asset = matches[0]
        data = read_asset(asset)
        sources.append(
            {
                "release_id": release["id"],
                "asset_id": asset["id"],
                "sha256": sha(data),
                "size": len(data),
                "partition": part["partition"],
                "source_partition": part["source_partition"],
            }
        )
        for row in iter_jsonl_gzip(data):
            mapping = v3_by_market.get(row.get("market"))
            if mapping is None or row["market"] not in expected_by_market:
                raise ValueError("retained canonical shard exceeds target catalog")
            if row["schema"] == OBSERVATION_SCHEMA:
                validate_observation(row)
                observations += 1
                if row["availability"] == "observed_ask":
                    by_side[(row["market"], row["outcome"])] += 1
            elif row["schema"] == RESOLUTION_SCHEMA:
                validate_resolution(row)
                winners[row["market"]].add((row["winning_token"], row["winning_outcome"]))
            else:
                raise ValueError("forbidden canonical row schema")
    missing_sides = sorted(
        f"{market}:{side}"
        for market in expected_by_market
        for side in ("UP", "DOWN")
        if not by_side[(market, side)]
    )
    missing_resolutions, contradictory, resolution_count = _resolution_evidence(
        expected_by_market, winners
    )
    reasons = []
    if len(expected) != len(SERIES) * 288:
        reasons.append("incomplete_independent_target_catalog")
    if missing:
        reasons.append("expected_target_missing_from_v3_mapping")
    if unexpected:
        reasons.append("v3_target_not_in_independent_catalog")
    if mismatched:
        reasons.append("target_identity_or_orientation_mismatch")
    if source_errors:
        reasons.append("malformed_target_source_rows")
    if missing_sides:
        reasons.append("missing_recorded_best_ask_side_evidence")
    if contradictory:
        reasons.append("contradictory_official_resolution")
    status = (
        "PENDING"
        if missing_resolutions and not reasons
        else "EXCLUDED"
        if reasons or missing_resolutions
        else "CERTIFIED"
    )
    if missing_resolutions:
        reasons.append("official_resolution_not_yet_present_in_pinned_v3")
    mapping_data = jsonl_gzip(valid_mappings) if status == "CERTIFIED" else b""
    manifest = {
        "schema": TARGET_DAY_SCHEMA,
        **scope_fields(),
        "status": status,
        "day": day,
        "claim": (
            "complete independent target-series catalog joined to authenticated retained "
            "V3 observations"
        ),
        "limitations": [
            "no continuity or missed-excursion exclusion",
            "no synthetic or time-only crossings",
            "no historical deleted-listing retention claim",
            "not sender execution reconstruction",
        ],
        "target_catalog_generation": target_catalog["generation"],
        "target_catalog_tag": target_tag,
        "target_catalog_sha256": target_sha,
        "v3_inventory_generation": v3_catalog["inventory_generation"],
        "v3_inventory_tag": v3_catalog["inventory_tag"],
        "v3_inventory_sha256": v3_catalog["inventory_sha256"],
        "v3_catalog_generation": v3_catalog["generation"],
        "v3_catalog_tag": V3_CATALOG_TAG,
        "v3_catalog_sha256": V3_CATALOG_SHA,
        "v3_data_index_generation": index["generation"],
        "v3_data_index_tag": V3_INDEX_TAG,
        "v3_data_index_sha256": V3_INDEX_SHA,
        "canonical_row_certification_scope": "PINNED_PUBLISHED_PENDULUMFLOW_V3_INVENTORY",
        "transform": TRANSFORM,
        "mapping_schema": MAPPING_SCHEMA,
        "observation_schema": OBSERVATION_SCHEMA,
        "resolution_schema": RESOLUTION_SCHEMA,
        "expected_market_count": len(expected),
        "present_and_valid_count": len(expected) - len(missing) - len(mismatched),
        "present_but_invalid": mismatched,
        "missing_from_v3": missing,
        "ambiguous_identity": [],
        "unexpected_v3_targets": unexpected,
        "unrelated_unidentified_v3_conditions_classified": 0,
        "unrelated_unidentified_v3_conditions_block_authority": False,
        "unresolved_v3_condition_count": len(index["unresolved_condition_references"]),
        "unresolved_v3_condition_set_sha256": UNRESOLVED_SET_SHA,
        "observation_count": observations,
        "resolution_count": resolution_count,
        "missing_sides": missing_sides,
        "missing_resolutions": missing_resolutions,
        "contradictory_resolutions": contradictory,
        "source_errors": source_errors,
        "certification_reasons": reasons,
        "source_assets": sources,
        "mapping_data_sha256": sha(mapping_data) if mapping_data else None,
        "mapping_data_size": len(mapping_data),
        "v3_source_reacquisition_bytes": 0,
        "research_import_allowed": status == "CERTIFIED",
        "implementation_commit": current_commit(),
    }
    manifest["generation"] = sha(canonical(manifest))
    payloads = {"manifest.json": canonical(manifest)}
    if mapping_data:
        payloads["mappings.jsonl.gz"] = mapping_data
    tag = "target-day-v1-" + manifest["generation"]
    release = publish(
        tag,
        payloads,
        current_commit(),
        f"Target-first observed day {day}: {status}",
        "Target-first V3 observed day assessment; read limitations before use.",
    )
    print(
        canonical(
            {
                "day": day,
                "status": status,
                "tag": tag,
                "release_id": release["id"],
                "markets": len(expected),
                "observations": observations,
                "reasons": reasons,
            }
        ).decode()
    )
    return manifest


def publish_window(target_tag: str, target_sha: str) -> dict[str, Any]:
    target_catalog = _load_target_catalog(target_tag, target_sha)
    latest: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for release in _all_releases():
        if not str(release.get("tag_name", "")).startswith("target-day-v1-") or not release.get(
            "immutable"
        ):
            continue
        _, raw = _asset(release, "manifest.json")
        value = json.loads(raw)
        if value.get("schema") != TARGET_DAY_SCHEMA or _generation(value) != release[
            "tag_name"
        ].removeprefix("target-day-v1-"):
            raise ValueError("target day release malformed")
        if value.get("target_catalog_generation") != target_catalog["generation"]:
            continue
        prior = latest.get(value["day"])
        if prior is None or release["id"] > prior[0]["id"]:
            latest[value["day"]] = (release, value)
    certified = [value for _, value in latest.values() if value["status"] == "CERTIFIED"]
    selected = select_window(certified)
    if not selected:
        raise ValueError("no target-first certified day exists")
    refs = []
    for day in selected:
        release, _ = latest[day["day"]]
        mapping_asset, _ = _asset(release, "mappings.jsonl.gz")
        manifest_asset, _ = _asset(release, "manifest.json")
        refs.append(
            {
                "day": day["day"],
                "generation": day["generation"],
                "tag": release["tag_name"],
                "release_id": release["id"],
                "manifest_sha256": manifest_asset["name"].split("--", 1)[0],
                "mapping_data_sha256": day["mapping_data_sha256"],
                "mapping_data_size": day["mapping_data_size"],
                "market_count": day["expected_market_count"],
                "observation_count": day["observation_count"],
                "mapping_asset_id": mapping_asset["id"],
            }
        )
    value = {
        "schema": TARGET_WINDOW_SCHEMA,
        **scope_fields(),
        "research_import_allowed": True,
        "claim": "rolling authority over independently cataloged target-first V3 observed days",
        "continuity_warning": (
            "continuity between observations is NOT certified; first means first "
            "qualifying RECORDED observation"
        ),
        "future_incompatible_profile": "OWN_RECORDER_EXACT",
        "target_catalog_generation": target_catalog["generation"],
        "target_catalog_tag": target_tag,
        "target_catalog_sha256": target_sha,
        "v3_inventory_generation": selected[-1]["v3_inventory_generation"],
        "v3_inventory_tag": selected[-1]["v3_inventory_tag"],
        "v3_inventory_sha256": selected[-1]["v3_inventory_sha256"],
        "v3_catalog_generation": selected[-1]["v3_catalog_generation"],
        "v3_catalog_tag": V3_CATALOG_TAG,
        "v3_catalog_sha256": V3_CATALOG_SHA,
        "v3_data_index_generation": selected[-1]["v3_data_index_generation"],
        "v3_data_index_tag": V3_INDEX_TAG,
        "v3_data_index_sha256": V3_INDEX_SHA,
        "canonical_row_certification_scope": "PINNED_PUBLISHED_PENDULUMFLOW_V3_INVENTORY",
        "included_certified_days": [item["day"] for item in refs],
        "day_generations": refs,
        "excluded_or_pending": [
            {"day": day, "status": item[1]["status"], "reasons": item[1]["certification_reasons"]}
            for day, item in sorted(latest.items())
            if item[1]["status"] != "CERTIFIED"
        ],
        "selection_rule": "all certified days when fewer than 30, otherwise latest 30 by UTC day",
        "verification": "python -m pflow.target_salvage verify --tag <tag> --sha256 <sha256>",
        "repository": "atalaydor/polymarket-5m-seven-asset-price-time-canonical-data",
        "v3_source_reacquisition_bytes": 0,
        "implementation_commit": current_commit(),
    }
    value["generation"] = sha(canonical(value))
    payload = canonical(value)
    tag = "target-window-v1-" + value["generation"]
    release = publish(
        tag,
        {"consumer-handoff.json": payload},
        current_commit(),
        "Target-first observed rolling window",
        "Factory-usable recorded-observation authority; no continuity claim.",
    )
    result = verify_window(tag, sha(payload))
    _update_target_current(tag, sha(payload), value, release["id"])
    _output("window_tag", tag)
    _output("handoff_sha256", sha(payload))
    print(
        canonical(
            {
                "release_id": release["id"],
                "verified": result["verified"],
                "days": value["included_certified_days"],
            }
        ).decode()
    )
    return value


def _update_target_current(tag: str, digest: str, value: dict[str, Any], release_id: int) -> None:
    pointer = canonical(
        {
            "schema": "pendulumflow-target-first-current-reference.v1",
            **scope_fields(),
            "research_import_allowed": True,
            "window_tag": tag,
            "handoff_sha256": digest,
            "window_generation": value["generation"],
            "window_release_id": release_id,
            "included_certified_days": value["included_certified_days"],
            "v3_inventory_generation": value["v3_inventory_generation"],
            "updated_by_run_id": os.environ.get("GITHUB_RUN_ID"),
        }
    )
    branch = "observed-current"
    ref = api(f"git/ref/heads/{branch}")
    if ref:
        commit = api("git/commits/" + ref["object"]["sha"])
        _, current = _load_current_blob(commit["tree"]["sha"])
        old_days = current.get("included_certified_days", [])
        new_days = value["included_certified_days"]
        if not isinstance(old_days, list) or not _rolling_day_set_advances(old_days, new_days):
            raise ValueError("target current reference would regress")
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
            "message": "Update target-first observed current-window reference",
            "tree": tree["sha"],
            "parents": [parent],
        },
    )
    if ref:
        api(f"git/refs/heads/{branch}", "PATCH", {"sha": commit["sha"], "force": False})
    else:
        api("git/refs", "POST", {"ref": "refs/heads/" + branch, "sha": commit["sha"]})
    blob_check = api("git/blobs/" + blob["sha"])
    if base64.b64decode(blob_check["content"]) != pointer:
        raise ValueError("current reference read-after-write failed")


def verify_window(tag: str, digest: str) -> dict[str, Any]:
    release, value = _json_release(tag, digest, "consumer-handoff.json")
    if value.get("schema") != TARGET_WINDOW_SCHEMA or tag != "target-window-v1-" + _generation(
        value
    ):
        raise ValueError("target window identity invalid")
    if any(value.get(key) != expected for key, expected in scope_fields().items()):
        raise ValueError("wrong target window profile/scope")
    if (
        value.get("research_import_allowed") is not True
        or value.get("future_incompatible_profile") != "OWN_RECORDER_EXACT"
    ):
        raise ValueError("target window is not importable observed authority")
    if value.get("v3_source_reacquisition_bytes") != 0 or not value.get("day_generations"):
        raise ValueError("target window acquisition/day closure invalid")
    target_catalog = _load_target_catalog(
        value["target_catalog_tag"], value["target_catalog_sha256"]
    )
    if target_catalog["generation"] != value["target_catalog_generation"]:
        raise ValueError("target catalog generation mismatch")
    names = [item["day"] for item in value["day_generations"]]
    if names != sorted(set(names)) or names != value["included_certified_days"] or len(names) > 30:
        raise ValueError("window day selection invalid")
    counts = Counter[str]()
    for reference in value["day_generations"]:
        day_release = _release(reference["tag"])
        manifest_asset, manifest_data = _asset(day_release, "manifest.json")
        manifest = json.loads(manifest_data)
        if (
            manifest.get("schema") != TARGET_DAY_SCHEMA
            or manifest.get("status") != "CERTIFIED"
            or manifest.get("research_import_allowed") is not True
            or _generation(manifest) != reference["generation"]
            or sha(manifest_data) != reference["manifest_sha256"]
            or manifest_asset["name"].split("--", 1)[0] != reference["manifest_sha256"]
            or manifest.get("target_catalog_generation") != target_catalog["generation"]
            or manifest.get("v3_source_reacquisition_bytes") != 0
            or manifest.get("certification_reasons")
        ):
            raise ValueError("referenced target day is not certified authority")
        mapping_asset, mapping_data = _asset(day_release, "mappings.jsonl.gz")
        if (
            mapping_asset["id"] != reference["mapping_asset_id"]
            or sha(mapping_data) != reference["mapping_data_sha256"]
        ):
            raise ValueError("target day mapping digest mismatch")
        mappings = {row["market"]: row for row in iter_jsonl_gzip(mapping_data)}
        for mapping_value in mappings.values():
            validate_mapping(mapping_value)
        expected = {
            item["market"]: item
            for item in target_catalog["markets"]
            if datetime.fromtimestamp(item["start_us"] / 1_000_000, UTC).date().isoformat()
            == reference["day"]
        }
        if set(mappings) != set(expected) or any(
            not _mapping_relation(expected[key], value) for key, value in mappings.items()
        ):
            raise ValueError("certified target day does not exhaust independent catalog")
        by_side: dict[str, set[str]] = defaultdict(set)
        winners: dict[str, set[tuple[str, str]]] = defaultdict(set)
        observations = 0
        for source in manifest["source_assets"]:
            shard_release = api(f"releases/{source['release_id']}")
            if shard_release is None or not shard_release.get("immutable"):
                raise ValueError("canonical shard release unavailable")
            matches = [
                asset for asset in shard_release["assets"] if asset["id"] == source["asset_id"]
            ]
            if len(matches) != 1:
                raise ValueError("canonical shard asset unavailable")
            data = read_asset(matches[0])
            if sha(data) != source["sha256"] or len(data) != source["size"]:
                raise ValueError("canonical shard bytes changed")
            for row in iter_jsonl_gzip(data):
                row_mapping = mappings.get(row.get("market"))
                if row_mapping is None:
                    raise ValueError("canonical row outside independent target catalog")
                if row["schema"] == OBSERVATION_SCHEMA:
                    validate_observation(row)
                    observations += 1
                    if row["availability"] == "observed_ask":
                        by_side[row["market"]].add(row["outcome"])
                elif row["schema"] == RESOLUTION_SCHEMA:
                    validate_resolution(row)
                    winners[row["market"]].add((row["winning_token"], row["winning_outcome"]))
                else:
                    raise ValueError("depth/opaque canonical row rejected")
            counts["bytes"] += len(data)
        if (
            any(by_side[market] != {"UP", "DOWN"} for market in mappings)
            or set(winners) != set(mappings)
            or any(len(items) != 1 for items in winners.values())
        ):
            raise ValueError("target day observation/resolution completeness mismatch")
        if (
            observations != manifest["observation_count"]
            or len(mappings) != manifest["expected_market_count"]
        ):
            raise ValueError("target day count mismatch")
        counts["markets"] += len(mappings)
        counts["observations"] += observations
        counts["resolutions"] += len(winners)
        counts["bytes"] += len(mapping_data)
    return {
        "verified": True,
        "research_import_allowed": True,
        "profile": PROFILE,
        "profile_version": PROFILE_VERSION,
        "certification_scope": TARGET_SCOPE,
        "certification_scope_version": TARGET_SCOPE_VERSION,
        "continuity_between_observations_certified": False,
        "historical_deleted_listing_completeness_claimed": False,
        "tag": tag,
        "sha256": digest,
        "release_id": release["id"],
        "days": names,
        "counts": dict(counts),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    command = parser.add_subparsers(dest="command", required=True)
    command.add_parser("catalog")
    certify = command.add_parser("certify")
    certify.add_argument("--target-tag", required=True)
    certify.add_argument("--target-sha", required=True)
    certify.add_argument("--day", required=True, choices=DAYS)
    window = command.add_parser("window")
    window.add_argument("--target-tag", required=True)
    window.add_argument("--target-sha", required=True)
    verify = command.add_parser("verify")
    verify.add_argument("--tag", required=True)
    verify.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.command == "catalog":
        build_catalog()
    elif args.command == "certify":
        certify_day(args.target_tag, args.target_sha, args.day)
    elif args.command == "window":
        publish_window(args.target_tag, args.target_sha)
    else:
        print(canonical(verify_window(args.tag, args.sha256)).decode())


if __name__ == "__main__":
    main()
