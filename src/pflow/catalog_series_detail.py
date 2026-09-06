"""Bounded first-party series detail route; response metadata projection only."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from pflow.catalog_probe import NoRedirect, keys, project
from pflow.catalog_targets import SERIES, SERIES_SHA, interval, series_evidence
from pflow.release import api, current_commit, publish, read_asset
from pflow.source import canonical, sha

SCHEMA = "polymarket-series-detail-diagnostic.v2"
BOUND = 128_000_000


def projection(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("series detail object required")
    events = data.get("events")
    if events is not None and (not isinstance(events, list) or len(events) > 100_000):
        raise ValueError("series detail event inventory shape/bound")
    return dict(
        series=project(data, "series"),
        events=None if events is None else [project(row, "event") for row in events],
    )


def validate(report: dict[str, Any], asset: str, commit: str) -> None:
    keys(
        report,
        "schema identity asset commit series_sha256 request metadata "
        "expected_catalog_certified research_import_allowed",
    )
    identity = sha(
        canonical(dict(schema=SCHEMA, asset=asset, commit=commit, series_sha256=SERIES_SHA))
    )
    if (
        report["schema"] != SCHEMA
        or report["identity"] != identity
        or report["asset"] != asset
        or report["commit"] != commit
        or report["series_sha256"] != SERIES_SHA
        or report["expected_catalog_certified"] is not False
        or report["research_import_allowed"] is not False
        or not re.fullmatch("[0-9a-f]{40}", commit)
    ):
        raise ValueError("detail report generation/scope mismatch")
    request = report["request"]
    keys(
        request,
        "url observed_at http_date status bytes network_ns body_complete sha256 hash_scope "
        "declared_bytes",
    )
    if request["url"] != "https://gamma-api.polymarket.com/series/" + SERIES[asset]:
        raise ValueError("detail request origin mismatch")
    if (
        any(
            type(request[k]) is not int or request[k] < 0 for k in ("status", "bytes", "network_ns")
        )
        or not 100 <= request["status"] <= 599
        or not 0 <= request["bytes"] <= BOUND
    ):
        raise ValueError("detail measurements invalid")
    if (
        type(request["body_complete"]) is not bool
        or request["body_complete"]
        != (
            request["bytes"] < BOUND
            and (request["declared_bytes"] is None or request["bytes"] == request["declared_bytes"])
        )
        or request["hash_scope"]
        != ("whole_response" if request["body_complete"] else "downloaded_prefix_only")
        or not re.fullmatch("[0-9a-f]{64}", request["sha256"])
    ):
        raise ValueError("detail partial-byte integrity claim mismatch")
    if request["declared_bytes"] is not None and (
        type(request["declared_bytes"]) is not int or request["declared_bytes"] < 0
    ):
        raise ValueError("detail declared byte length invalid")
    if not isinstance(request["observed_at"], str) or (
        request["http_date"] is not None and not isinstance(request["http_date"], str)
    ):
        raise ValueError("detail clock metadata invalid")
    metadata = report["metadata"]
    if metadata is not None:
        keys(metadata, "series events")
        if (
            not request["body_complete"]
            or request["status"] != 200
            or metadata["series"]["id"] != SERIES[asset]
        ):
            raise ValueError("detail metadata absent/identity mismatch")
        if projection(dict(metadata["series"], events=metadata["events"])) != metadata:
            raise ValueError("non-metadata field in detail authority")
    elif request["body_complete"] and request["status"] == 200:
        raise ValueError("complete successful response lacks projection")


def run(asset: str) -> None:
    if platform.system() != "Linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("series detail acquisition requires Actions Linux")
    commit = current_commit()
    identity = sha(
        canonical(dict(schema=SCHEMA, asset=asset, commit=commit, series_sha256=SERIES_SHA))
    )
    tag = "catalog-series-detail-" + identity
    existing = api("releases/tags/" + tag)
    if existing is not None and existing["assets"]:
        selected = [a for a in existing["assets"] if a["name"].endswith("--series-detail.json")]
        if len(selected) != 1:
            raise ValueError("unique detail report required")
        raw = read_asset(selected[0], draft=existing["draft"])
        report = json.loads(raw)
        if report["identity"] != identity or report["commit"] != commit:
            raise ValueError("detail generation mismatch")
    else:
        series_evidence()
        url = "https://gamma-api.polymarket.com/series/" + SERIES[asset]
        opener = urllib.request.build_opener(NoRedirect())
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "PendulumFlowCatalogProof/0.1 (public metadata research)",
                "Accept": "application/json",
            },
        )
        started = datetime.now(UTC).isoformat()
        begin = time.monotonic_ns()
        try:
            response = opener.open(request, timeout=90)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read(BOUND)
            code = response.status
            http_date = response.headers.get("Date")
            header_length = response.headers.get("Content-Length")
        network_ns = time.monotonic_ns() - begin
        declared_bytes = int(header_length) if header_length is not None else None
        complete = len(body) < BOUND and (declared_bytes is None or len(body) == declared_bytes)
        metadata = projection(json.loads(body)) if complete and code == 200 else None
        report = dict(
            schema=SCHEMA,
            identity=identity,
            asset=asset,
            commit=commit,
            series_sha256=SERIES_SHA,
            request=dict(
                url=url,
                observed_at=started,
                http_date=http_date,
                status=code,
                bytes=len(body),
                network_ns=network_ns,
                declared_bytes=declared_bytes,
                body_complete=complete,
                sha256=sha(body),
                hash_scope="whole_response" if complete else "downloaded_prefix_only",
            ),
            metadata=metadata,
            expected_catalog_certified=False,
            research_import_allowed=False,
        )
        del body
        raw = canonical(report)
    validate(report, asset, commit)
    metadata = report["metadata"]
    if (
        metadata is not None
        and projection(dict(metadata["series"], events=metadata["events"])) != metadata
    ):
        raise ValueError("non-metadata detail field")
    events = metadata["events"] if metadata else None
    identities = [interval(row, asset) for row in events] if events is not None else []
    starts = sorted(i["start_us"] for i in identities if i["start_us"] is not None)
    overview = dict(
        schema=SCHEMA,
        identity=identity,
        asset=asset,
        series_id=SERIES[asset],
        request=report["request"],
        event_count=len(events) if events is not None else None,
        earliest_start_us=starts[0] if starts else None,
        latest_start_us=starts[-1] if starts else None,
        interval_error_count=sum(bool(i["errors"]) for i in identities),
        first=identities[:2],
        last=identities[-2:],
        expected_catalog_certified=False,
        research_import_allowed=False,
    )
    release = publish(
        tag,
        {"series-detail.json": raw, "summary.json": canonical(overview)},
        commit,
        "First-party series detail evidence: " + asset,
    )
    print(canonical(dict(tag=tag, release_id=release["id"], summary=overview)).decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("asset", choices=tuple(SERIES))
    run(parser.parse_args().asset)
