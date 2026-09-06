"""Bounded source reads. Payload range acquisition is restricted to Actions Linux."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

BASE = "https://archive.pendulumflow.com/"
PRODUCTS = ("new_market", "best_bid_ask", "market_resolved")
COMMON = (
    "event_type",
    "timestamp_received",
    "timestamp",
    "sequence",
    "market",
    "source_witness",
    "witness_set",
    "arrival_skew",
)
COLUMNS = {
    "new_market": (*COMMON, "id", "assets_ids", "outcomes", "slug", "question"),
    "best_bid_ask": (*COMMON, "asset_id", "best_ask"),
    "market_resolved": (*COMMON, "id", "assets_ids", "winning_asset_id", "winning_outcome"),
}


class _SourceRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        valid_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPEN = urllib.request.build_opener(_SourceRedirect())


def canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "archive.pendulumflow.com":
        raise ValueError("source origin must be native PendulumFlow")
    if not parsed.path.startswith("/v3/"):
        raise ValueError("only native V3 payload/metadata allowed")


@dataclass
class Reader:
    limit: int = 1_500_000_000
    measurements: list[dict[str, Any]] = field(default_factory=list)
    downloaded: int = 0

    def get(self, url: str, interval: tuple[int, int] | None = None) -> bytes:
        valid_url(url)
        headers = {
            "User-Agent": "pendulumflow-price-time-source-proof/0.1",
            "Accept-Encoding": "identity",
        }
        cap = 2_000_000
        if interval is not None:
            if sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true":
                raise RuntimeError("market byte ranges run only on standard Actions Linux")
            start, end = interval
            if not 0 <= start < end or end - start > 350_000_000:
                raise ValueError("range bounds")
            cap = end - start
            headers["Range"] = f"bytes={start}-{end - 1}"
        if self.downloaded + cap > self.limit:
            raise ValueError("canary byte budget exhausted")
        record: dict[str, Any] = {
            "url": url,
            "range": interval,
            "requested_bytes": cap if interval else None,
        }
        started = time.monotonic()
        request = urllib.request.Request(url, headers=headers)
        with OPEN.open(request, timeout=90) as response:
            valid_url(response.url)
            record.update(
                status=response.status,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                content_range=response.headers.get("Content-Range"),
            )
            if interval is not None:
                expected = f"bytes {interval[0]}-{interval[1] - 1}/"
                if response.status != 206 or not (record["content_range"] or "").startswith(
                    expected
                ):
                    raise ValueError("server did not honor exact range; full body rejected")
            data = bytes(response.read(cap + 1))
            self.downloaded += len(data)
            record.update(
                downloaded_bytes=len(data), seconds=time.monotonic() - started, sha256=sha(data)
            )
            self.measurements.append(record)
            if len(data) > cap or (interval is not None and len(data) != cap):
                raise ValueError("truncated or oversized response")
            return data

    def inventory(self) -> tuple[dict[str, str], bytes]:
        raw = self.get(BASE + "v3/SHA256SUMS.txt")
        inventory = {}
        for line in raw.decode().splitlines():
            match = re.fullmatch(
                r"([0-9a-f]{64})\s+([0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{2}/[^/]+)", line
            )
            if match:
                inventory[match[2]] = match[1]
        if not inventory:
            raise ValueError("no indexed V3 objects")
        return inventory, raw

    def manifest(self, hour: str, inventory: dict[str, str]) -> tuple[dict[str, Any], bytes]:
        key = hour + "/manifest.json"
        if key not in inventory:
            raise ValueError("hour manifest not in observed public ledger")
        data = self.get(BASE + "v3/" + key)
        if sha(data) != inventory[key]:
            raise ValueError("manifest changed relative to ledger; rediscovery required")
        obj: dict[str, Any] = json.loads(data)
        if obj["hour"] != hour or "/" in obj["file"]:
            raise ValueError("manifest identity mismatch")
        if inventory.get(hour + "/" + obj["file"]) != obj["sha256"]:
            raise ValueError("whole-object digest disagrees with inventory")
        return obj, data


def product_contract(manifest: dict[str, Any], product: str) -> tuple[int, int, int, int]:
    if product not in PRODUCTS:
        raise ValueError("depth/non-required product rejected")
    spec = manifest["products"][product]
    start, end = spec["byte_range"]
    first, last = spec["row_groups"]
    if not (type(start) is int and type(end) is int and 4 <= start < end < manifest["bytes"]):
        raise ValueError("invalid byte range")
    if not (type(first) is int and type(last) is int and 0 <= first <= last):
        raise ValueError("invalid row groups")
    if not re.fullmatch("[0-9a-f]{64}", spec["sha256"]):
        raise ValueError("missing product digest")
    return start, end, first, last


def fetch_products(
    reader: Reader, manifest: dict[str, Any], products: tuple[str, ...], path: Path
) -> tuple[Any, dict[str, Any]]:
    import pyarrow.parquet as pq

    url = urljoin(BASE, f"v3/{manifest['hour']}/{manifest['file']}")
    size = manifest["bytes"]
    tail = reader.get(url, (size - 8, size))
    if tail[-4:] != b"PAR1":
        raise ValueError("invalid parquet footer signature")
    footer_size = int.from_bytes(tail[:4], "little")
    if not 0 < footer_size < min(size - 12, 8_000_000):
        raise ValueError("unbounded footer")
    footer_start = size - 8 - footer_size
    footer = reader.get(url, (footer_start, size - 8))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"PAR1")
        handle.seek(footer_start)
        handle.write(footer + tail)
        for product in products:
            start, end, _, _ = product_contract(manifest, product)
            if end > footer_start:
                raise ValueError("product overlaps footer")
            data = reader.get(url, (start, end))
            if sha(data) != manifest["products"][product]["sha256"]:
                raise ValueError("product hash mismatch")
            handle.seek(start)
            handle.write(data)
    parquet = pq.ParquetFile(path)
    proof: dict[str, Any] = {
        "footer_sha256_observed": sha(footer + tail),
        "whole_file_verified": False,
        "products": {},
    }
    for product in products:
        check_schema(parquet.schema_arrow, product)
        start, end, first, last = product_contract(manifest, product)
        rows = 0
        for ordinal in range(first, last + 1):
            group = parquet.metadata.row_group(ordinal)
            rows += group.num_rows
            event_found = False
            for index in range(group.num_columns):
                column = group.column(index)
                offsets = [column.data_page_offset]
                if column.has_dictionary_page:
                    offsets.append(column.dictionary_page_offset)
                offset = min(offsets)
                if not start <= offset < offset + column.total_compressed_size <= end:
                    raise ValueError("footer column escapes hashed product")
                if column.path_in_schema == "event_type":
                    stats = column.statistics
                    if not stats or stats.min != product or stats.max != product:
                        raise ValueError("footer product label disagrees")
                    event_found = True
            if not event_found:
                raise ValueError("no event_type footer statistics")
        if rows != manifest["products"][product]["row_count"]:
            raise ValueError("footer/manifest row count mismatch")
        proof["products"][product] = {
            **manifest["products"][product],
            "range_sha256_verified": True,
            "footer_binding_checked": True,
        }
    return parquet, proof


def check_schema(schema: Any, product: str) -> None:
    import pyarrow as pa

    required = {
        "timestamp": pa.timestamp("ms", tz="UTC"),
        "timestamp_received": pa.timestamp("us", tz="UTC"),
        "sequence": pa.uint64(),
    }
    if product == "best_bid_ask":
        required["best_ask"] = pa.decimal128(9, 4)
    for name, expected in required.items():
        if name not in schema.names or schema.field(name).type != expected:
            raise ValueError(f"unsupported native exact schema: {name}")
    identities = ["market", "asset_id"] if product == "best_bid_ask" else ["market"]
    if product == "market_resolved":
        identities.append("winning_asset_id")
    for name in identities:
        if name not in schema.names:
            raise ValueError(f"missing identity: {name}")
        kind = schema.field(name).type
        if not (
            pa.types.is_binary(kind)
            or (pa.types.is_fixed_size_binary(kind) and kind.byte_width == 32)
        ):
            raise ValueError(f"unsupported binary identity: {name}")
