"""Independent pinned GitHub evidence review; no source acquisition or research approval."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from pflow.catalog_enumerate import specification, stable
from pflow.catalog_enumerate import summary as series_summary
from pflow.catalog_enumerate import validate as validate_series
from pflow.catalog_probe import PRIOR_SHA, PRIOR_TAG, project
from pflow.catalog_targets import DAYS, SERIES
from pflow.catalog_targets import summary as target_summary
from pflow.catalog_targets import validate as validate_target
from pflow.model import ASSETS, validate_quote
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import canonical, sha

SCHEMA = "polymarket-independent-catalog-review.v2"
SERIES_COMMIT = "8659c75117a2b2acf080cea49ee0143d54ef25ae"
TARGET_COMMIT = "c4df60f9bfaa2ae1ea4f5d8838c33f73d6025e0b"
NATIVE_COMMIT = "58b8fa385c676b8ce454a02e0e8bc5bfc9dfb19a"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# All pins were frozen from the already sealed public release metadata before this review.
# name -> (release ID, report asset ID, tag suffix, report SHA-256)
SERIES_PINS = {
    "ascending": (
        383545434,
        547060367,
        "4c065ce9d6c76e8b07835b97a04c96cab6cffaf88e3d83c99b1d2c66ea8ea478",
        "f4dbb82576c1001d25d82cb91163b51250da20cdc3c48bbe89e78ce3658e3c05",
    ),
    "descending": (
        383545482,
        547060538,
        "7c6512c01e8f1d3642cf658c682d51f8f1a369f4c97c7db80018c9e56053687d",
        "42f1e04183603e84d8e85fa08ebf4bd46bbf3ad1578f4855c476d44ce84a9b6d",
    ),
}
TARGET_PINS = {
    "BTC": (
        383548088,
        547070436,
        "537a1de71f435bed033ac1343f38ec524b1f5b1dd5e151a9f1dff6b71f0f8786",
        "5cf3abbcbbcb8e537d00c32735cfcb3c273062a561e8acf46e852c73e58874b9",
    ),
    "ETH": (
        383548111,
        547070496,
        "cec376a71017f65590a0eacbcc4ae680260f99622bfddd1651f1bf57b5689253",
        "642a56cb6dc1ed2a82ec0619b98e12a1010800ddb6cd324506c9b29c35166022",
    ),
    "SOL": (
        383548184,
        547070797,
        "60a158da35341f65e9dddad274ce9e6921557a91480b7ef73d10063cbc9f2876",
        "e302dc2b9b3d6e99c12425167d0f0753320d4651ee2c14b816a1a7d645a3c142",
    ),
    "XRP": (
        383548224,
        547070972,
        "fc9fd8de84370a604c6dbf46f11ee6c8562370449c3dbcc240f21165ce13c058",
        "608239b2e3b98853fe804921411f5cb0b622bedc420c3fa697c438f4be51544d",
    ),
    "DOGE": (
        383548283,
        547071138,
        "35daa283d99bbc146639840f0b6303c77fbe219ad3b8434b0c179ec314ba7bd0",
        "4d68177a622b63b28a91bdea1ad7f7c5278ccce4110a2f8dbf37aebe5556116c",
    ),
    "BNB": (
        383548320,
        547071218,
        "413d5ddc6e9f25197acdd34f03c5e13eed543983ed7eac103d439f2dfca3f272",
        "0373dcbd1d83db8a7aef7ca91de271aab1e78cb610fe6bf96bcd40370f880fdc",
    ),
    "HYPE": (
        383548375,
        547071419,
        "22b534ca89cfc8cfebd3e998e491c523438b7004ef3c4ec6a237524b99bdb6f7",
        "554622969833cf73965dbb6771833b9fe8b5765bc60b166f27a2b82add12dc16",
    ),
}
SCOPE = (
    "positive identities in exact pinned queries; no historical denominator or research authority"
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def linux_only() -> None:
    import platform

    require(
        platform.system() == "Linux" and os.environ.get("GITHUB_ACTIONS") == "true",
        "pinned full-report review requires Actions Linux",
    )


def pinned_report(
    name: str, pin: tuple[int, int, str, str], kind: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    linux_only()
    release_id, asset_id, suffix, digest = pin
    prefix = {
        "series": "catalog-enumeration-",
        "target": "catalog-targets-",
        "native": "source-probe-",
    }[kind]
    tag = prefix + suffix
    commit = {"series": SERIES_COMMIT, "target": TARGET_COMMIT, "native": NATIVE_COMMIT}[kind]
    filename = {
        "series": "catalog-stream.json",
        "target": "target-series.json",
        "native": "report.json",
    }[kind]
    release = api("releases/tags/" + tag)
    require(release is not None and release["id"] == release_id, "pinned release identity mismatch")
    require(release["tag_name"] == tag, "pinned release tag mismatch")
    assets = release["assets"]
    require(len(assets) == (1 if kind == "native" else 2), "pinned inventory count mismatch")
    require(
        all(type(a["size"]) is int and 0 < a["size"] < 8_000_000 for a in assets),
        "pinned evidence size bound exceeded",
    )
    matches = [a for a in assets if a["id"] == asset_id and a["name"] == digest + "--" + filename]
    require(len(matches) == 1, "pinned report asset identity mismatch")
    raw = read_asset(matches[0])
    require(sha(raw) == digest, "independent report SHA-256 mismatch")
    report = json.loads(raw)
    expected = {digest + "--" + filename: raw}
    if kind == "series":
        validate_series(report, specification("series-complete-" + name), commit)
        overview = canonical(series_summary(report))
        expected[sha(overview) + "--summary.json"] = overview
    elif kind == "target":
        validate_target(report, name, commit)
        overview = canonical(target_summary(report))
        expected[sha(overview) + "--summary.json"] = overview
    else:
        require(
            report["schema"] == "pendulumflow-source-canary.v1"
            and report["partition_identity"] == suffix
            and report["transform_commit"] == commit
            and report["research_authority"] is False
            and report["certified_days"] == [],
            "native evidence scope/transform mismatch",
        )
        require(
            set(report["quote_samples"])
            == {a + ":" + side for a in ASSETS for side in ("UP", "DOWN")},
            "native sample inventory mismatch",
        )
        for row in report["quote_samples"].values():
            validate_quote(row)
    verify_release(release, expected)
    ref = api("git/ref/tags/" + tag)
    require(
        ref["object"]["type"] == "commit" and ref["object"]["sha"] == commit,
        "pinned tag transform mismatch",
    )
    return report, dict(
        name=name,
        kind=kind,
        release_id=release_id,
        report_asset_id=asset_id,
        tag=tag,
        report_sha256=digest,
        report_bytes=len(raw),
        commit=commit,
        immutable_verified=True,
        exact_inventory_verified=True,
    )


def clock(value: str | None) -> int | None:
    if value is None:
        return None
    require(
        re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
            value,
        )
        is not None,
        "unsupported metadata clock",
    )
    delta = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def identity(row: dict[str, Any], asset: str) -> dict[str, Any]:
    require(project(row, "event") == row, "foreign field in event projection")
    start, end = clock(row["startTime"]), clock(row["endDate"])
    require(start is not None and end is not None, "missing target interval")
    assert start is not None and end is not None
    require(
        start % 300_000_000 == 0 and end - start == 300_000_000,
        "target interval is not exact five minutes",
    )
    require(
        row["slug"] == f"{asset.lower()}-updown-5m-{start // 1_000_000}",
        "target slug/interval mismatch",
    )
    require(
        bool(row["series"]) and SERIES[asset] in [s["id"] for s in row["series"]],
        "target series mismatch",
    )
    require(
        row["markets"] is not None and len(row["markets"]) == 1,
        "target event market cardinality mismatch",
    )
    market = row["markets"][0]
    require(
        clock(market["endDate"]) == end
        and (market["eventStartTime"] is None or clock(market["eventStartTime"]) == start),
        "market/event interval mismatch",
    )
    labels, tokens = market["outcomes"], market["clobTokenIds"]
    require(labels in (["Up", "Down"], ["Down", "Up"]), "unproven outcome orientation")
    require(
        tokens is not None and len(tokens) == 2 and len(set(tokens)) == 2,
        "unproven complementary tokens",
    )
    require(
        all(
            re.fullmatch(r"[1-9][0-9]{0,77}", token) is not None and int(token) < 2**256
            for token in tokens
        ),
        "invalid outcome token identity",
    )
    require(
        isinstance(market["conditionId"], str)
        and re.fullmatch(r"0x[0-9a-f]{64}", market["conditionId"]) is not None,
        "invalid target condition",
    )
    require(
        all(isinstance(value, str) and bool(value) for value in (row["id"], market["id"])),
        "missing positive listing identity",
    )
    return dict(
        asset=asset,
        event_id=row["id"],
        market_id=market["id"],
        condition=market["conditionId"][2:],
        start_us=start,
        end_us=end,
        up_token=tokens[labels.index("Up")],
        down_token=tokens[labels.index("Down")],
    )


def day_diagnostic(rows: list[dict[str, Any]], day: str) -> dict[str, Any]:
    lower = clock(day + "T00:00:00Z")
    assert lower is not None
    selected = [r for r in rows if lower <= r["start_us"] < lower + 86_400_000_000]
    starts = sorted(r["start_us"] for r in selected)
    unique = all(
        len({r[key] for r in selected}) == len(selected)
        for key in ("event_id", "market_id", "condition", "start_us")
    )
    grid = starts == [lower + i * 300_000_000 for i in range(288)]
    return dict(
        day=day,
        returned_rows=len(selected),
        unique_event_market_condition_start=unique,
        observed_288_grid_diagnostic=grid,
        identity_sha256=sha(canonical(sorted(selected, key=canonical))),
        expected_membership_inferred=False,
    )


def review_target(report: dict[str, Any], asset: str) -> tuple[dict[str, Any], dict[str, Any]]:
    by_condition: dict[str, Any] = {}
    by_day: dict[str, list[dict[str, Any]]] = {day: [] for day in DAYS}
    terminal_days = 0
    sentinel_nonterminal = 0
    for stream in report["evidence"]["scans"]:
        require(
            stream["error"] is None and not stream["duplicate_ids"],
            "target query error or duplicate rows",
        )
        records = [identity(row, asset) for row in stream["rows"]]
        for record in records:
            condition = record["condition"]
            require(
                condition not in by_condition or by_condition[condition] == record,
                "contradictory target identity across queries",
            )
            by_condition[condition] = record
        params = stream["parameters"]
        if "end_date_min" in params:
            require(stream["terminal_observed"] is True, "day query is not terminal")
            day = params["end_date_min"][:10]
            by_day[day].extend(records)
            terminal_days += 1
        elif not stream["terminal_observed"]:
            sentinel_nonterminal += 1
    days = [day_diagnostic(by_day[day], day) for day in DAYS]
    require(
        all(
            d["unique_event_market_condition_start"] and d["observed_288_grid_diagnostic"]
            for d in days
        ),
        "positive target day identities differ from observed 288 grid",
    )
    return dict(
        asset=asset,
        series_id=SERIES[asset],
        query_count=len(report["evidence"]["scans"]),
        terminal_day_queries=terminal_days,
        nonterminal_id_sentinels=sentinel_nonterminal,
        unique_returned_conditions=len(by_condition),
        interval_errors=0,
        days=days,
        all_outcome_token_pairs_oriented=True,
    ), by_condition


def classify_series(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ("slug", "title", "ticker", "recurrence")
    pattern = re.compile(r"(?<![a-z0-9])(?:5|five)[\s_-]*(?:m|min(?:ute)?s?)(?![a-z])", re.I)
    aliases = dict(
        BTC=r"btc|bitcoin",
        ETH=r"eth|ether|ethereum",
        SOL=r"sol|solana",
        XRP=r"xrp|ripple",
        DOGE=r"doge|dogecoin",
        BNB=r"bnb|binance",
        HYPE=r"hype|hyperliquid",
    )
    candidates = []
    nulls = Counter({field: 0 for field in fields})
    missing_identity = 0
    known = set(SERIES.values())
    for row in rows:
        require(project(row, "series") == row, "foreign field in series projection")
        require(
            isinstance(row["id"], str) and re.fullmatch(r"[0-9]{1,20}", row["id"]) is not None,
            "unsupported series identity representation",
        )
        for field in fields:
            nulls[field] += row[field] is None
        missing_identity += row["slug"] is None and row["title"] is None
        hints = [field for field in fields if pattern.search(row[field] or "")]
        if hints or row["id"] in known:
            text = " ".join(row[field] or "" for field in fields)
            assets = [
                a
                for a in ASSETS
                if re.search(r"(?<![a-z0-9])(?:" + aliases[a] + r")(?![a-z0-9])", text, re.I)
            ]
            candidates.append(
                dict(
                    series_id=row["id"],
                    slug=row["slug"],
                    title=row["title"],
                    recurrence=row["recurrence"],
                    known_target=row["id"] in known,
                    matched_assets=assets,
                    hint_fields=hints,
                    null_fields=[f for f in fields if row[f] is None],
                )
            )
    candidates.sort(key=lambda row: row["series_id"])
    ambiguous = [
        row for row in candidates if len(row["matched_assets"]) != 1 or not row["known_target"]
    ]
    return dict(
        rows_scanned=len(rows),
        null_field_counts=dict(nulls),
        null_slug_and_title_rows=missing_identity,
        five_minute_candidates=len(candidates),
        known_target_candidates=sum(row["known_target"] for row in candidates),
        unknown_or_ambiguous_candidates=len(ambiguous),
        candidate_inventory_sha256=sha(canonical(candidates)),
        candidate_samples=candidates[:32],
        candidate_samples_truncated=len(candidates) > 32,
        classification_is_heuristic=True,
        historical_alias_completeness_proven=False,
    )


def validate_output(report: dict[str, Any]) -> None:
    require(
        set(report)
        == {
            "schema",
            "commit",
            "input_pins",
            "full_series_count",
            "opposite_order_stable_identities_equal",
            "stable_series_identity_sha256",
            "series_classification",
            "targets",
            "native_identity_comparisons",
            "native_identity_matches",
            "unique_positive_target_day_conditions",
            "unique_positive_target_day_markets",
            "unique_positive_target_day_events",
            "positive_target_day_identity_sha256",
            "first_party_source_requests",
            "native_payload_requests",
            "foreign_prices_outcomes_depth_exported",
            "expected_catalog_certified",
            "research_import_allowed",
            "certified_days",
            "scope",
        },
        "unexpected review output field",
    )
    require(
        report["schema"] == SCHEMA
        and report["scope"] == SCOPE
        and re.fullmatch(r"[0-9a-f]{40}", report["commit"]) is not None,
        "invalid review schema/provenance",
    )
    for field in (
        "expected_catalog_certified",
        "research_import_allowed",
        "foreign_prices_outcomes_depth_exported",
    ):
        require(
            report[field] is False, "review cannot confer authority or export foreign observations"
        )
    require(
        report["first_party_source_requests"] == 0
        and report["native_payload_requests"] == 0
        and report["certified_days"] == [],
        "unexpected review source activity or promotion",
    )
    require(
        len(report["input_pins"]) == 10 and len(report["targets"]) == 7,
        "review input/asset inventory mismatch",
    )
    for pin in report["input_pins"]:
        require(
            set(pin)
            == {
                "name",
                "kind",
                "release_id",
                "report_asset_id",
                "tag",
                "report_sha256",
                "report_bytes",
                "commit",
                "immutable_verified",
                "exact_inventory_verified",
            },
            "unexpected pin evidence field",
        )
        require(
            pin["immutable_verified"] is True and pin["exact_inventory_verified"] is True,
            "unverified input cannot pass",
        )
    classification = report["series_classification"]
    require(
        set(classification)
        == {
            "rows_scanned",
            "null_field_counts",
            "null_slug_and_title_rows",
            "five_minute_candidates",
            "known_target_candidates",
            "unknown_or_ambiguous_candidates",
            "candidate_inventory_sha256",
            "candidate_samples",
            "candidate_samples_truncated",
            "classification_is_heuristic",
            "historical_alias_completeness_proven",
        },
        "unexpected classification evidence field",
    )
    require(
        classification["classification_is_heuristic"] is True
        and classification["historical_alias_completeness_proven"] is False,
        "candidate heuristic cannot establish historical completeness",
    )
    require(
        set(classification["null_field_counts"]) == {"slug", "title", "ticker", "recurrence"},
        "unexpected null-field diagnostic",
    )
    for candidate in classification["candidate_samples"]:
        require(
            set(candidate)
            == {
                "series_id",
                "slug",
                "title",
                "recurrence",
                "known_target",
                "matched_assets",
                "hint_fields",
                "null_fields",
            },
            "unexpected candidate metadata field",
        )
        require(
            all(
                candidate[field] is None
                or (isinstance(candidate[field], str) and len(candidate[field]) <= 2048)
                for field in ("slug", "title", "recurrence")
            ),
            "unexpected candidate identity text",
        )
        require(
            re.fullmatch(r"[0-9]{1,20}", candidate["series_id"]) is not None
            and set(candidate["matched_assets"]) <= set(ASSETS)
            and set(candidate["hint_fields"] + candidate["null_fields"])
            <= {"slug", "title", "ticker", "recurrence"},
            "unexpected candidate metadata value",
        )
    for asset, target in zip(ASSETS, report["targets"], strict=True):
        require(
            set(target)
            == {
                "asset",
                "series_id",
                "query_count",
                "terminal_day_queries",
                "nonterminal_id_sentinels",
                "unique_returned_conditions",
                "interval_errors",
                "days",
                "all_outcome_token_pairs_oriented",
            }
            and target["asset"] == asset
            and target["series_id"] == SERIES[asset],
            "unexpected target diagnostic field or identity",
        )
        require(len(target["days"]) == len(DAYS), "unexpected day diagnostic inventory")
        for day, evidence in zip(DAYS, target["days"], strict=True):
            require(
                set(evidence)
                == {
                    "day",
                    "returned_rows",
                    "unique_event_market_condition_start",
                    "observed_288_grid_diagnostic",
                    "identity_sha256",
                    "expected_membership_inferred",
                }
                and evidence["day"] == day
                and evidence["expected_membership_inferred"] is False,
                "unexpected day diagnostic field or authority claim",
            )


def run() -> None:
    linux_only()
    provenance = []
    series_reports = []
    for name, pin in SERIES_PINS.items():
        report, record = pinned_report(name, pin, "series")
        provenance.append(record)
        stream = report["evidence"]["scans"][0]
        require(
            stream["terminal_observed"] is True
            and stream["error"] is None
            and not stream["duplicate_ids"]
            and len(stream["rows"]) == 2414,
            "pinned full-series traversal not complete as observed",
        )
        series_reports.append(stream["rows"])
    stable_rows = [
        sorted([stable(row, "series") for row in rows], key=canonical) for rows in series_reports
    ]
    require(stable_rows[0] == stable_rows[1], "opposite-order full series identities disagree")
    classification = classify_series(series_reports[0])
    for asset in ASSETS:
        selected = [row for row in series_reports[0] if row["id"] == SERIES[asset]]
        require(
            len(selected) == 1 and selected[0]["slug"] == asset.lower() + "-up-or-down-5m",
            "independent target series discovery mismatch",
        )
    native, record = pinned_report(
        "native-aug28",
        (383484175, 546816669, PRIOR_TAG.removeprefix("source-probe-"), PRIOR_SHA),
        "native",
    )
    provenance.append(record)
    targets = []
    matched = 0
    positive: dict[str, Any] = {}
    day_bounds = [clock(day + "T00:00:00Z") for day in DAYS]
    for asset in ASSETS:
        report, record = pinned_report(asset, TARGET_PINS[asset], "target")
        provenance.append(record)
        target, records = review_target(report, asset)
        for condition, mapping in records.items():
            if any(
                lower is not None and lower <= mapping["start_us"] < lower + 86_400_000_000
                for lower in day_bounds
            ):
                require(condition not in positive, "condition appears in multiple asset identities")
                positive[condition] = mapping
        for side, token_field in (("UP", "up_token"), ("DOWN", "down_token")):
            quote = native["quote_samples"][asset + ":" + side]
            require(
                quote["asset"] == asset and quote["outcome"] == side,
                "native quote identity label mismatch",
            )
            require(quote["market"] in records, "native condition not in positive target queries")
            mapping = records[quote["market"]]
            require(
                mapping[token_field] == quote["token"]
                and mapping["start_us"] == quote["start_us"]
                and mapping["end_us"] == quote["end_us"],
                "native/catalog oriented mismatch",
            )
            matched += 1
        targets.append(target)
    positive_markets = {record["market_id"] for record in positive.values()}
    positive_events = {record["event_id"] for record in positive.values()}
    require(
        len(positive) == len(positive_markets) == len(positive_events) == 6048,
        "positive target days do not contain 6048 globally unique listing identities",
    )
    commit = current_commit()
    report = dict(
        schema=SCHEMA,
        commit=commit,
        input_pins=provenance,
        full_series_count=2414,
        opposite_order_stable_identities_equal=True,
        stable_series_identity_sha256=sha(canonical(stable_rows[0])),
        series_classification=classification,
        targets=targets,
        native_identity_comparisons=matched,
        native_identity_matches=matched,
        unique_positive_target_day_conditions=len(positive),
        unique_positive_target_day_markets=len(positive_markets),
        unique_positive_target_day_events=len(positive_events),
        positive_target_day_identity_sha256=sha(
            canonical(sorted(positive.values(), key=canonical))
        ),
        first_party_source_requests=0,
        native_payload_requests=0,
        foreign_prices_outcomes_depth_exported=False,
        expected_catalog_certified=False,
        research_import_allowed=False,
        certified_days=[],
        scope=SCOPE,
    )
    require(matched == 14, "incomplete native identity comparison")
    validate_output(report)
    raw = canonical(report)
    require(len(raw) < 64_000, "review report exceeds fixed small evidence bound")
    tag = "catalog-independent-review-" + sha(raw)
    release = publish(
        tag,
        {"independent-review.json": raw},
        commit,
        "Independent pinned catalog identity review; no research authority",
    )
    print(
        canonical(
            dict(
                tag=tag,
                release_id=release["id"],
                sha256=sha(raw),
                bytes=len(raw),
                research_import_allowed=False,
                expected_catalog_certified=False,
            )
        ).decode()
    )


def self_test() -> None:
    row = project(
        dict(
            id="1",
            slug="btc-updown-5m-1787875200",
            startTime="2026-08-28T00:00:00Z",
            endDate="2026-08-28T00:05:00Z",
            series=[dict(id="10684")],
            markets=[
                dict(
                    id="2",
                    conditionId="0x" + "1" * 64,
                    eventStartTime="2026-08-28T00:00:00Z",
                    endDate="2026-08-28T00:05:00Z",
                    outcomes=["Down", "Up"],
                    clobTokenIds=["11", "22"],
                )
            ],
        ),
        "event",
    )
    require(identity(row, "BTC")["up_token"] == "22", "self-test orientation")
    row["markets"][0]["clobTokenIds"] = ["11", "11"]
    try:
        identity(row, "BTC")
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate tokens accepted")
    try:
        clock("2026-08-28T00:00:00.0000001Z")
    except ValueError:
        pass
    else:
        raise AssertionError("sub-microsecond timestamp accepted")
    lower = clock("2026-08-28T00:00:00Z")
    assert lower is not None
    fixtures = [
        dict(event_id=str(i), market_id=str(i), condition=str(i), start_us=lower + i * 300_000_000)
        for i in range(288)
    ]
    require(
        day_diagnostic(fixtures, "2026-08-28")["observed_288_grid_diagnostic"],
        "self-test positive observed count",
    )
    require(
        not day_diagnostic(fixtures[:-1], "2026-08-28")["observed_288_grid_diagnostic"],
        "missing row must not pass",
    )
    require(
        not day_diagnostic(fixtures + fixtures[:1], "2026-08-28")[
            "unique_event_market_condition_start"
        ],
        "duplicate row must not pass",
    )
    result = classify_series(
        [
            project(dict(id="1", title="Unknown five-minute test"), "series"),
            project(dict(id="2"), "series"),
        ]
    )
    require(
        result["rows_scanned"] == 2
        and result["five_minute_candidates"] == 1
        and result["unknown_or_ambiguous_candidates"] == 1
        and result["null_slug_and_title_rows"] == 1,
        "self-test all-row unknown classification",
    )
    require(
        result["candidate_samples"][0]["title"] == "Unknown five-minute test"
        and result["candidate_samples"][0]["slug"] is None
        and result["candidate_samples"][0]["recurrence"] is None,
        "candidate identity text must be explicit without fabricated values",
    )
    print("Independent review self-tests passed; no network requests")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        run()
