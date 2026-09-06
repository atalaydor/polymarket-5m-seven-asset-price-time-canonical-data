"""First-party target-series history diagnostics; no research or outcome authority."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from pflow.catalog_enumerate import summary as stream_summary
from pflow.catalog_enumerate import validate as validate_stream
from pflow.catalog_probe import (
    PRIOR_SHA,
    PRIOR_TAG,
    SCHEMA,
    SCOPE,
    Reader,
    keys,
    scan,
    validate_report,
)
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import canonical, sha

SCHEMA_TARGET = "polymarket-target-series-diagnostic.v1"
SERIES_TAG = "catalog-enumeration-4c065ce9d6c76e8b07835b97a04c96cab6cffaf88e3d83c99b1d2c66ea8ea478"
SERIES_SHA = "f4dbb82576c1001d25d82cb91163b51250da20cdc3c48bbe89e78ce3658e3c05"
SERIES_COMMIT = "8659c75117a2b2acf080cea49ee0143d54ef25ae"
SERIES = dict(
    BTC="10684", ETH="10683", SOL="10686", XRP="10685", DOGE="11325", BNB="11326", HYPE="11327"
)
DAYS = ("2026-08-25", "2026-08-27", "2026-08-28")


def queries(asset: str) -> list[dict[str, str]]:
    result = []
    for closed in ("true", "false"):
        for ascending in ("true", "false"):
            result.append(
                dict(
                    limit="1",
                    order="id",
                    ascending=ascending,
                    closed=closed,
                    series_id=SERIES[asset],
                )
            )
        for day in DAYS:
            end = datetime.fromisoformat(day) + timedelta(days=1, minutes=5)
            result.append(
                dict(
                    limit="100",
                    order="id",
                    ascending="true",
                    closed=closed,
                    series_id=SERIES[asset],
                    end_date_min=day + "T00:00:00Z",
                    end_date_max=end.isoformat() + "Z",
                )
            )
    return result


def series_evidence() -> dict[str, Any]:
    release = api("releases/tags/" + SERIES_TAG)
    asset = next(a for a in release["assets"] if a["name"].endswith("--catalog-stream.json"))
    raw = read_asset(asset)
    if sha(raw) != SERIES_SHA:
        raise ValueError("independent series catalog pin mismatch")
    report = json.loads(raw)
    validate_stream(report, report["specification"], SERIES_COMMIT)
    overview = canonical(stream_summary(report))
    verify_release(release, {asset["name"]: raw, sha(overview) + "--summary.json": overview})
    if api("git/ref/tags/" + SERIES_TAG)["object"]["sha"] != SERIES_COMMIT:
        raise ValueError("series transform tag mismatch")
    return dict(report)


def instant(value: str | None) -> int | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("naive first-party interval")
    delta = dt.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def interval(row: dict[str, Any], asset: str) -> dict[str, Any]:
    start = instant(row["startTime"])
    end = instant(row["endDate"])
    markets = row["markets"]
    errors = []
    if start is None or end is None or end - start != 300_000_000 or start % 300_000_000:
        errors.append("UNPROVEN_5M_INTERVAL")
    if not markets or len(markets) != 1:
        errors.append("NONUNIQUE_MARKET")
    market = markets[0] if markets and len(markets) == 1 else None
    if market is not None:
        if market["eventStartTime"] is not None and instant(market["eventStartTime"]) != start:
            errors.append("MARKET_EVENT_START_MISMATCH")
        if instant(market["endDate"]) != end:
            errors.append("MARKET_EVENT_END_MISMATCH")
        if (
            market["outcomes"] != ["Up", "Down"]
            or not market["clobTokenIds"]
            or len(market["clobTokenIds"]) != 2
        ):
            errors.append("UNPROVEN_TOKEN_ORIENTATION")
        if not market["conditionId"] or not re.fullmatch(r"0x[0-9a-f]{64}", market["conditionId"]):
            errors.append("UNPROVEN_CONDITION")
    if start is not None and row["slug"] != f"{asset.lower()}-updown-5m-{start // 1_000_000}":
        errors.append("SLUG_INTERVAL_MISMATCH")
    if not row["series"] or SERIES[asset] not in [s["id"] for s in row["series"]]:
        errors.append("SERIES_RELATION_MISMATCH")
    return dict(
        event_id=row["id"],
        slug=row["slug"],
        start_us=start,
        end_us=end,
        market_id=market["id"] if market else None,
        condition=market["conditionId"] if market else None,
        tokens=market["clobTokenIds"] if market else None,
        errors=errors,
    )


def summary(report: dict[str, Any]) -> dict[str, Any]:
    asset = report["asset"]
    diagnostics = []
    for stream in report["evidence"]["scans"]:
        rows = stream["rows"]
        identities = [interval(row, asset) for row in rows]
        diagnostics.append(
            dict(
                parameters=stream["parameters"],
                rows=len(rows),
                pages=len(stream["pages"]),
                terminal=stream["terminal_observed"],
                error=stream["error"],
                duplicates=stream["duplicate_ids"],
                interval_errors=[i for i in identities if i["errors"]][:20],
                interval_error_count=sum(bool(i["errors"]) for i in identities),
                first=identities[:2],
                last=identities[-2:],
                market_start_day_counts={
                    day: sum(
                        i["start_us"] is not None
                        and instant(day + "T00:00:00Z")
                        <= i["start_us"]
                        < instant(day + "T00:00:00Z") + 86400_000_000  # type: ignore[operator]
                        for i in identities
                    )
                    for day in DAYS
                },
            )
        )
    return dict(
        schema=SCHEMA_TARGET,
        identity=report["identity"],
        asset=asset,
        series_id=SERIES[asset],
        streams=diagnostics,
        source_bytes=report["evidence"]["downloaded_bytes"],
        network_ns=report["evidence"]["network_ns"],
        expected_catalog_certified=False,
        research_import_allowed=False,
    )


def validate(report: dict[str, Any], asset: str, commit: str) -> None:
    keys(report, "schema identity asset commit series_tag series_sha256 evidence")
    identity = sha(
        canonical(dict(schema=SCHEMA_TARGET, asset=asset, commit=commit, series_sha256=SERIES_SHA))
    )
    if (
        report["schema"] != SCHEMA_TARGET
        or report["identity"] != identity
        or report["asset"] != asset
        or report["commit"] != commit
        or report["series_tag"] != SERIES_TAG
        or report["series_sha256"] != SERIES_SHA
    ):
        raise ValueError("target diagnostic provenance mismatch")
    evidence = report["evidence"]
    validate_report(
        evidence, sha(canonical(dict(schema=SCHEMA, commit=commit, prior_sha256=PRIOR_SHA)))
    )
    if evidence["slug_checks"] or [s["parameters"] for s in evidence["scans"]] != queries(asset):
        raise ValueError("target query inventory mismatch")
    if any(s["path"] != "/events/keyset" for s in evidence["scans"]):
        raise ValueError("target query route mismatch")


def run(asset: str) -> None:
    commit = current_commit()
    identity = sha(
        canonical(dict(schema=SCHEMA_TARGET, asset=asset, commit=commit, series_sha256=SERIES_SHA))
    )
    tag = "catalog-targets-" + identity
    existing = api("releases/tags/" + tag)
    if existing is not None and existing["assets"]:
        selected = [a for a in existing["assets"] if a["name"].endswith("--target-series.json")]
        if len(selected) != 1:
            raise ValueError("unique target checkpoint required")
        raw = read_asset(selected[0], draft=existing["draft"])
        report = json.loads(raw)
    else:
        source = series_evidence()
        rows = source["evidence"]["scans"][0]["rows"]
        chosen = [r for r in rows if r["id"] == SERIES[asset]]
        if len(chosen) != 1 or chosen[0]["slug"] != asset.lower() + "-up-or-down-5m":
            raise ValueError("series identity not independently discovered")
        reader = Reader()
        reader.opener.addheaders = [
            ("User-Agent", "PendulumFlowCatalogProof/0.1 (public metadata research)"),
            ("Accept", "application/json"),
        ]
        scans = [
            scan(reader, "/events/keyset", q, "event", 1 if q["limit"] == "1" else 10)
            for q in queries(asset)
        ]
        evidence = dict(
            schema=SCHEMA,
            identity=sha(canonical(dict(schema=SCHEMA, commit=commit, prior_sha256=PRIOR_SHA))),
            commit=commit,
            workflow_run_id=os.environ.get("GITHUB_RUN_ID"),
            prior_tag=PRIOR_TAG,
            prior_sha256=PRIOR_SHA,
            semantic_profile="PENDULUMFLOW_V3_OBSERVED",
            profile_version=1,
            research_import_allowed=False,
            expected_catalog_certified=False,
            scans=scans,
            slug_checks=[],
            requests=reader.ledger,
            downloaded_bytes=reader.bytes,
            network_ns=sum(r["network_ns"] for r in reader.ledger),
            foreign_price_outcome_depth_fields_retained=False,
            scope=SCOPE,
        )
        report = dict(
            schema=SCHEMA_TARGET,
            identity=identity,
            asset=asset,
            commit=commit,
            series_tag=SERIES_TAG,
            series_sha256=SERIES_SHA,
            evidence=evidence,
        )
        raw = canonical(report)
    validate(report, asset, commit)
    overview = canonical(summary(report))
    release = publish(
        tag,
        {"target-series.json": raw, "summary.json": overview},
        commit,
        "Target catalog evidence: " + asset,
    )
    print(canonical(dict(tag=tag, release_id=release["id"], summary_sha256=sha(overview))).decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("asset", choices=tuple(SERIES))
    run(parser.parse_args().asset)
