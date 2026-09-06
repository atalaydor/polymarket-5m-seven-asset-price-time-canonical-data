"""Inspect durable projected catalog evidence on Linux; publish only small diagnostics."""

from __future__ import annotations

import json
import os
import platform
from collections import Counter
from typing import Any

from pflow.catalog_enumerate import ENUM_SCHEMA, specification, validate
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import canonical, sha

PRIOR_COMMIT = "65b474aad96b6adde2901ba4d5b2944dd9353ce5"


def run() -> None:
    if platform.system() != "Linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("full catalog inspection requires Actions Linux")
    names = ["series-ascending", "series-descending"] + [
        f"2026-08-{day}-{group}-{closed}"
        for day in ("25", "27", "28")
        for group in ("markets", "events")
        for closed in ("true", "false")
    ]
    streams: list[dict[str, Any]] = []
    for name in names:
        spec = specification(name)
        identity = sha(canonical(dict(schema=ENUM_SCHEMA, specification=spec, commit=PRIOR_COMMIT)))
        tag = "catalog-enumeration-" + identity
        release = api("releases/tags/" + tag)
        if release is None or release["draft"]:
            streams.append(dict(name=name, status="NO_SEALED_STREAM"))
            continue
        verify_release(release)
        asset = next(a for a in release["assets"] if a["name"].endswith("--catalog-stream.json"))
        raw = read_asset(asset)
        report = json.loads(raw)
        validate(report, spec, PRIOR_COMMIT)
        result = report["evidence"]["scans"][0]
        rows = result["rows"]
        end_dates = sorted(row["endDate"] for row in rows if row.get("endDate"))

        def minimal(row: dict[str, Any]) -> dict[str, Any]:
            return {k: row[k] for k in ("id", "slug", "endDate") if k in row}

        streams.append(
            dict(
                name=name,
                status="SEALED_DIAGNOSTIC",
                release_id=release["id"],
                tag=tag,
                asset_sha256=sha(raw),
                rows=len(rows),
                pages=len(result["pages"]),
                claimed_terminal=result["terminal_observed"],
                error=result["error"],
                source_bytes=report["evidence"]["downloaded_bytes"],
                first_rows=[minimal(row) for row in rows[:3]],
                last_rows=[minimal(row) for row in rows[-3:]],
                earliest_end=end_dates[0] if end_dates else None,
                latest_end=end_dates[-1] if end_dates else None,
                null_end=sum(row.get("endDate") is None for row in rows),
                end_day_counts=dict(Counter(d[:10] for d in end_dates)),
                series_inventory=[
                    {k: row[k] for k in ("id", "slug", "title", "recurrence", "closed", "archived")}
                    for row in rows
                ]
                if spec["kind"] == "series"
                else [],
            )
        )
    evidence = dict(
        schema="polymarket-catalog-inspection.v1",
        commit=current_commit(),
        inspected_transform=PRIOR_COMMIT,
        streams=streams,
        expected_catalog_certified=False,
        research_import_allowed=False,
        series_short_page_terminal_claim_invalidated=True,
    )
    raw = canonical(evidence)
    tag = "catalog-inspection-" + sha(raw)
    release = publish(
        tag, {"inspection.json": raw}, current_commit(), "Catalog query behavior inspection"
    )
    print(
        canonical(dict(tag=tag, release_id=release["id"], sha256=sha(raw), bytes=len(raw))).decode()
    )


if __name__ == "__main__":
    run()
