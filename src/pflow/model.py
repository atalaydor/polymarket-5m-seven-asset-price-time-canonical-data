"""Structurally depth-free observed quote contract; no continuity implied."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

ASSETS = ("BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "HYPE")
SLUG = re.compile(r"(btc|eth|sol|xrp|doge|bnb|hype)-updown-5m-([0-9]{10})\Z")
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def micros(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("naive timestamp")
    delta = value - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def token(value: bytes) -> str:
    if not isinstance(value, bytes) or len(value) != 32:
        raise ValueError("token must be 32 native bytes")
    return str(int.from_bytes(value, "big"))


def mapping(row: dict[str, Any]) -> dict[str, Any] | None:
    slug = row.get("slug") or ""
    match = SLUG.fullmatch(slug)
    if not match:
        return None
    outcomes = row.get("outcomes")
    tokens = row.get("assets_ids")
    if outcomes not in (["Up", "Down"], ["Down", "Up"]):
        raise ValueError("ambiguous outcomes")
    if not tokens or len(tokens) != 2 or tokens[0] == tokens[1]:
        raise ValueError("ambiguous outcome tokens")
    start = int(match[2]) * 1_000_000
    if start % 300_000_000:
        raise ValueError("unaligned 5m start")
    return {
        "asset": match[1].upper(),
        "slug": slug,
        "market": row["market"].hex(),
        "venue_market_id": row["id"],
        "question": row["question"],
        "start_us": start,
        "end_us": start + 300_000_000,
        "up_token": token(tokens[outcomes.index("Up")]),
        "down_token": token(tokens[outcomes.index("Down")]),
        "interval_basis": "native_slug_5m_epoch_not_independent_schedule_proof",
    }


def quote(
    row: dict[str, Any], identity: dict[str, Any], hour: str, product_digest: str, ordinal: int
) -> dict[str, Any]:
    ask = row["best_ask"]
    if ask is not None and (not isinstance(ask, Decimal) or not Decimal(0) <= ask <= Decimal(1)):
        raise ValueError("ask requires exact native Decimal within [0,1]")
    token_id = token(row["asset_id"])
    if token_id not in (identity["up_token"], identity["down_token"]):
        raise ValueError("unmapped outcome")
    return {
        "schema": "pendulumflow-observed-ask.v1",
        "market": identity["market"],
        "asset": identity["asset"],
        "token": token_id,
        "outcome": "UP" if token_id == identity["up_token"] else "DOWN",
        "start_us": identity["start_us"],
        "end_us": identity["end_us"],
        "source_event_us": micros(row["timestamp"]) if row["timestamp"] else None,
        "archive_receipt_us": micros(row["timestamp_received"])
        if row["timestamp_received"]
        else None,
        "receipt_kind": "archive_collector_receipt_not_sender_http",
        "source_sequence": row["sequence"],
        "source_witness": row.get("source_witness"),
        "witness_set": row.get("witness_set"),
        "arrival_skew": row.get("arrival_skew"),
        "ask": str(ask) if ask is not None else None,
        "availability": "observed_ask" if ask is not None else "source_null_unknown_reason",
        "source_hour": hour,
        "product_sha256": product_digest,
        "product_row_ordinal": ordinal,
        "continuity": "unproven",
    }


QUOTE_FIELDS = frozenset(
    (
        "schema",
        "market",
        "asset",
        "token",
        "outcome",
        "start_us",
        "end_us",
        "source_event_us",
        "archive_receipt_us",
        "receipt_kind",
        "source_sequence",
        "source_witness",
        "witness_set",
        "arrival_skew",
        "ask",
        "availability",
        "source_hour",
        "product_sha256",
        "product_row_ordinal",
        "continuity",
    )
)


def validate_quote(row: dict[str, Any]) -> None:
    if row.keys() != QUOTE_FIELDS:
        raise ValueError("strict field allowlist: depth and opaque payload rejected")
    if any(isinstance(value, float | list | dict) for value in row.values()):
        raise ValueError("nested/float research values prohibited")
    if row["schema"] != "pendulumflow-observed-ask.v1" or row["continuity"] != "unproven":
        raise ValueError("unproven quote cannot claim interval authority")
    if row["asset"] not in ASSETS or row["outcome"] not in ("UP", "DOWN"):
        raise ValueError("invalid asset/outcome")
    for name in ("market", "product_sha256"):
        if not isinstance(row[name], str) or not re.fullmatch("[0-9a-f]{64}", row[name]):
            raise ValueError("invalid identity/digest")
    if (
        not isinstance(row["token"], str)
        or not re.fullmatch(r"[0-9]{1,78}", row["token"])
        or not 0 <= int(row["token"]) < 2**256
    ):
        raise ValueError("invalid token")
    for name in ("start_us", "end_us", "product_row_ordinal"):
        if type(row[name]) is not int or row[name] < 0:
            raise ValueError("invalid required integer")
    for name in ("source_event_us", "archive_receipt_us", "source_sequence", "arrival_skew"):
        if row[name] is not None and type(row[name]) is not int:
            raise ValueError("invalid nullable integer")
    if row["end_us"] - row["start_us"] != 300_000_000 or row["start_us"] % 300_000_000:
        raise ValueError("invalid interval")
    if row["receipt_kind"] != "archive_collector_receipt_not_sender_http":
        raise ValueError("invalid clock provenance")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}/[0-9]{2}", row["source_hour"]):
        raise ValueError("invalid source hour")
    for name in ("source_witness", "witness_set"):
        if row[name] is not None and not isinstance(row[name], str):
            raise ValueError("invalid witness provenance")
    if row["ask"] is None:
        if row["availability"] != "source_null_unknown_reason":
            raise ValueError("null ask cannot establish known absence")
    elif (
        not isinstance(row["ask"], str)
        or not re.fullmatch(r"[01]\.[0-9]{4}", row["ask"])
        or not Decimal(0) <= Decimal(row["ask"]) <= Decimal(1)
        or row["availability"] != "observed_ask"
    ):
        raise ValueError("invalid exact ask/availability")


def certification_reasons(evidence: dict[str, bool]) -> list[str]:
    """Gate established before acquisition; no caller can omit a required condition."""
    gates = (
        "complete_utc_day",
        "independent_target_universe",
        "unique_mapping",
        "both_side_history",
        "opening_state",
        "target_continuity",
        "boundary_dependencies",
        "official_resolutions",
        "exact_clock_provenance",
        "source_integrity",
        "source_incidents_resolved",
    )
    return [name for name in gates if evidence.get(name) is not True]
