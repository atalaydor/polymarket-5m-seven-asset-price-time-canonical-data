"""Two-hour native V3 integrity experiment; never publishes research authority."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from pflow.consumer import verify
from pflow.integrity import Counters, Event, diagnose, require_counter_export
from pflow.model import token, validate_quote
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import BASE, COMMON, Reader, canonical, check_schema, sha

HOURS = ("2026-08-28/11", "2026-08-28/12")
MANIFEST_PINS = (
    "e0eaf9f38222ebe4ba78df9ba525cd56b89b273d577f8bec8af058457ef52c5b",
    "b7d00beb5e0590d88482824580493f793ad379024cce94a28e20f6a21ad0145b",
)
PRIOR_TAG = "source-probe-8e650e70605997c050bf7d32ef898e8077105fe19ebaa21c1089d07b0a1cc31c"
PRIOR_SHA = "61347d5fdd408676adff2d40a5224934e5b646175a59d2c562a6b042ec355173"
COHORT_SHA = "ccc37ac860ec9cce50a9ee501b6375435f85893d32204373046559760e479fe1"
INTEGRITY_PRODUCTS = ("book", "price_change", "best_bid_ask")
PROJECTION = {
    "book": (*COMMON, "asset_id", "asks"),
    "price_change": (*COMMON, "asset_id", "price", "size", "side", "best_ask"),
    "best_bid_ask": (*COMMON, "asset_id", "best_ask"),
}


def contract(manifest: dict[str, Any], product: str) -> tuple[int, int, int, int]:
    if product not in INTEGRITY_PRODUCTS:
        raise ValueError("not an authorized transient integrity product")
    spec = manifest["products"][product]
    start, end = spec["byte_range"]
    first, last = spec["row_groups"]
    if not all(type(v) is int for v in (start, end, first, last)):
        raise ValueError("noninteger range")
    if not 4 <= start < end < manifest["bytes"] or not 0 <= first <= last < 1000:
        raise ValueError("range/row-group bounds")
    if not re.fullmatch(r"[0-9a-f]{64}", spec["sha256"]):
        raise ValueError("missing product hash")
    return start, end, first, last


def acquire(reader: Reader, manifest: dict[str, Any], path: Path) -> tuple[Any, dict[str, Any]]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    url = BASE + f"v3/{manifest['hour']}/{manifest['file']}"
    size = manifest["bytes"]
    tail = reader.get(url, (size - 8, size))
    length = int.from_bytes(tail[:4], "little")
    if tail[-4:] != b"PAR1" or not 0 < length < min(size - 12, 8_000_000):
        raise ValueError("invalid/bounded footer")
    offset = size - 8 - length
    footer = reader.get(url, (offset, size - 8))
    proof: dict[str, Any] = {
        "hour": manifest["hour"],
        "manifest_sha256": sha(canonical(manifest)),
        "footer_sha256_observed": sha(footer + tail),
        "whole_file_verified": False,
        "products": [],
    }
    with path.open("wb") as handle:
        handle.write(b"PAR1")
        handle.seek(offset)
        handle.write(footer + tail)
        for product in INTEGRITY_PRODUCTS:
            start, end, first, last = contract(manifest, product)
            if end > offset:
                raise ValueError("product overlaps footer")
            digest = hashlib.sha256()
            handle.seek(start)
            for chunk_start in range(start, end, 32_000_000):
                data = reader.get(url, (chunk_start, min(chunk_start + 32_000_000, end)))
                digest.update(data)
                handle.write(data)
            if digest.hexdigest() != manifest["products"][product]["sha256"]:
                raise ValueError("complete transient product hash mismatch")
            proof["products"].append(
                {
                    "product": product,
                    "sha256": digest.hexdigest(),
                    "start": start,
                    "end": end,
                    "first_group": first,
                    "last_group": last,
                    "row_count": manifest["products"][product]["row_count"],
                    "range_hash_verified": True,
                }
            )
            print(canonical({"hour": manifest["hour"], "hashed_product": product}).decode())
    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    check_schema(schema, "best_bid_ask")
    if schema.field("price").type != pa.decimal128(9, 4):
        raise ValueError("price must remain exact decimal")
    if schema.field("size").type != pa.decimal128(18, 6):
        raise ValueError("transient size must remain exact decimal")
    asks_type = pa.list_(
        pa.struct([("price", pa.decimal128(9, 4)), ("size", pa.decimal128(18, 6))])
    )
    if schema.field("asks").type != asks_type:
        raise ValueError("unsupported transient native book shape")
    for product in INTEGRITY_PRODUCTS:
        start, end, first, last = contract(manifest, product)
        rows = 0
        for ordinal in range(first, last + 1):
            group = parquet.metadata.row_group(ordinal)
            rows += group.num_rows
            labels = 0
            for index in range(group.num_columns):
                col = group.column(index)
                page = col.data_page_offset
                if col.has_dictionary_page:
                    page = min(page, col.dictionary_page_offset)
                if not start <= page < page + col.total_compressed_size <= end:
                    raise ValueError("footer column escapes authenticated product range")
                if col.path_in_schema == "event_type":
                    if (
                        not col.statistics
                        or col.statistics.min != product
                        or col.statistics.max != product
                    ):
                        raise ValueError("footer product label mismatch")
                    labels += 1
            if labels != 1:
                raise ValueError("missing footer label")
        if rows != manifest["products"][product]["row_count"]:
            raise ValueError("footer row-count mismatch")
    return parquet, proof


def target_rows(
    parquet: Any, manifest: dict[str, Any], targets: dict[str, dict[str, Any]]
) -> tuple[dict[str, list[Event]], dict[str, Counters], dict[str, int]]:
    import pyarrow as pa
    import pyarrow.compute as pc

    market_keys = {bytes.fromhex(row["market"]) for row in targets.values()}
    token_keys = pa.array([int(row["token"]).to_bytes(32, "big") for row in targets.values()])
    by_token = {row["token"]: label for label, row in targets.items()}
    events: dict[str, list[Event]] = {label: [] for label in targets}
    counts = {label: Counters() for label in targets}
    scan = {"groups_read": 0, "groups_pruned": 0, "rows_projected": 0, "target_rows": 0}
    for product in INTEGRITY_PRODUCTS:
        _, _, first, last = contract(manifest, product)
        groups = []
        for ordinal in range(first, last + 1):
            group = parquet.metadata.row_group(ordinal)
            stats = next(
                (
                    group.column(i).statistics
                    for i in range(group.num_columns)
                    if group.column(i).path_in_schema == "market"
                ),
                None,
            )
            if (
                stats
                and stats.has_min_max
                and not any(stats.min <= m <= stats.max for m in market_keys)
            ):
                scan["groups_pruned"] += 1
            else:
                groups.append(ordinal)
                scan["groups_read"] += 1
        batch_size = 1024 if product == "book" else 65536
        for batch in parquet.iter_batches(
            batch_size=batch_size, row_groups=groups, columns=PROJECTION[product]
        ):
            scan["rows_projected"] += batch.num_rows
            filtered = batch.filter(pc.is_in(batch.column("asset_id"), value_set=token_keys))
            # Units were checked against the Arrow schema. Integer conversion
            # preserves all bits and avoids platform timezone-database needs.
            for clock in ("timestamp", "timestamp_received"):
                index = filtered.schema.get_field_index(clock)
                filtered = filtered.set_column(
                    index, clock, filtered.column(index).cast(pa.int64())
                )
            for row in filtered.to_pylist():
                label = by_token[token(row["asset_id"])]
                if row["market"].hex() != targets[label]["market"] or row["event_type"] != product:
                    raise ValueError("target identity/product mismatch")
                scan["target_rows"] += 1
                if scan["target_rows"] > 1_000_000:
                    raise ValueError("bounded target-row budget")
                if row["timestamp"] is None or row["timestamp_received"] is None:
                    counts[label].missing_clock_rows += 1
                    continue
                witness = row["source_witness"]
                witnesses = row["witness_set"]
                if not isinstance(witness, str) or not re.fullmatch("[a-z]", witness):
                    counts[label].missing_witness_rows += 1
                    continue
                if not isinstance(witnesses, str) or not re.fullmatch(r"(?:\|[a-z])+\|", witnesses):
                    counts[label].missing_witness_rows += 1
                    continue
                events[label].append(
                    Event(
                        product=product,
                        hour=manifest["hour"],
                        event_us=row["timestamp"] * 1000,
                        receipt_us=row["timestamp_received"],
                        sequence=row["sequence"],
                        witness=witness,
                        witnesses=witnesses,
                        ask=row.get("best_ask"),
                        price=row.get("price"),
                        size=row.get("size"),
                        side=row.get("side"),
                        asks=tuple(
                            (level["price"], level["size"]) for level in row.get("asks", []) or []
                        ),
                    )
                )
    return events, counts, scan


def validate_report(report: dict[str, Any]) -> None:
    expected = {
        "schema",
        "identity",
        "commit",
        "prior_tag",
        "prior_sha256",
        "hours",
        "source_proofs",
        "targets",
        "counters",
        "scans",
        "downloaded_bytes",
        "requested_range_bytes",
        "network_seconds",
        "decode_seconds",
        "research_authority",
        "certified_days",
        "continuity_proven",
        "canonical_rows_emitted",
        "venue_sequence_evidence",
        "witness_session_gap_evidence",
        "source_attribution",
    }
    if report.keys() != expected:
        raise ValueError("unexpected report fields")
    if (
        report["schema"] != "pendulumflow-continuity-diagnostic.v1"
        or report["research_authority"] is not False
        or report["continuity_proven"] is not False
        or report["certified_days"] != []
        or report["canonical_rows_emitted"] != 0
        or report["venue_sequence_evidence"] != "not_exported_in_observed_contract"
        or report["witness_session_gap_evidence"] != "not_exported_in_observed_contract"
        or report["source_attribution"] != "PendulumFlow native V3; CC BY 4.0"
        or report["hours"] != list(HOURS)
        or report["prior_tag"] != PRIOR_TAG
        or report["prior_sha256"] != PRIOR_SHA
    ):
        raise ValueError("diagnostic cannot promote authority or carry untyped text")
    for key, length in (("identity", 64), ("commit", 40)):
        if not re.fullmatch("[0-9a-f]{" + str(length) + "}", report[key]):
            raise ValueError("invalid identity")
    if report["targets"].keys() != report["counters"].keys() or len(report["targets"]) != 14:
        raise ValueError("bounded 14-outcome cohort required")
    if sha(canonical(report["targets"])) != COHORT_SHA:
        raise ValueError("only the exact previously verified depth-free cohort may be exported")
    for label, row in report["targets"].items():
        validate_quote(row)
        if label != row["asset"] + ":" + row["outcome"]:
            raise ValueError("cohort label mismatch")
        require_counter_export(report["counters"][label])
    for key in ("downloaded_bytes", "requested_range_bytes", "network_seconds", "decode_seconds"):
        value = report[key]
        if type(value) not in (int, float) or not 0 <= value < 2_100_000_000:
            raise ValueError("invalid bounded telemetry")
    if len(report["source_proofs"]) != 2 or len(report["scans"]) != 2:
        raise ValueError("two-hour diagnostic required")
    for i, proof in enumerate(report["source_proofs"]):
        if proof.keys() != {
            "hour",
            "manifest_sha256",
            "footer_sha256_observed",
            "whole_file_verified",
            "products",
        }:
            raise ValueError("unknown proof field")
        if (
            proof["hour"] != HOURS[i]
            or proof["manifest_sha256"] != MANIFEST_PINS[i]
            or proof["whole_file_verified"] is not False
        ):
            raise ValueError("proof identity")
        if not re.fullmatch("[0-9a-f]{64}", proof["footer_sha256_observed"]):
            raise ValueError("footer digest")
        if len(proof["products"]) != 3:
            raise ValueError("product count")
        for product, spec in zip(INTEGRITY_PRODUCTS, proof["products"], strict=True):
            if spec.keys() != {
                "product",
                "sha256",
                "start",
                "end",
                "first_group",
                "last_group",
                "row_count",
                "range_hash_verified",
            }:
                raise ValueError("unknown product field")
            if spec["product"] != product or spec["range_hash_verified"] is not True:
                raise ValueError("product contract")
            if not re.fullmatch("[0-9a-f]{64}", spec["sha256"]):
                raise ValueError("product digest")
            if any(
                type(spec[k]) is not int or not 0 <= spec[k] < 2_100_000_000
                for k in ("start", "end", "first_group", "last_group", "row_count")
            ):
                raise ValueError("invalid product metadata")
    for scan in report["scans"]:
        if scan.keys() != {"groups_read", "groups_pruned", "rows_projected", "target_rows"} or any(
            type(v) is not int or v < 0 for v in scan.values()
        ):
            raise ValueError("only bounded scan counters")


def main() -> None:
    if sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("transient integrity acquisition runs only on Actions Linux")
    commit = current_commit()
    identity = sha(
        canonical(
            {"commit": commit, "hours": HOURS, "manifests": MANIFEST_PINS, "prior": PRIOR_SHA}
        )
    )
    tag = "continuity-probe-" + identity
    existing = api("releases/tags/" + tag)
    if existing is not None and not existing["draft"]:
        verify_release(existing)
        if len(existing["assets"]) != 1:
            raise ValueError("unexpected evidence inventory")
        old = json.loads(read_asset(existing["assets"][0]))
        validate_report(old)
        if old["identity"] != identity or old["commit"] != commit:
            raise ValueError("existing diagnostic partition differs")
        print(canonical({"reused_release": existing["id"], "new_source_bytes": 0}).decode())
        return
    if existing is not None:
        # An uploaded diagnostic can be sealed without reacquiring transient data.
        if len(existing["assets"]) != 1:
            raise ValueError("incomplete draft preserved; manual inspection required")
        data = read_asset(existing["assets"][0], draft=True)
        old = json.loads(data)
        validate_report(old)
        if old["identity"] != identity or old["commit"] != commit:
            raise ValueError("draft identity")
        publish(tag, {"diagnostic.json": data}, commit, "Blocked V3 continuity diagnostic")
        return
    prior = verify(PRIOR_TAG, PRIOR_SHA, evidence_only=True)["report"]
    targets = prior["quote_samples"]
    for row in targets.values():
        validate_quote(row)
    reader = Reader(limit=2_100_000_000)
    inventory, _ = reader.inventory()
    all_events: dict[str, list[Event]] = {label: [] for label in targets}
    all_counters = {label: Counters() for label in targets}
    proofs = []
    scans = []
    decode_seconds = 0.0
    with tempfile.TemporaryDirectory(prefix="transient-v3-integrity-") as directory:
        for hour, pin in zip(HOURS, MANIFEST_PINS, strict=True):
            manifest, raw = reader.manifest(hour, inventory)
            if sha(raw) != pin:
                raise ValueError("pinned source changed; new evidence decision required")
            path = Path(directory) / "transient.parquet"
            parquet, proof = acquire(reader, manifest, path)
            proof["manifest_sha256"] = sha(raw)
            started = time.monotonic()
            events, counters, scan = target_rows(parquet, manifest, targets)
            decode_seconds += time.monotonic() - started
            parquet.close()
            path.unlink()
            proofs.append(proof)
            scans.append(scan)
            for label in targets:
                all_events[label].extend(events[label])
                all_counters[label].missing_clock_rows += counters[label].missing_clock_rows
                all_counters[label].missing_witness_rows += counters[label].missing_witness_rows
            print(canonical({"hour": hour, "scan": scan}).decode())
        started = time.monotonic()
        results = {
            label: diagnose(events, all_counters[label]) for label, events in all_events.items()
        }
        decode_seconds += time.monotonic() - started
        all_events.clear()
        events.clear()
    report = {
        "schema": "pendulumflow-continuity-diagnostic.v1",
        "identity": identity,
        "commit": commit,
        "prior_tag": PRIOR_TAG,
        "prior_sha256": PRIOR_SHA,
        "hours": list(HOURS),
        "source_proofs": proofs,
        "targets": targets,
        "counters": results,
        "scans": scans,
        "downloaded_bytes": reader.downloaded,
        "requested_range_bytes": sum(m["requested_bytes"] or 0 for m in reader.measurements),
        "network_seconds": sum(m["seconds"] for m in reader.measurements),
        "decode_seconds": decode_seconds,
        "research_authority": False,
        "certified_days": [],
        "continuity_proven": False,
        "canonical_rows_emitted": 0,
        "venue_sequence_evidence": "not_exported_in_observed_contract",
        "witness_session_gap_evidence": "not_exported_in_observed_contract",
        "source_attribution": "PendulumFlow native V3; CC BY 4.0",
    }
    validate_report(report)
    release = publish(
        tag, {"diagnostic.json": canonical(report)}, commit, "Blocked V3 continuity diagnostic"
    )
    print(
        canonical(
            {
                "release_id": release["id"],
                "tag": tag,
                "report_sha256": sha(canonical(report)),
                "research_authority": False,
            }
        ).decode()
    )


if __name__ == "__main__":
    main()
