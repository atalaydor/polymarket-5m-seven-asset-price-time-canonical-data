"""Representative native V3 canary; measurements cannot promote a research day."""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pflow.model import ASSETS, mapping, micros, quote, token, validate_quote
from pflow.release import api, current_commit, publish, read_asset, verify_release
from pflow.source import COLUMNS, PRODUCTS, Reader, canonical, fetch_products, sha


def plan(reader: Reader) -> dict[str, Any]:
    inventory, ledger = reader.inventory()
    hours = sorted(
        key.removesuffix("/manifest.json") for key in inventory if key.endswith("/manifest.json")
    )
    today = datetime.now(UTC).date().isoformat()
    counts = Counter(hour[:10] for hour in hours)
    complete = sorted(day for day, count in counts.items() if count == 24 and day < today)
    if not complete:
        raise ValueError("no complete indexed UTC day")
    return {
        "schema": "source-probe-plan.v1",
        "ledger_sha256": sha(ledger),
        "indexed_hours": len(hours),
        "first_hour": hours[0],
        "last_hour": hours[-1],
        "complete_indexed_days_not_certified": complete,
        "hours": [day + "/12" for day in complete[-3:]],
        "discovery_url": "https://archive.pendulumflow.com/v3/SHA256SUMS.txt",
    }


def batches(parquet: Any, manifest: dict[str, Any], product: str) -> Any:
    first, last = manifest["products"][product]["row_groups"]
    columns = [name for name in COLUMNS[product] if name in parquet.schema_arrow.names]
    return parquet.iter_batches(
        row_groups=list(range(first, last + 1)), columns=columns, batch_size=32768
    )


def run(hour: str, history: int = 30, after: int = 6) -> dict[str, Any]:
    if history < 1 or history > 48 or after < 1 or after > 24:
        raise ValueError("bounded context required")
    reader = Reader()
    inventory, ledger = reader.inventory()
    center = datetime.strptime(hour, "%Y-%m-%d/%H").replace(tzinfo=UTC)
    center_us = micros(center)
    context = [
        (center + timedelta(hours=i)).strftime("%Y-%m-%d/%H") for i in range(-history, after + 1)
    ]
    missing = [h for h in context if h + "/manifest.json" not in inventory]
    context = [h for h in context if h not in missing]
    if hour not in context:
        raise ValueError("canary hour absent from current inventory")
    # Manifest identities bind an exact observed source generation before payload work.
    manifests = {h: reader.manifest(h, inventory) for h in context}
    identity = sha(
        canonical(
            {
                "schema": "source-probe-partition.v1",
                "hour": hour,
                "history": history,
                "after": after,
                "sources": {h: sha(raw) for h, (_, raw) in manifests.items()},
                "transform_commit": current_commit(),
            }
        )
    )
    tag = "source-probe-" + identity
    previous = api(f"releases/tags/{tag}")
    if previous and previous["assets"]:
        if len(previous["assets"]) != 1 or not previous["assets"][0]["name"].endswith(
            "--report.json"
        ):
            raise ValueError("checkpoint report inventory differs")
        existing_bytes = read_asset(previous["assets"][0], draft=previous["draft"])
        existing = json.loads(existing_bytes)
        expected_sources = {h: sha(raw) for h, (_, raw) in manifests.items()}
        actual_sources = {h: v["manifest_sha256"] for h, v in existing["source_versions"].items()}
        if (
            existing["schema"] != "pendulumflow-source-canary.v1"
            or existing["partition_identity"] != identity
            or existing["hour"] != hour
            or existing["transform_commit"] != current_commit()
            or existing["research_authority"] is not False
            or actual_sources != expected_sources
        ):
            raise ValueError("checkpoint semantic/source/transform binding differs")
        for sample in existing["quote_samples"].values():
            validate_quote(sample)
        if previous["draft"]:
            previous = publish(
                tag,
                {"report.json": existing_bytes},
                current_commit(),
                "Verified source canary; no research authority",
            )
        else:
            verify_release(previous, {previous["assets"][0]["name"]: existing_bytes})
        print(
            canonical(
                {
                    "checkpoint_reused": True,
                    "tag": tag,
                    "release_id": previous["id"],
                    "new_payload_bytes": 0,
                }
            ).decode()
        )
        return dict(previous)
    work = Path("work") / identity
    work.mkdir(parents=True, exist_ok=True)
    observed_mappings: dict[str, dict[str, Any]] = {}
    contradictions: set[str] = set()
    mapping_errors: list[str] = []
    resolutions: list[dict[str, Any]] = []
    proofs: dict[str, Any] = {}
    lifecycle_rows = Counter[str]()
    target_parquet: Any = None
    decode_seconds = 0.0
    for h, (manifest, _) in manifests.items():
        products = PRODUCTS if h == hour else ("new_market", "market_resolved")
        path = work / (h.replace("/", "T") + ".parquet")
        parquet, proof = fetch_products(reader, manifest, products, path)
        proofs[h] = {"manifest_sha256": sha(manifests[h][1]), **proof}
        started = time.monotonic()
        for product in ("new_market", "market_resolved"):
            product_ordinal = 0
            for batch in batches(parquet, manifest, product):
                for row in batch.to_pylist():
                    ordinal = product_ordinal
                    product_ordinal += 1
                    if row["event_type"] != product:
                        raise ValueError("decoded event type differs from range")
                    lifecycle_rows[product] += 1
                    if product == "new_market":
                        try:
                            mapped = mapping(row)
                        except (ValueError, TypeError, AttributeError) as exc:
                            mapping_errors.append(str(exc))
                            continue
                        if mapped and center_us <= mapped["start_us"] < center_us + 3600_000_000:
                            market = mapped["market"]
                            if market in observed_mappings and mapped != observed_mappings[market]:
                                contradictions.add(market)
                            observed_mappings[market] = mapped
                    elif row["market"] is not None:
                        resolutions.append(
                            {
                                "market": row["market"].hex(),
                                "winning_asset_id": row["winning_asset_id"],
                                "winning_outcome": row["winning_outcome"],
                                "assets_ids": row["assets_ids"],
                                "source_hour": h,
                                "source_event": row["timestamp"],
                                "archive_receipt": row["timestamp_received"],
                                "source_sequence": row["sequence"],
                                "source_witness": row.get("source_witness"),
                                "witness_set": row.get("witness_set"),
                                "arrival_skew": row.get("arrival_skew"),
                                "product_sha256": manifest["products"][product]["sha256"],
                                "product_row_ordinal": ordinal,
                            }
                        )
        decode_seconds += time.monotonic() - started
        if h == hour:
            target_parquet = parquet
        else:
            parquet.close()
            path.unlink()
    manifest = manifests[hour][0]
    counts = Counter[str]()
    unavailable = Counter[str]()
    repeated = Counter[str]()
    previous_ask: dict[str, tuple[Any, ...]] = {}
    first_last: dict[str, tuple[int, int]] = {}
    samples: dict[str, dict[str, Any]] = {}
    missing_clock = 0
    missing_event_time = 0
    outside_interval = 0
    decoded = 0
    started = time.monotonic()
    for batch in batches(target_parquet, manifest, "best_bid_ask"):
        for row in batch.to_pylist():
            decoded += 1
            mapped = observed_mappings.get(row["market"].hex())
            if mapped is None:
                continue
            normalized = quote(
                row, mapped, hour, manifest["products"]["best_bid_ask"]["sha256"], decoded - 1
            )
            validate_quote(normalized)
            timestamp = normalized["source_event_us"]
            if (
                not normalized["source_witness"]
                or normalized["archive_receipt_us"] is None
                or timestamp is None
            ):
                missing_clock += 1
            if timestamp is None:
                missing_event_time += 1
                continue
            if not mapped["start_us"] <= timestamp < mapped["end_us"]:
                outside_interval += 1
                continue
            key = normalized["market"] + ":" + normalized["outcome"]
            counts[key] += 1
            if normalized["ask"] is None:
                unavailable[key] += 1
            state = (
                normalized["ask"],
                normalized["archive_receipt_us"],
                normalized["source_witness"],
            )
            if (
                key in previous_ask
                and state[0] == previous_ask[key][0]
                and state[1:] != previous_ask[key][1:]
            ):
                repeated[key] += 1
            previous_ask[key] = state
            edges = first_last.get(key, (timestamp, timestamp))
            first_last[key] = (min(timestamp, edges[0]), max(timestamp, edges[1]))
            samples.setdefault(mapped["asset"] + ":" + normalized["outcome"], normalized)
    decode_seconds += time.monotonic() - started
    target_parquet.close()
    for path in work.glob("*.parquet"):
        path.unlink()
    resolved: dict[str, set[str]] = {}
    resolution_samples: list[dict[str, Any]] = []
    resolution_assets: set[str] = set()
    for row in resolutions:
        mapped = observed_mappings.get(row["market"])
        if mapped is None or row["winning_asset_id"] is None:
            continue
        winning = token(row["winning_asset_id"])
        actual_tokens = {token(value) for value in row["assets_ids"] or []}
        if actual_tokens != {mapped["up_token"], mapped["down_token"]}:
            contradictions.add(row["market"])
            continue
        expected = (
            mapped["up_token"]
            if row["winning_outcome"] == "Up"
            else mapped["down_token"]
            if row["winning_outcome"] == "Down"
            else None
        )
        if winning != expected:
            contradictions.add(row["market"])
            continue
        resolved.setdefault(row["market"], set()).add(winning)
        if mapped["asset"] not in resolution_assets:
            resolution_assets.add(mapped["asset"])
            resolution_samples.append(
                {
                    "market": row["market"],
                    "asset": mapped["asset"],
                    "winning_token": winning,
                    "winning_outcome": row["winning_outcome"],
                    "source_hour": row["source_hour"],
                    "source_event_us": micros(row["source_event"]) if row["source_event"] else None,
                    "archive_receipt_us": micros(row["archive_receipt"])
                    if row["archive_receipt"]
                    else None,
                    "source_sequence": row["source_sequence"],
                    "source_witness": row["source_witness"],
                    "witness_set": row["witness_set"],
                    "arrival_skew": row["arrival_skew"],
                    "product_sha256": row["product_sha256"],
                    "product_row_ordinal": row["product_row_ordinal"],
                    "evidence_kind": "native_V3_archived_venue_lifecycle",
                    "transport": "not_identified_in_published_schema",
                }
            )
    source_versions = {
        h: {
            "manifest_sha256": sha(raw),
            "merger_git_sha": m.get("merger_git_sha"),
            "layout": m.get("layout"),
            "sequence_note": m.get("sequence_note"),
        }
        for h, (m, raw) in manifests.items()
    }
    network_seconds = sum(item["seconds"] for item in reader.measurements)
    report = {
        "schema": "pendulumflow-source-canary.v1",
        "partition_identity": identity,
        "transform_commit": current_commit(),
        "hour": hour,
        "runner": {
            "os": platform.system(),
            "python": platform.python_version(),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "attribution": "PendulumFlow native V3; CC BY 4.0; archive.pendulumflow.com",
        "research_authority": False,
        "certified_days": [],
        "certification_status": "BLOCKED_SOURCE_CAPABILITY",
        "missing_conditions": [
            "independent_target_market_census",
            "target_token_continuity",
            "opening_state_across_unobserved_gaps",
        ],
        "ledger_sha256": sha(ledger),
        "source_versions": source_versions,
        "source_document_snapshots": json.loads(
            Path("docs/source-document-snapshots.json").read_text(encoding="utf-8")
        ),
        "observed_schema_sha256": sha(Path("docs/native-schema-observed.json").read_bytes()),
        "context_hours": context,
        "missing_context_hours": missing,
        "decoded_lifecycle_rows": dict(lifecycle_rows),
        "decoded_quote_rows": decoded,
        "mapped_target_markets": len(observed_mappings),
        "mapped_markets_by_asset": dict(Counter(m["asset"] for m in observed_mappings.values())),
        "assets_without_mapping": sorted(
            set(ASSETS) - {m["asset"] for m in observed_mappings.values()}
        ),
        "mapping_errors": dict(Counter(mapping_errors)),
        "contradictory_markets": sorted(contradictions),
        "both_side_observed_markets": sum(
            all(m + ":" + s in counts for s in ("UP", "DOWN")) for m in observed_mappings
        ),
        "missing_side_observations": [
            m + ":" + s
            for m in observed_mappings
            for s in ("UP", "DOWN")
            if m + ":" + s not in counts
        ],
        "resolved_target_markets": len(resolved),
        "contradictory_resolutions": sorted(
            m for m, winners in resolved.items() if len(winners) != 1
        ),
        "pending_resolutions": sorted(set(observed_mappings) - resolved.keys()),
        "target_ask_observations": sum(counts.values()),
        "source_null_asks": sum(unavailable.values()),
        "unchanged_ask_distinct_receipts": sum(repeated.values()),
        "missing_quote_clock": missing_clock,
        "target_quotes_missing_event_time": missing_event_time,
        "target_quotes_outside_market_interval": outside_interval,
        "observed_first_last_event_us_by_market_side_not_continuity": first_last,
        "quote_samples": samples,
        "resolution_samples": resolution_samples,
        "mapping_samples": sorted(observed_mappings.values(), key=lambda m: m["slug"])[:14],
        "opening_state_proven": False,
        "target_continuity_proven": False,
        "source_integrity": proofs,
        "measurements": reader.measurements,
        "downloaded_bytes": reader.downloaded,
        "requested_range_bytes": sum(m["requested_bytes"] or 0 for m in reader.measurements),
        "network_seconds": network_seconds,
        "decode_seconds": decode_seconds,
        "network_bytes_per_second": reader.downloaded / max(network_seconds, 0.001),
        "backfill_estimate": None,
        "estimate_reason": "No scaling before source certification sufficiency",
    }
    report_bytes = canonical(report)
    (work / "report.json").write_bytes(report_bytes)
    release = publish(
        tag,
        {"report.json": report_bytes},
        current_commit(),
        "Verified source canary; no research authority",
    )
    print(
        canonical(
            {
                "tag": tag,
                "release_id": release["id"],
                "report_sha256": sha(report_bytes),
                "downloaded_bytes": reader.downloaded,
                "mapped_markets": len(observed_mappings),
                "both_sides": report["both_side_observed_markets"],
                "resolved": len(resolved),
            }
        ).decode()
    )
    return release


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "probe"))
    parser.add_argument("--hour")
    parser.add_argument("--history", type=int, default=30)
    parser.add_argument("--after", type=int, default=6)
    args = parser.parse_args()
    if args.command == "plan":
        result = plan(Reader())
        Path("work").mkdir(exist_ok=True)
        Path("work/plan.json").write_bytes(canonical(result))
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
                handle.write("hours=" + json.dumps(result["hours"]) + "\n")
        print(canonical(result).decode())
    elif args.hour:
        run(args.hour, args.history, args.after)
    else:
        parser.error("--hour required")


if __name__ == "__main__":
    main()
