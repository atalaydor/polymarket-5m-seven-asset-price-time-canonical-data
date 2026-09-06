"""Content-pinned enumeration of the complete published native V3 hour index."""

from __future__ import annotations

import base64
import html.parser
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from pflow.source import BASE, Reader, canonical, product_contract, sha

INVENTORY_SCHEMA = "pendulumflow-v3-published-inventory.v1"
HOUR_LINK = re.compile(r"/v3/([0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{2})/")


class Links(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for key, value in attrs:
                if key == "href" and value is not None:
                    self.hrefs.append(value)


def parse_page(raw: bytes, page: int) -> tuple[list[str], str | None]:
    parser = Links()
    parser.feed(raw.decode("utf-8"))
    for href in parser.hrefs:
        if re.search(r"(?:^|/)v3/[0-9]{4}-", href) and HOUR_LINK.fullmatch(href) is None:
            raise ValueError("unsupported hour-like inventory link")
        if (
            "page=" in href
            and (href.startswith("?page=") or "/v3/" in href)
            and re.fullmatch(r"/v3/\?page=[0-9]+", href) is None
        ):
            raise ValueError("unsupported inventory pagination link")
    hours = [match.group(1) for href in parser.hrefs if (match := HOUR_LINK.fullmatch(href))]
    if not hours or len(hours) != len(set(hours)):
        raise ValueError("inventory page has no hours or duplicate hour links")
    next_links = sorted(set(href for href in parser.hrefs if href.startswith("/v3/?page=")))
    page_numbers = []
    for href in next_links:
        try:
            page_numbers.append(int(href.removeprefix("/v3/?page=")))
        except ValueError as exc:
            raise ValueError("non-numeric inventory pagination") from exc
    if any(number > page + 1 or number < 1 for number in page_numbers):
        raise ValueError("unexpected inventory pagination jump")
    expected = f"/v3/?page={page + 1}"
    return hours, urljoin(BASE, expected) if expected in next_links else None


def _read_pages(reader: Reader) -> tuple[list[dict[str, Any]], list[str]]:
    url: str | None = BASE + "v3/"
    pages: list[dict[str, Any]] = []
    hours: list[str] = []
    page = 1
    while url is not None:
        if page > 100:
            raise ValueError("unbounded inventory pagination")
        raw = reader.get(url)
        found, next_url = parse_page(raw, page)
        pages.append(
            {
                "page": page,
                "url": url,
                "sha256": sha(raw),
                "size": len(raw),
                "content_base64": base64.b64encode(raw).decode(),
                "parsed_hours": found,
                "next_page": next_url,
            }
        )
        hours.extend(found)
        url = next_url
        page += 1
    if len(hours) != len(set(hours)):
        raise ValueError("hour moved or duplicated across inventory pages")
    if hours != sorted(hours, reverse=True):
        raise ValueError("inventory hours are not strict reverse chronological order")
    return pages, hours


def discover(reader: Reader | None = None) -> dict[str, Any]:
    reader = reader or Reader(limit=100_000_000)
    first_pages, first_hours = _read_pages(reader)
    second_pages, second_hours = _read_pages(reader)
    if first_pages != second_pages or first_hours != second_hours:
        raise ValueError("published index changed during pinning; retry discovery")

    def get_manifest(hour: str) -> dict[str, Any]:
        raw = Reader(limit=2_000_000).get(BASE + "v3/" + hour + "/manifest.json")
        value: dict[str, Any] = json.loads(raw)
        if value.get("hour") != hour or not isinstance(value.get("file"), str):
            raise ValueError("manifest identity mismatch")
        if "/" in value["file"] or not value["file"].endswith(".parquet"):
            raise ValueError("manifest object path invalid")
        for product in ("new_market", "best_bid_ask", "market_resolved"):
            if product not in value.get("products", {}):
                raise ValueError(f"required product absent: {hour}/{product}")
        return {
            "hour": hour,
            "manifest_sha256": sha(raw),
            "manifest_raw_base64": base64.b64encode(raw).decode(),
            "manifest": value,
        }

    with ThreadPoolExecutor(max_workers=16) as pool:
        records = list(pool.map(get_manifest, first_hours))
    records.sort(key=lambda item: item["hour"])
    body: dict[str, Any] = {
        "schema": INVENTORY_SCHEMA,
        "source": "PendulumFlow native V3; CC BY 4.0",
        "source_origin": BASE,
        "scope": "all receipt-hour objects linked by a stable complete published V3 index pass",
        "scope_limitations": [
            "inventory presence is not historical Polymarket listing completeness",
            "inventory absence does not prove a market never existed",
            "published bytes do not prove no source event was missed",
        ],
        "index_pages": first_pages,
        "hours": records,
    }
    body["generation"] = sha(canonical(body))
    return body


def validate_inventory(value: dict[str, Any]) -> None:
    if value.get("schema") != INVENTORY_SCHEMA:
        raise ValueError("wrong inventory schema")
    records = value.get("hours")
    if not isinstance(records, list) or not records:
        raise ValueError("empty inventory")
    hours = [item.get("hour") for item in records]
    if hours != sorted(hours) or len(hours) != len(set(hours)):
        raise ValueError("inventory hour set invalid")
    for item in records:
        if not HOUR_LINK.fullmatch("/v3/" + item["hour"] + "/"):
            raise ValueError("bad inventory hour")
        manifest = item.get("manifest")
        if not isinstance(manifest, dict) or manifest.get("hour") != item["hour"]:
            raise ValueError("manifest binding invalid")
        if (
            not isinstance(manifest.get("file"), str)
            or "/" in manifest["file"]
            or not manifest["file"].endswith(".parquet")
            or type(manifest.get("bytes")) is not int
            or manifest["bytes"] <= 12
            or not re.fullmatch(r"[0-9a-f]{64}", manifest.get("sha256", ""))
        ):
            raise ValueError("manifest object contract invalid")
        products = manifest.get("products")
        if not isinstance(products, dict):
            raise ValueError("manifest product inventory invalid")
        for product in ("new_market", "best_bid_ask", "market_resolved"):
            product_contract(manifest, product)
            if (
                type(products[product].get("row_count")) is not int
                or products[product]["row_count"] < 0
            ):
                raise ValueError("manifest product row count invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("manifest_sha256", "")):
            raise ValueError("manifest digest invalid")
        datetime.strptime(item["hour"], "%Y-%m-%d/%H").replace(tzinfo=UTC)
        raw = base64.b64decode(item.get("manifest_raw_base64", ""), validate=True)
        if sha(raw) != item["manifest_sha256"] or json.loads(raw) != manifest:
            raise ValueError("manifest raw-byte binding invalid")
    pages = value.get("index_pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("inventory page evidence absent")
    flattened: list[str] = []
    for position, page in enumerate(pages, start=1):
        raw = base64.b64decode(page.get("content_base64", ""), validate=True)
        parsed, next_page = parse_page(raw, page["page"])
        expected_url = BASE + ("v3/" if position == 1 else f"v3/?page={position}")
        expected_next = BASE + f"v3/?page={position + 1}" if position < len(pages) else None
        if (
            page.get("page") != position
            or page.get("url") != expected_url
            or sha(raw) != page.get("sha256")
            or len(raw) != page.get("size")
            or parsed != page.get("parsed_hours")
            or next_page != page.get("next_page")
            or next_page != expected_next
        ):
            raise ValueError("inventory page evidence binding invalid")
        flattened.extend(parsed)
    if flattened != list(reversed(hours)):
        raise ValueError("inventory pages do not bind exact normalized hour set")
    expected = sha(canonical({k: v for k, v in value.items() if k != "generation"}))
    if value.get("generation") != expected:
        raise ValueError("inventory generation mismatch")


def manifest_records(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validate_inventory(value)
    return {item["hour"]: item["manifest"] for item in value["hours"]}
