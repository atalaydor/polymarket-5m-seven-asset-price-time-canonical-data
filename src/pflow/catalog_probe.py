"""Bounded first-party catalog capability evidence; never price/research authority."""

from __future__ import annotations

import json
import os
import platform
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from pflow.model import ASSETS, validate_quote
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import canonical, sha

GAMMA = "https://gamma-api.polymarket.com"
PRIOR_TAG = "source-probe-8e650e70605997c050bf7d32ef898e8077105fe19ebaa21c1089d07b0a1cc31c"
PRIOR_SHA = "61347d5fdd408676adff2d40a5224934e5b646175a59d2c562a6b042ec355173"
SCHEMA = "polymarket-catalog-capability-probe.v1"
SCOPE = "bounded first-party metadata capability probe; no day/window authority"
SCAN_SCOPE = "returned catalog pages only; not certified expected membership"
TEXT = {
    "market": (
        "id",
        "question",
        "conditionId",
        "slug",
        "startDate",
        "endDate",
        "eventStartTime",
        "createdAt",
        "updatedAt",
        "closedTime",
        "pastSlugs",
        "questionID",
        "acceptingOrdersTimestamp",
        "scheduledDeploymentTimestamp",
        "deployingTimestamp",
    ),
    "event": (
        "id",
        "slug",
        "ticker",
        "title",
        "startDate",
        "endDate",
        "startTime",
        "creationDate",
        "createdAt",
        "updatedAt",
        "closedTime",
        "seriesSlug",
        "eventDate",
        "scheduledDeploymentTimestamp",
        "deployingTimestamp",
    ),
    "series": (
        "id",
        "slug",
        "ticker",
        "title",
        "seriesType",
        "recurrence",
        "createdAt",
        "updatedAt",
        "publishedAt",
    ),
}
BOOL = (
    "active",
    "closed",
    "archived",
    "restricted",
    "ready",
    "funded",
    "acceptingOrders",
    "pendingDeployment",
    "deploying",
    "automaticallyActive",
    "manualActivation",
)
DOCS = (
    "https://docs.polymarket.com/api-reference/markets/list-markets-keyset-pagination.md",
    "https://docs.polymarket.com/api-reference/events/list-events-keyset-pagination.md",
    "https://docs.polymarket.com/api-reference/markets/list-markets.md",
    "https://docs.polymarket.com/api-reference/events/list-events.md",
    "https://docs.polymarket.com/api-reference/series/list-series.md",
    "https://docs.polymarket.com/market-data/market-details.md",
    "https://docs.polymarket.com/concepts/markets-events.md",
)


def relation(value: Any, kind: str) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or len(value) > 1000
        or any(not isinstance(item, dict) for item in value)
    ):
        raise ValueError("invalid catalog relation")
    return [project(item, kind, False) for item in value]


def project(row: dict[str, Any], kind: str, links: bool = True) -> dict[str, Any]:
    """No unknown source key, result, price, depth or raw response survives this boundary."""
    result: dict[str, Any] = {}
    for field in TEXT[kind]:
        value = row.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > 2048):
            raise ValueError("invalid catalog text field: " + field)
        result[field] = value
    for field in BOOL:
        value = row.get(field)
        if value is not None and type(value) is not bool:
            raise ValueError("invalid catalog boolean: " + field)
        result[field] = value
    if kind == "market":
        for field in ("outcomes", "clobTokenIds"):
            value = row.get(field)
            if isinstance(value, str):
                value = json.loads(value)
            if value is not None and (
                not isinstance(value, list)
                or len(value) > 32
                or any(not isinstance(item, str) or len(item) > 256 for item in value)
            ):
                raise ValueError("invalid catalog identity array")
            result[field] = value
        if links:
            result["events"] = relation(row.get("events"), "event")
    if kind == "event":
        result["series"] = relation(row.get("series"), "series")
        if links:
            result["markets"] = relation(row.get("markets"), "market")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        # Record redirect responses as unavailable; no redirect origin is contacted.
        return None


class Reader:
    def __init__(self) -> None:
        self.ledger: list[dict[str, Any]] = []
        self.bytes = 0
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, url: str) -> tuple[Any, dict[str, Any]]:
        if platform.system() != "Linux" or os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("catalog acquisition requires GitHub-hosted Linux")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.netloc not in (
            "gamma-api.polymarket.com",
            "docs.polymarket.com",
        ):
            raise ValueError("catalog request origin forbidden")
        if len(self.ledger) >= 100 or self.bytes >= 64_000_000:
            raise ValueError("catalog scout total budget exhausted")
        begin = time.monotonic_ns()
        observed = datetime.now(UTC).isoformat()
        try:
            response = self.opener.open(url, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            bound = min(8_000_000, 64_000_000 - self.bytes)
            # The sentinel byte itself is counted inside the total cap.
            raw = response.read(bound)
            if len(raw) >= bound:
                raise ValueError("catalog response exceeds bound")
            status = response.status
            date = response.headers.get("Date")
        self.bytes += len(raw)
        entry = {
            "url": url,
            "observed_at": observed,
            "http_date": date,
            "status": status,
            "bytes": len(raw),
            "sha256": sha(raw),
            "network_ns": time.monotonic_ns() - begin,
        }
        self.ledger.append(entry)
        if status != 200 or parsed.netloc == "docs.polymarket.com":
            return None, entry
        return json.loads(raw), entry


def scan(
    reader: Reader, path: str, parameters: dict[str, str], kind: str, max_pages: int
) -> dict[str, Any]:
    keyset = path.endswith("/keyset")
    rows: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    seen_cursors: set[str] = set()
    limit = int(parameters["limit"])
    query = dict(parameters)
    terminal = False
    error: str | None = None
    for index in range(max_pages):
        if not keyset:
            query["offset"] = str(index * limit)
        url = GAMMA + path + "?" + urllib.parse.urlencode(query)
        data, evidence = reader.get(url)
        page: dict[str, Any] = {"request": evidence, "row_count": None, "next_cursor": None}
        pages.append(page)
        if evidence["status"] != 200:
            error = "HTTP_" + str(evidence["status"])
            break
        source_rows = data.get(kind + "s") if keyset and isinstance(data, dict) else data
        if not isinstance(source_rows, list) or len(source_rows) > limit:
            raise ValueError("catalog page shape/limit invalid")
        page["row_count"] = len(source_rows)
        rows.extend(project(item, kind) for item in source_rows)
        if keyset:
            cursor = data.get("next_cursor")
            if cursor is not None and (not isinstance(cursor, str) or not cursor):
                raise ValueError("invalid next_cursor")
            page["next_cursor"] = cursor
            if cursor is None:
                terminal = True
                break
            if cursor in seen_cursors or len(source_rows) != limit:
                raise ValueError("repeated cursor or short nonterminal page")
            seen_cursors.add(cursor)
            query["after_cursor"] = cursor
        elif len(source_rows) < limit:
            terminal = True
            break
    ids = [row["id"] for row in rows]
    return {
        "path": path,
        "parameters": parameters,
        "pages": pages,
        "rows": rows,
        "terminal_observed": terminal,
        "error": error,
        "page_budget": max_pages,
        "duplicate_ids": sorted({item for item in ids if ids.count(item) > 1}),
        "scope": SCAN_SCOPE,
    }


def keys(value: dict[str, Any], allowed: str) -> None:
    if not isinstance(value, dict) or value.keys() != set(allowed.split()):
        raise ValueError("strict catalog evidence field allowlist")


def prior_identities(prior: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for asset in ASSETS:
        up, down = (prior["quote_samples"][asset + ":" + side] for side in ("UP", "DOWN"))
        validate_quote(up)
        validate_quote(down)
        for field in ("asset", "market", "start_us", "end_us"):
            if up[field] != down[field]:
                raise ValueError("prior sides do not establish same market")
        result[asset] = {
            "asset": asset,
            "market": up["market"],
            "start_us": up["start_us"],
            "end_us": up["end_us"],
            "up_token": up["token"],
            "down_token": down["token"],
            "slug": f"{asset.lower()}-updown-5m-{up['start_us'] // 1_000_000}",
        }
    return result


def validate_report(report: dict[str, Any], identity: str) -> None:
    keys(
        report,
        "schema identity commit workflow_run_id prior_tag prior_sha256 semantic_profile "
        "profile_version research_import_allowed expected_catalog_certified scans slug_checks "
        "requests downloaded_bytes network_ns foreign_price_outcome_depth_fields_retained scope",
    )
    if (
        report.get("schema") != SCHEMA
        or report.get("identity") != identity
        or report.get("research_import_allowed") is not False
        or report.get("expected_catalog_certified") is not False
        or report.get("foreign_price_outcome_depth_fields_retained") is not False
        or report.get("semantic_profile") != "PENDULUMFLOW_V3_OBSERVED"
        or report.get("profile_version") != 1
        or report.get("prior_tag") != PRIOR_TAG
        or report.get("prior_sha256") != PRIOR_SHA
        or report.get("scope") != SCOPE
        or type(report.get("profile_version")) is not int
    ):
        raise ValueError("catalog scout cannot be promoted or substituted")
    if report["workflow_run_id"] is not None and (
        not isinstance(report["workflow_run_id"], str) or not report["workflow_run_id"].isdigit()
    ):
        raise ValueError("invalid workflow provenance")
    if not re.fullmatch("[0-9a-f]{40}", report["commit"]) or identity != sha(
        canonical({"schema": SCHEMA, "commit": report["commit"], "prior_sha256": PRIOR_SHA})
    ):
        raise ValueError("catalog generation identity mismatch")
    for request in report["requests"]:
        keys(request, "url observed_at http_date status bytes sha256 network_ns")
        if not re.fullmatch("[0-9a-f]{64}", request["sha256"]):
            raise ValueError("invalid response digest")
        if any(
            type(request[key]) is not int or request[key] < 0
            for key in ("status", "bytes", "network_ns")
        ):
            raise ValueError("invalid request measurement")
        if any(
            request[key] is not None and not isinstance(request[key], str)
            for key in ("url", "observed_at", "http_date")
        ):
            raise ValueError("invalid request provenance")
    if report["downloaded_bytes"] != sum(x["bytes"] for x in report["requests"]) or (
        report["network_ns"] != sum(x["network_ns"] for x in report["requests"])
    ):
        raise ValueError("request ledger total mismatch")
    for result in report["scans"]:
        keys(
            result,
            "path parameters pages rows terminal_observed error page_budget duplicate_ids scope",
        )
        if result["scope"] != SCAN_SCOPE:
            raise ValueError("catalog scan scope changed")
        if result["path"] not in (
            "/markets",
            "/markets/keyset",
            "/events",
            "/events/keyset",
            "/series",
        ):
            raise ValueError("unexpected catalog route")
        allowed_params = {
            "limit",
            "order",
            "ascending",
            "closed",
            "exclude_events",
            "end_date_min",
            "end_date_max",
        }
        if not result["parameters"].keys() <= allowed_params or any(
            not isinstance(v, str) for v in result["parameters"].values()
        ):
            raise ValueError("unexpected catalog query")
        if type(result["terminal_observed"]) is not bool or type(result["page_budget"]) is not int:
            raise ValueError("invalid pagination state")
        if result["error"] is not None and not re.fullmatch("HTTP_[0-9]{3}", result["error"]):
            raise ValueError("invalid catalog error")
        if any(not isinstance(item, str) for item in result["duplicate_ids"]):
            raise ValueError("invalid duplicate identity")
        for page in result["pages"]:
            keys(page, "request row_count next_cursor")
            if page["request"] not in report["requests"]:
                raise ValueError("page lacks request provenance")
            if page["row_count"] is not None and type(page["row_count"]) is not int:
                raise ValueError("invalid page row count")
            if page["next_cursor"] is not None and not isinstance(page["next_cursor"], str):
                raise ValueError("invalid pagination cursor")
        kind = (
            "series"
            if result["path"] == "/series"
            else ("event" if result["path"].startswith("/events") else "market")
        )
        for row in result["rows"]:
            if project(row, kind) != row:
                raise ValueError("non-catalog field in published row")
    for item in report["slug_checks"]:
        keys(item, "asset prior_mapping request market")
        keys(item["prior_mapping"], "asset market start_us end_us up_token down_token slug")
        mapping = item["prior_mapping"]
        if (
            item["asset"] not in ASSETS
            or mapping["asset"] != item["asset"]
            or item["request"] not in report["requests"]
            or not re.fullmatch("[0-9a-f]{64}", mapping["market"])
            or any(
                not isinstance(mapping[x], str) or not mapping[x].isdigit()
                for x in ("up_token", "down_token")
            )
            or any(type(mapping[x]) is not int for x in ("start_us", "end_us"))
        ):
            raise ValueError("invalid prior identity evidence")
        if (
            mapping["slug"]
            != f"{item['asset'].lower()}-updown-5m-{mapping['start_us'] // 1_000_000}"
        ):
            raise ValueError("prior lookup slug hypothesis changed")
        if item["market"] is not None and project(item["market"], "market") != item["market"]:
            raise ValueError("non-catalog field in slug check")


def run() -> None:
    commit = current_commit()
    identity = sha(canonical({"schema": SCHEMA, "commit": commit, "prior_sha256": PRIOR_SHA}))
    tag = "catalog-probe-" + identity
    existing = api("releases/tags/" + tag)
    if existing is not None and existing["assets"]:
        if len(existing["assets"]) != 1:
            raise ValueError("unexpected existing catalog report inventory")
        raw = read_asset(existing["assets"][0], draft=existing["draft"])
        validate_report(json.loads(raw), identity)
        release = publish(tag, {"catalog-report.json": raw}, commit, "Catalog capability evidence")
        print(canonical({"reused_release": release["id"], "new_catalog_bytes": 0}).decode())
        return
    old = api("releases/tags/" + PRIOR_TAG)
    verify_release(old)
    raw = read_asset(old["assets"][0])
    if sha(raw) != PRIOR_SHA:
        raise ValueError("prior canary evidence pin mismatch")
    prior = json.loads(raw)
    samples = prior_identities(prior)
    reader = Reader()
    for url in DOCS:
        reader.get(url)
    slug_checks: list[dict[str, Any]] = []
    for asset, mapping in sorted(samples.items()):
        data, evidence = reader.get(GAMMA + "/markets/slug/" + mapping["slug"])
        slug_checks.append(
            {
                "asset": asset,
                "prior_mapping": mapping,
                "request": evidence,
                "market": project(data, "market") if isinstance(data, dict) else None,
            }
        )
    scans = []
    for closed in ("false", "true"):
        common = {"limit": "100", "order": "id", "ascending": "true", "closed": closed}
        for path in ("/markets/keyset", "/markets", "/events/keyset", "/events"):
            params = dict(common)
            params.update(
                {
                    "end_date_min": "2026-08-28T00:00:00Z",
                    "end_date_max": "2026-08-29T00:05:00Z",
                }
            )
            scans.append(scan(reader, path, params, "event" if "events" in path else "market", 2))
        series_params = dict(common, exclude_events="true")
        scans.append(scan(reader, "/series", series_params, "series", 10))
    report = {
        "schema": SCHEMA,
        "identity": identity,
        "commit": commit,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "prior_tag": PRIOR_TAG,
        "prior_sha256": PRIOR_SHA,
        "semantic_profile": "PENDULUMFLOW_V3_OBSERVED",
        "profile_version": 1,
        "research_import_allowed": False,
        "expected_catalog_certified": False,
        "scans": scans,
        "slug_checks": slug_checks,
        "requests": reader.ledger,
        "downloaded_bytes": reader.bytes,
        "network_ns": sum(item["network_ns"] for item in reader.ledger),
        "foreign_price_outcome_depth_fields_retained": False,
        "scope": SCOPE,
    }
    validate_report(report, identity)
    data = canonical(report)
    release = publish(tag, {"catalog-report.json": data}, commit, "Catalog capability evidence")
    print(
        canonical(
            {
                "release_id": release["id"],
                "tag": tag,
                "report_sha256": sha(data),
                "downloaded_bytes": reader.bytes,
                "report_bytes": len(data),
                "requests": len(reader.ledger),
                "research_import_allowed": False,
            }
        ).decode()
    )


if __name__ == "__main__":
    run()
