"""Durable bounded first-party catalog streams, independent of V3 quote presence."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
from collections import Counter
from datetime import date, timedelta
from typing import Any

from pflow.catalog_probe import (
    PRIOR_SHA,
    PRIOR_TAG,
    SCHEMA,
    SCOPE,
    Reader,
    scan,
)
from pflow.catalog_probe import (
    validate_report as validate_scout,
)
from pflow.release import api, current_commit, publish, read_asset
from pflow.source import canonical, sha

ENUM_SCHEMA = "polymarket-catalog-enumeration.v1"
DAYS = ("2026-08-25", "2026-08-27", "2026-08-28")
TARGET_WORDS = re.compile(
    r"(bitcoin|btc|ethereum|ether|eth|solana|sol|xrp|ripple|doge|bnb|hyperliquid|hype)", re.I
)


def specification(name: str) -> dict[str, Any]:
    if name in ("series-ascending", "series-descending"):
        return dict(
            name=name,
            path="/series",
            kind="series",
            max_pages=50,
            parameters={
                "limit": "100",
                "order": "id",
                "ascending": "true" if name.endswith("ascending") else "false",
                "exclude_events": "true",
            },
        )
    match = re.fullmatch(r"(2026-08-(?:25|27|28))-(markets|events)-(true|false)", name)
    if match is None:
        raise ValueError("unknown preregistered catalog stream")
    day, group, closed = match.groups()
    return dict(
        name=name,
        path="/" + group + "/keyset",
        kind=group[:-1],
        max_pages=50,
        parameters={
            "limit": "100",
            "order": "id",
            "ascending": "true",
            "closed": closed,
            "end_date_min": day + "T00:00:00Z",
            "end_date_max": str(date.fromisoformat(day) + timedelta(days=1)) + "T00:05:00Z",
        },
    )


def stable(row: dict[str, Any], kind: str) -> dict[str, Any]:
    fields = {
        "series": ("id", "slug", "title", "seriesType", "recurrence", "createdAt"),
        "market": (
            "id",
            "slug",
            "question",
            "conditionId",
            "eventStartTime",
            "endDate",
            "outcomes",
            "clobTokenIds",
        ),
        "event": ("id", "slug", "title", "startTime", "endDate", "seriesSlug"),
    }
    result = {key: row[key] for key in fields[kind]}
    relations = {
        "series": (),
        "market": (("events", "event"),),
        "event": (("series", "series"), ("markets", "market")),
    }
    for field, child_kind in relations[kind]:
        if field in row:
            result[field] = (
                None
                if row[field] is None
                else sorted(
                    [stable(child, child_kind) for child in row[field]],
                    key=lambda value: canonical(value),
                )
            )
    return result


def summary(report: dict[str, Any]) -> dict[str, Any]:
    spec = report["specification"]
    result = report["evidence"]["scans"][0]
    rows = result["rows"]
    candidates = []
    counts: dict[str, int] = {}
    for row in rows:
        slug = row.get("slug") or ""
        text = " ".join(
            str(row.get(key) or "") for key in ("slug", "title", "question", "recurrence")
        )
        if spec["kind"] == "series":
            if TARGET_WORDS.search(text):
                candidates.append(stable(row, "series"))
        else:
            match = re.fullmatch(r"(btc|eth|sol|xrp|doge|bnb|hype)-updown-5m-([0-9]{10})", slug)
            if match:
                asset = match[1].upper()
                counts[asset] = counts.get(asset, 0) + 1
                if sum(1 for item in candidates if item["slug"].startswith(match[1] + "-")) < 2:
                    candidates.append(stable(row, spec["kind"]))
    return dict(
        schema="polymarket-catalog-stream-summary.v1",
        identity=report["identity"],
        commit=report["commit"],
        name=spec["name"],
        rows=len(rows),
        pages=len(result["pages"]),
        terminal_observed=result["terminal_observed"],
        error=result["error"],
        duplicate_ids=result["duplicate_ids"],
        stable_identity_sha256=sha(
            canonical(
                sorted([stable(row, spec["kind"]) for row in rows], key=lambda x: canonical(x))
            )
        ),
        target_slug_counts_diagnostic_only=counts,
        candidate_identity_samples=candidates,
        downloaded_bytes=report["evidence"]["downloaded_bytes"],
        network_ns=report["evidence"]["network_ns"],
        expected_catalog_certified=False,
        research_import_allowed=False,
    )


def validate(report: dict[str, Any], spec: dict[str, Any], commit: str) -> None:
    if report.keys() != {"schema", "identity", "commit", "specification", "evidence"}:
        raise ValueError("strict enumeration report fields")
    identity = sha(canonical(dict(schema=ENUM_SCHEMA, specification=spec, commit=commit)))
    if (
        report["schema"] != ENUM_SCHEMA
        or report["identity"] != identity
        or report["commit"] != commit
        or report["specification"] != spec
    ):
        raise ValueError("enumeration generation mismatch")
    evidence = report["evidence"]
    validate_scout(
        evidence, sha(canonical(dict(schema=SCHEMA, commit=commit, prior_sha256=PRIOR_SHA)))
    )
    if len(evidence["scans"]) != 1 or evidence["slug_checks"]:
        raise ValueError("enumeration stream inventory mismatch")
    stream = evidence["scans"][0]
    if stream["path"] != spec["path"] or stream["parameters"] != spec["parameters"]:
        raise ValueError("enumeration query changed")
    if stream["page_budget"] != spec["max_pages"]:
        raise ValueError("enumeration bound changed")
    pages = stream["pages"]
    if not 1 <= len(pages) <= spec["max_pages"] or evidence["requests"] != [
        page["request"] for page in pages
    ]:
        raise ValueError("enumeration request/page ledger mismatch")
    query = dict(spec["parameters"])
    keyset = spec["path"].endswith("/keyset")
    count = 0
    terminal = False
    error = None
    cursors: set[str] = set()
    for index, page in enumerate(pages):
        if terminal or error is not None:
            raise ValueError("pages after terminal/error")
        if not keyset:
            query["offset"] = str(index * int(query["limit"]))
        expected_url = "https://gamma-api.polymarket.com" + spec["path"] + "?"
        expected_url += urllib.parse.urlencode(query)
        if page["request"]["url"] != expected_url:
            raise ValueError("pagination request chain mismatch")
        if page["request"]["status"] != 200:
            if page["row_count"] is not None or page["next_cursor"] is not None:
                raise ValueError("failed page has catalog rows")
            error = "HTTP_" + str(page["request"]["status"])
            continue
        n = page["row_count"]
        if type(n) is not int or not 0 <= n <= int(query["limit"]):
            raise ValueError("invalid page row count")
        count += n
        cursor = page["next_cursor"]
        if keyset:
            if cursor is None:
                terminal = True
            elif not cursor or cursor in cursors or n != int(query["limit"]):
                raise ValueError("invalid pagination cursor/limit")
            else:
                cursors.add(cursor)
                query["after_cursor"] = cursor
        else:
            if cursor is not None:
                raise ValueError("offset page has cursor")
            terminal = n < int(query["limit"])
    ids = [row["id"] for row in stream["rows"]]
    if any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("enumeration row lacks identity")
    duplicates = sorted(key for key, n in Counter(ids).items() if n > 1)
    if (
        count != len(ids)
        or stream["duplicate_ids"] != duplicates
        or stream["terminal_observed"] is not terminal
        or stream["error"] != error
        or (not terminal and error is None and len(pages) != spec["max_pages"])
    ):
        raise ValueError("pagination closure/accounting mismatch")


def run(name: str) -> None:
    spec = specification(name)
    commit = current_commit()
    identity = sha(canonical(dict(schema=ENUM_SCHEMA, specification=spec, commit=commit)))
    tag = "catalog-enumeration-" + identity
    existing = api("releases/tags/" + tag)
    if existing is not None and existing["assets"]:
        candidates = [a for a in existing["assets"] if a["name"].endswith("--catalog-stream.json")]
        if len(candidates) != 1:
            raise ValueError("no unique durable catalog stream")
        raw = read_asset(candidates[0], draft=existing["draft"])
        report = json.loads(raw)
        validate(report, spec, commit)
        release = publish(
            tag,
            {"catalog-stream.json": raw, "summary.json": canonical(summary(report))},
            commit,
            "Catalog enumeration evidence: " + name,
        )
        print(canonical(dict(reused_release=release["id"], new_catalog_bytes=0)).decode())
        return
    reader = Reader()
    reader.opener.addheaders = [
        ("User-Agent", "PendulumFlowCatalogProof/0.1 (public metadata research)"),
        ("Accept", "application/json"),
    ]
    result = scan(reader, spec["path"], spec["parameters"], spec["kind"], spec["max_pages"])
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
        scans=[result],
        slug_checks=[],
        requests=reader.ledger,
        downloaded_bytes=reader.bytes,
        network_ns=sum(item["network_ns"] for item in reader.ledger),
        foreign_price_outcome_depth_fields_retained=False,
        scope=SCOPE,
    )
    report = dict(
        schema=ENUM_SCHEMA, identity=identity, commit=commit, specification=spec, evidence=evidence
    )
    validate(report, spec, commit)
    overview = summary(report)
    release = publish(
        tag,
        {"catalog-stream.json": canonical(report), "summary.json": canonical(overview)},
        commit,
        "Catalog enumeration evidence: " + name,
    )
    print(canonical(dict(release_id=release["id"], tag=tag, summary=overview)).decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stream")
    args = parser.parse_args()
    run(args.stream)
