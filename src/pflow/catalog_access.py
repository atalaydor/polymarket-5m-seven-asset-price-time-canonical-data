"""Remaining documented catalog routes, metadata-only and without denial bypass."""

from __future__ import annotations

import http.client
import json
import os
import platform
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any

from pflow.catalog_probe import (
    GAMMA,
    PRIOR_SHA,
    PRIOR_TAG,
    NoRedirect,
    keys,
    prior_identities,
    project,
)
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import canonical, sha

SCHEMA = "polymarket-catalog-route-access.v1"
HOSTS = {"gamma-api.polymarket.com", "clob.polymarket.com", "polymarket.com", "polygon-rpc.com"}
HEADERS = (
    "Content-Type",
    "Server",
    "Date",
    "Retry-After",
    "Via",
    "X-Cache",
    "X-Mitmproxy-Blocked-Reason",
)
SCOPE = "catalog route access only; no exhaustive catalog or research authority"
RPC_BODY = canonical({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})


def denial_class(raw: bytes) -> str:
    if raw.strip().lower() in (
        b"permission denied",
        b"access denied",
        b"forbidden",
        b"request forbidden",
    ):
        return "ACCESS_DENIED"
    return "UNCLASSIFIED_HTTP_ERROR"


def clob(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "condition_id",
        "question_id",
        "market_slug",
        "question",
        "end_date_iso",
        "game_start_time",
    ):
        value = row.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > 2048):
            raise ValueError("invalid CLOB identity scalar")
        result[key] = value
    for key in ("active", "closed", "archived", "accepting_orders", "enable_order_book"):
        value = row.get(key)
        if value is not None and type(value) is not bool:
            raise ValueError("invalid CLOB listing flag")
        result[key] = value
    tokens = row.get("tokens")
    if tokens is not None:
        if not isinstance(tokens, list) or len(tokens) > 32:
            raise ValueError("invalid CLOB token relation")
        tokens = [{key: item.get(key) for key in ("token_id", "outcome")} for item in tokens]
        if any(
            value is not None and (not isinstance(value, str) or len(value) > 256)
            for item in tokens
            for value in item.values()
        ):
            raise ValueError("invalid CLOB token identity")
    result["tokens"] = tokens
    return result


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.capture = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)


def projected_body(kind: str, raw: bytes) -> Any:
    if kind == "robots":
        urls = []
        for line in raw.decode("utf-8").splitlines():
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme == "https" and parsed.hostname == "polymarket.com":
                    urls.append(url)
        return {"advertised_sitemaps": urls[:50]}
    if kind == "web":
        page = Page()
        page.feed(raw.decode("utf-8"))
        rows: list[dict[str, Any]] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                if "conditionId" in value and "slug" in value:
                    rows.append(project(value, "market"))
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        if page.parts:
            walk(json.loads("".join(page.parts)))
        return {"embedded_catalog_rows": rows, "next_data_present": bool(page.parts)}
    data = json.loads(raw)
    if kind == "gamma":
        if not isinstance(data, list) or len(data) > 1:
            raise ValueError("Gamma access probe limit ignored")
        return {"series": [project(item, "series") for item in data]}
    if kind == "clob_list":
        if not isinstance(data.get("data"), list) or len(data["data"]) > 2000:
            raise ValueError("CLOB capability page bound")
        return {
            "rows": [clob(item) for item in data["data"]],
            "next_cursor": data.get("next_cursor"),
            "count": data.get("count"),
            "limit": data.get("limit"),
        }
    if kind == "clob_token":
        # The documented clean identity lookup has no price or winning-result input.
        return {
            key: data.get(key) for key in ("condition_id", "primary_token_id", "secondary_token_id")
        }
    if kind == "geo":
        return {key: data.get(key) for key in ("blocked", "country", "region")}
    if kind == "rpc":
        return {
            "chain_id": data.get("result"),
            "jsonrpc": data.get("jsonrpc"),
            "id": data.get("id"),
        }
    raise ValueError("unknown metadata route")


def validate_result(kind: str, result: Any) -> None:
    if result is None:
        return
    if kind == "gamma":
        keys(result, "series")
        if any(project(item, "series") != item for item in result["series"]):
            raise ValueError("Gamma projection mismatch")
    elif kind == "clob_list":
        keys(result, "rows next_cursor count limit")
        if any(clob(row) != row for row in result["rows"]):
            raise ValueError("CLOB extra fields")
        if result["next_cursor"] is not None and not isinstance(result["next_cursor"], str):
            raise ValueError("invalid CLOB cursor")
        if any(
            result[key] is not None and type(result[key]) is not int for key in ("count", "limit")
        ):
            raise ValueError("invalid CLOB pagination count")
    elif kind == "clob_token":
        keys(result, "condition_id primary_token_id secondary_token_id")
        if not isinstance(result["condition_id"], str) or not re.fullmatch(
            "0x[0-9a-fA-F]{64}", result["condition_id"]
        ):
            raise ValueError("invalid condition identity")
        # Actual shape must be identity-only. Unknown structures stay rejected.
        if any(
            not isinstance(result[key], str) or not result[key].isdigit()
            for key in ("primary_token_id", "secondary_token_id")
        ):
            raise ValueError("unexpected token lookup shape")
    elif kind == "web":
        keys(result, "embedded_catalog_rows next_data_present")
        if type(result["next_data_present"]) is not bool or any(
            project(row, "market") != row for row in result["embedded_catalog_rows"]
        ):
            raise ValueError("web metadata projection mismatch")
    elif kind == "robots":
        keys(result, "advertised_sitemaps")
        if any(
            not isinstance(url, str) or not url.startswith("https://polymarket.com/")
            for url in result["advertised_sitemaps"]
        ):
            raise ValueError("invalid advertised sitemap")
    elif kind == "geo":
        keys(result, "blocked country region")
        if type(result["blocked"]) is not bool or any(
            result[key] is not None and not isinstance(result[key], str)
            for key in ("country", "region")
        ):
            raise ValueError("invalid access geography")
    elif kind == "rpc":
        keys(result, "chain_id jsonrpc id")
        if result != {"chain_id": "0x89", "jsonrpc": "2.0", "id": 1}:
            raise ValueError("Polygon transport identity not established")
    else:
        raise ValueError("unknown result kind")


def request(url: str, kind: str, remaining: int) -> dict[str, Any]:
    if remaining <= 0:
        raise ValueError("no remaining response budget; no request issued")
    if platform.system() != "Linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("catalog network probes require GitHub-hosted Linux")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in HOSTS:
        raise ValueError("unapproved route origin")
    body = RPC_BODY if kind == "rpc" else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "PendulumFlowCatalogProof/0.1 (public metadata research)",
            "Accept": "application/json"
            if kind not in ("web", "robots")
            else "text/html,text/plain",
            **({"Content-Type": "application/json"} if body else {}),
        },
    )
    started = datetime.now(UTC).isoformat()
    begin = time.monotonic_ns()
    raw = b""
    status = 0
    headers: dict[str, Any] = dict.fromkeys(HEADERS)
    complete = False
    processing = "TRANSPORT_ERROR"
    try:
        try:
            response = urllib.request.build_opener(NoRedirect()).open(req, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.status
            headers = {key: response.headers.get(key) for key in HEADERS}
            raw = response.read(min(8_000_000, remaining))
            complete = len(raw) < min(8_000_000, remaining)
        processing = (
            "OK" if complete and status == 200 else ("HTTP_ERROR" if complete else "BODY_CAP")
        )
    except (OSError, http.client.HTTPException):
        pass
    network_ns = time.monotonic_ns() - begin
    result = None
    if processing == "OK":
        try:
            result = projected_body(kind, raw)
            validate_result(kind, result)
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            result = None
            processing = "UNSUPPORTED_METADATA_SHAPE"
    return {
        "url": url,
        "kind": kind,
        "method": "POST" if body else "GET",
        "request_sha256": sha(body) if body else None,
        "observed_at": started,
        "status": status,
        "headers": headers,
        "bytes": len(raw),
        "sha256": sha(raw),
        "network_ns": network_ns,
        "body_complete": complete,
        "processing_status": processing,
        "denial_class": denial_class(raw) if status != 200 else None,
        "result": result,
    }


def validate_report(report: dict[str, Any]) -> None:
    keys(
        report,
        "schema identity commit workflow_run_id prior_tag prior_sha256 requests "
        "downloaded_bytes network_ns research_import_allowed expected_catalog_certified scope "
        "budget_exhausted",
    )
    if (
        report["schema"] != SCHEMA
        or report["research_import_allowed"] is not False
        or report["expected_catalog_certified"] is not False
        or report["scope"] != SCOPE
        or report["prior_tag"] != PRIOR_TAG
        or report["prior_sha256"] != PRIOR_SHA
    ):
        raise ValueError("access diagnostic authority changed")
    if (
        not isinstance(report["commit"], str)
        or not re.fullmatch("[0-9a-f]{40}", report["commit"])
        or not isinstance(report["workflow_run_id"], str)
        or not report["workflow_run_id"].isdigit()
        or type(report["budget_exhausted"]) is not bool
    ):
        raise ValueError("invalid access report provenance")
    expected = sha(
        canonical({"schema": SCHEMA, "commit": report["commit"], "prior_sha256": PRIOR_SHA})
    )
    if report["identity"] != expected:
        raise ValueError("access diagnostic generation mismatch")
    for item in report["requests"]:
        keys(
            item,
            "url kind method request_sha256 observed_at status headers bytes sha256 "
            "network_ns body_complete processing_status denial_class result",
        )
        if item["kind"] not in ("gamma", "clob_list", "clob_token", "geo", "robots", "web", "rpc"):
            raise ValueError("invalid route kind")
        if (
            item["processing_status"]
            not in ("OK", "HTTP_ERROR", "BODY_CAP", "TRANSPORT_ERROR", "UNSUPPORTED_METADATA_SHAPE")
            or type(item["body_complete"]) is not bool
        ):
            raise ValueError("invalid access attempt status")
        if item["processing_status"] != "OK" and item["result"] is not None:
            raise ValueError("failed access attempt cannot yield catalog data")
        if any(
            type(item[key]) is not int or item[key] < 0 for key in ("status", "bytes", "network_ns")
        ):
            raise ValueError("invalid access attempt measurements")
        if (
            not isinstance(item["url"], str)
            or urllib.parse.urlparse(item["url"]).netloc not in HOSTS
        ):
            raise ValueError("invalid recorded request origin")
        if urllib.parse.urlparse(item["url"]).scheme != "https":
            raise ValueError("invalid recorded request scheme")
        if not isinstance(item["observed_at"], str):
            raise ValueError("invalid observation time")
        if datetime.fromisoformat(item["observed_at"]).utcoffset() != timedelta(0):
            raise ValueError("UTC observation time required")
        if item["method"] != ("POST" if item["kind"] == "rpc" else "GET"):
            raise ValueError("invalid catalog request method")
        if item["request_sha256"] != (sha(RPC_BODY) if item["kind"] == "rpc" else None):
            raise ValueError("unexpected catalog request body")
        keys(item["headers"], " ".join(HEADERS))
        if any(
            value is not None and (not isinstance(value, str) or len(value) > 512)
            for value in item["headers"].values()
        ):
            raise ValueError("invalid response header metadata")
        if item["denial_class"] not in (None, "ACCESS_DENIED", "UNCLASSIFIED_HTTP_ERROR"):
            raise ValueError("opaque denial payload rejected")
        if not re.fullmatch("[0-9a-f]{64}", item["sha256"]):
            raise ValueError("invalid response digest")
        validate_result(item["kind"], item["result"])
    if report["downloaded_bytes"] != sum(item["bytes"] for item in report["requests"]):
        raise ValueError("byte ledger mismatch")
    if report["network_ns"] != sum(item["network_ns"] for item in report["requests"]):
        raise ValueError("time ledger mismatch")


def run() -> None:
    commit = current_commit()
    identity = sha(canonical({"schema": SCHEMA, "commit": commit, "prior_sha256": PRIOR_SHA}))
    tag = "catalog-access-" + identity
    existing = api("releases/tags/" + tag)
    if existing and existing["assets"]:
        if len(existing["assets"]) != 1:
            raise ValueError("unexpected access checkpoint inventory")
        data = read_asset(existing["assets"][0], draft=existing["draft"])
        report = json.loads(data)
        validate_report(report)
        if report["identity"] != identity:
            raise ValueError("wrong access checkpoint")
        publish(tag, {"access-report.json": data}, commit, "Catalog route access evidence")
        print("Verified existing access checkpoint; zero new source requests")
        return
    old = api("releases/tags/" + PRIOR_TAG)
    verify_release(old)
    data = read_asset(old["assets"][0])
    if sha(data) != PRIOR_SHA:
        raise ValueError("prior identity pin mismatch")
    seeds = prior_identities(json.loads(data))
    routes = [
        (GAMMA + "/series?limit=1&exclude_events=true", "gamma"),
        ("https://clob.polymarket.com/markets?next_cursor=MA%3D%3D", "clob_list"),
        ("https://clob.polymarket.com/simplified-markets?next_cursor=MA%3D%3D", "clob_list"),
        ("https://polymarket.com/api/geoblock", "geo"),
        ("https://polymarket.com/robots.txt", "robots"),
        ("https://polymarket.com/event/" + seeds["BTC"]["slug"], "web"),
        ("https://polygon-rpc.com", "rpc"),
    ]
    routes += [
        ("https://clob.polymarket.com/markets-by-token/" + value["up_token"], "clob_token")
        for value in seeds.values()
    ]
    requests = []
    total = 0
    for url, kind in routes:
        if total >= 64_000_000:
            break
        value = request(url, kind, 64_000_000 - total)
        total += value["bytes"]
        requests.append(value)
    report = dict(
        schema=SCHEMA,
        identity=identity,
        commit=commit,
        workflow_run_id=os.environ.get("GITHUB_RUN_ID"),
        prior_tag=PRIOR_TAG,
        prior_sha256=PRIOR_SHA,
        requests=requests,
        downloaded_bytes=total,
        network_ns=sum(item["network_ns"] for item in requests),
        research_import_allowed=False,
        expected_catalog_certified=False,
        scope=SCOPE,
        budget_exhausted=len(requests) < len(routes),
    )
    validate_report(report)
    data = canonical(report)
    release = publish(tag, {"access-report.json": data}, commit, "Catalog route access evidence")
    print(
        canonical(
            dict(
                release_id=release["id"],
                tag=tag,
                report_sha256=sha(data),
                downloaded_bytes=total,
                report_bytes=len(data),
                statuses=[item["status"] for item in requests],
            )
        ).decode()
    )


if __name__ == "__main__":
    run()
