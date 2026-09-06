"""Frozen, structurally depth-free PENDULUMFLOW_V3_OBSERVED v1 contracts."""

from __future__ import annotations

import gzip
import io
import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any

from pflow.model import ASSETS, mapping, micros, token
from pflow.source import canonical

PROFILE = "PENDULUMFLOW_V3_OBSERVED"
PROFILE_VERSION = 1
CERTIFICATION_SCOPE = "PINNED_PUBLISHED_PENDULUMFLOW_V3_INVENTORY"
CERTIFICATION_SCOPE_VERSION = 1
TRANSFORM = "pendulumflow-v3-observed-inventory-projection.v1"
MAPPING_SCHEMA = "pendulumflow-v3-observed-mapping.v1"
OBSERVATION_SCHEMA = "pendulumflow-v3-observed-observation.v1"
RESOLUTION_SCHEMA = "pendulumflow-v3-observed-resolution.v1"
WINDOW_SCHEMA = "pendulumflow-v3-observed-window.v1"


def profile_fields() -> dict[str, Any]:
    return {
        "profile": PROFILE,
        "profile_version": PROFILE_VERSION,
        "certification_scope": CERTIFICATION_SCOPE,
        "certification_scope_version": CERTIFICATION_SCOPE_VERSION,
        "continuity_between_observations_certified": False,
        "historical_polymarket_listing_completeness_claimed": False,
    }


def mapping_record(row: dict[str, Any], source: dict[str, Any]) -> dict[str, Any] | None:
    identity = mapping(row)
    if identity is None:
        return None
    value = {
        "schema": MAPPING_SCHEMA,
        **profile_fields(),
        **identity,
        "source_event_us": micros(row["timestamp"]) if row.get("timestamp") else None,
        "archive_receipt_us": micros(row["timestamp_received"]),
        "source_sequence": row.get("sequence"),
        "source_witness": row.get("source_witness"),
        "witness_set": row.get("witness_set"),
        "arrival_skew": row.get("arrival_skew"),
        **source,
    }
    validate_mapping(value)
    return value


def observation_record(
    row: dict[str, Any], identity: dict[str, Any], source: dict[str, Any]
) -> dict[str, Any]:
    asset_token = token(row["asset_id"])
    if asset_token not in (identity["up_token"], identity["down_token"]):
        raise ValueError("observation token not in mapped market")
    ask = row.get("best_ask")
    if ask is not None and (not isinstance(ask, Decimal) or not Decimal(0) <= ask <= Decimal(1)):
        raise ValueError("ask is not exact Decimal in [0,1]")
    event_us = micros(row["timestamp"]) if row.get("timestamp") else None
    value = {
        "schema": OBSERVATION_SCHEMA,
        **profile_fields(),
        "market": identity["market"],
        "asset": identity["asset"],
        "token": asset_token,
        "outcome": "UP" if asset_token == identity["up_token"] else "DOWN",
        "start_us": identity["start_us"],
        "end_us": identity["end_us"],
        "source_event_us": event_us,
        "remaining_us": identity["end_us"] - event_us if event_us is not None else None,
        "archive_receipt_us": micros(row["timestamp_received"]),
        "receipt_kind": "archive_collector_receipt_not_sender_http",
        "source_sequence": row.get("sequence"),
        "source_witness": row.get("source_witness"),
        "witness_set": row.get("witness_set"),
        "arrival_skew": row.get("arrival_skew"),
        "ask": str(ask) if ask is not None else None,
        "availability": "observed_ask" if ask is not None else "source_null_unknown_reason",
        **source,
    }
    validate_observation(value)
    return value


def resolution_record(
    row: dict[str, Any], identity: dict[str, Any], source: dict[str, Any]
) -> dict[str, Any]:
    if row.get("winning_asset_id") is None:
        raise ValueError("resolution missing winning token")
    winner = token(row["winning_asset_id"])
    outcome = row.get("winning_outcome")
    if not isinstance(outcome, str):
        raise ValueError("resolution missing winning outcome")
    expected = {
        "Up": identity["up_token"],
        "Down": identity["down_token"],
    }.get(outcome)
    actual = {token(value) for value in row.get("assets_ids") or []}
    if (
        expected is None
        or winner != expected
        or actual
        != {
            identity["up_token"],
            identity["down_token"],
        }
    ):
        raise ValueError("resolution contradicts mapped outcomes")
    value = {
        "schema": RESOLUTION_SCHEMA,
        **profile_fields(),
        "market": identity["market"],
        "asset": identity["asset"],
        "winning_token": winner,
        "winning_outcome": row["winning_outcome"].upper(),
        "source_event_us": micros(row["timestamp"]) if row.get("timestamp") else None,
        "archive_receipt_us": micros(row["timestamp_received"]),
        "source_sequence": row.get("sequence"),
        "source_witness": row.get("source_witness"),
        "witness_set": row.get("witness_set"),
        "arrival_skew": row.get("arrival_skew"),
        "evidence_kind": "native_v3_archived_market_resolved",
        **source,
    }
    validate_resolution(value)
    return value


def _strict(value: dict[str, Any], fields: frozenset[str], schema: str) -> None:
    if value.keys() != fields or value.get("schema") != schema:
        raise ValueError("strict schema allowlist rejects depth or opaque fields")
    if (
        value.get("profile") != PROFILE
        or type(value.get("profile_version")) is not int
        or value.get("profile_version") != PROFILE_VERSION
    ):
        raise ValueError("wrong research profile")
    if (
        value.get("certification_scope") != CERTIFICATION_SCOPE
        or type(value.get("certification_scope_version")) is not int
        or value.get("certification_scope_version") != CERTIFICATION_SCOPE_VERSION
    ):
        raise ValueError("wrong certification scope")
    if value.get("continuity_between_observations_certified") is not False:
        raise ValueError("continuity overclaim")
    if value.get("historical_polymarket_listing_completeness_claimed") is not False:
        raise ValueError("venue completeness overclaim")
    if any(isinstance(item, float | list | dict) for item in value.values()):
        raise ValueError("float/nested/opaque values prohibited")


COMMON_PROFILE = frozenset(profile_fields())
MAPPING_FIELDS = frozenset(
    {
        "schema",
        "asset",
        "slug",
        "market",
        "venue_market_id",
        "question",
        "start_us",
        "end_us",
        "up_token",
        "down_token",
        "interval_basis",
        "source_event_us",
        "archive_receipt_us",
        "source_sequence",
        "source_witness",
        "witness_set",
        "arrival_skew",
        "source_hour",
        "source_manifest_sha256",
        "source_product_sha256",
        "source_product_row_ordinal",
        *COMMON_PROFILE,
    }
)
OBSERVATION_FIELDS = frozenset(
    {
        "schema",
        "market",
        "asset",
        "token",
        "outcome",
        "start_us",
        "end_us",
        "source_event_us",
        "remaining_us",
        "archive_receipt_us",
        "receipt_kind",
        "source_sequence",
        "source_witness",
        "witness_set",
        "arrival_skew",
        "ask",
        "availability",
        "source_hour",
        "source_manifest_sha256",
        "source_product_sha256",
        "source_product_row_ordinal",
        *COMMON_PROFILE,
    }
)
RESOLUTION_FIELDS = frozenset(
    {
        "schema",
        "market",
        "asset",
        "winning_token",
        "winning_outcome",
        "source_event_us",
        "archive_receipt_us",
        "source_sequence",
        "source_witness",
        "witness_set",
        "arrival_skew",
        "evidence_kind",
        "source_hour",
        "source_manifest_sha256",
        "source_product_sha256",
        "source_product_row_ordinal",
        *COMMON_PROFILE,
    }
)


def validate_mapping(value: dict[str, Any]) -> None:
    _strict(value, MAPPING_FIELDS, MAPPING_SCHEMA)
    if type(value["start_us"]) is not int or type(value["end_us"]) is not int:
        raise ValueError("mapping interval integer invalid")
    if value["asset"] not in ASSETS or value["end_us"] - value["start_us"] != 300_000_000:
        raise ValueError("mapping interval invalid")
    if value["start_us"] % 300_000_000:
        raise ValueError("mapping interval unaligned")
    _identities(value)
    _token_id(value["up_token"])
    _token_id(value["down_token"])
    if value["up_token"] == value["down_token"]:
        raise ValueError("mapping token orientation ambiguous")
    for name in ("slug", "venue_market_id", "question", "interval_basis"):
        if not isinstance(value[name], str):
            raise ValueError("mapping text invalid")


def validate_observation(value: dict[str, Any]) -> None:
    _strict(value, OBSERVATION_FIELDS, OBSERVATION_SCHEMA)
    _identities(value)
    _token_id(value["token"])
    if value["asset"] not in ASSETS or value["outcome"] not in ("UP", "DOWN"):
        raise ValueError("observation asset/outcome invalid")
    for name in ("start_us", "end_us", "source_event_us", "remaining_us"):
        if type(value.get(name)) is not int:
            raise ValueError("observation clock integer invalid")
    if value["source_event_us"] is None or value["remaining_us"] is None:
        raise ValueError("recorded observation requires source event time")
    if not value["start_us"] <= value["source_event_us"] < value["end_us"]:
        raise ValueError("observation outside market interval")
    if value["remaining_us"] != value["end_us"] - value["source_event_us"]:
        raise ValueError("remaining time mismatch")
    if value["receipt_kind"] != "archive_collector_receipt_not_sender_http":
        raise ValueError("clock provenance mismatch")
    if value["ask"] is None:
        if value["availability"] != "source_null_unknown_reason":
            raise ValueError("null ask cannot become known absence")
    elif (
        not isinstance(value["ask"], str)
        or not re.fullmatch(r"[01]\.[0-9]{4}", value["ask"])
        or not Decimal(0) <= Decimal(value["ask"]) <= Decimal(1)
    ):
        raise ValueError("ask must retain exact scale and range")
    elif value["availability"] != "observed_ask":
        raise ValueError("non-null ask requires observed availability")


def validate_resolution(value: dict[str, Any]) -> None:
    _strict(value, RESOLUTION_FIELDS, RESOLUTION_SCHEMA)
    _identities(value)
    _token_id(value["winning_token"])
    if value["asset"] not in ASSETS or value["winning_outcome"] not in ("UP", "DOWN"):
        raise ValueError("resolution outcome invalid")
    if value["evidence_kind"] != "native_v3_archived_market_resolved":
        raise ValueError("resolution evidence kind invalid")


def _identities(value: dict[str, Any]) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value["market"]):
        raise ValueError("market identity invalid")
    for name in ("source_manifest_sha256", "source_product_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", value[name]):
            raise ValueError("source digest invalid")
    if not isinstance(value.get("source_hour"), str):
        raise ValueError("source hour invalid")
    try:
        hour_start = datetime.strptime(value["source_hour"], "%Y-%m-%d/%H").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("source hour invalid") from exc
    for name in ("archive_receipt_us", "source_product_row_ordinal"):
        if type(value.get(name)) is not int or value[name] < 0:
            raise ValueError("required provenance integer invalid")
    for name in ("source_event_us", "source_sequence", "arrival_skew"):
        if value.get(name) is not None and type(value[name]) is not int:
            raise ValueError("optional provenance integer invalid")
    if value.get("source_event_us") is not None and value["source_event_us"] < 0:
        raise ValueError("negative source event time")
    if value.get("source_sequence") is not None and not 0 <= value["source_sequence"] < 2**64:
        raise ValueError("source sequence invalid")
    hour_start_us = int(hour_start.timestamp() * 1_000_000)
    hour_end_us = int((hour_start + timedelta(hours=1)).timestamp() * 1_000_000)
    if not hour_start_us <= value["archive_receipt_us"] < hour_end_us:
        raise ValueError("archive receipt is outside its source hour")
    for name in ("source_witness", "witness_set"):
        if value.get(name) is not None and not isinstance(value[name], str):
            raise ValueError("witness provenance invalid")


def _token_id(value: Any) -> None:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[0-9]{1,78}", value)
        or not 0 <= int(value) < 2**256
    ):
        raise ValueError("token identity invalid")


def jsonl_gzip(rows: Iterable[dict[str, Any]]) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0, filename="") as zipped:
        for row in rows:
            zipped.write(canonical(row))
    return output.getvalue()


def read_jsonl_gzip(data: bytes) -> list[dict[str, Any]]:
    return list(iter_jsonl_gzip(data))


def iter_jsonl_gzip(data: bytes) -> Iterable[dict[str, Any]]:
    with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as zipped:
        for line in zipped:
            if line.strip():
                yield json.loads(line)


def select_window(days: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = sorted(
        (day for day in days if day.get("status") == "CERTIFIED"), key=lambda d: d["day"]
    )
    return valid[-30:]


def exact_affine_qualifies(observation: dict[str, Any], t: str, m: str, b: str) -> bool:
    """Exact integer-rational form of the frozen strict affine predicate."""
    if observation.get("schema") != OBSERVATION_SCHEMA or observation.get("ask") is None:
        return False
    values = [Decimal(item) for item in (t, m, b, observation["ask"])]
    if any(not item.is_finite() for item in values) or values[0] <= 0:
        raise ValueError("finite parameters and positive T required")
    remaining = Fraction(observation["remaining_us"], 1_000_000)
    exact = [Fraction(*item.as_integer_ratio()) for item in values]
    return 0 < remaining < exact[0] and exact[3] > exact[1] * remaining + exact[2]


def market_signal(observations: Iterable[dict[str, Any]], t: str, m: str, b: str) -> dict[str, Any]:
    """Select at most one earliest qualifying recorded observation; never interpolate."""
    qualified: list[dict[str, Any]] = []
    market: str | None = None
    for row in observations:
        validate_observation(row)
        if market is None:
            market = row["market"]
        elif market != row["market"]:
            raise ValueError("one market required")
        if exact_affine_qualifies(row, t, m, b):
            qualified.append(row)
    if not qualified:
        return {"status": "NO_RECORDED_QUALIFICATION", "signal": None}
    earliest = min(row["source_event_us"] for row in qualified)
    tied = [row for row in qualified if row["source_event_us"] == earliest]
    if len({row["outcome"] for row in tied}) != 1:
        return {"status": "INDETERMINATE_EQUAL_SOURCE_TIME", "signal": None}
    authority = {
        (
            row["ask"],
            row["archive_receipt_us"],
            row["source_sequence"],
            row["source_witness"],
            row["witness_set"],
        )
        for row in tied
    }
    if len(authority) != 1:
        return {"status": "INDETERMINATE_AUTHORITY_AMBIGUITY", "signal": None}
    chosen = min(
        tied,
        key=lambda row: (
            row["source_hour"],
            row["source_product_row_ordinal"],
            row["source_product_sha256"],
        ),
    )
    return {
        "status": "RECORDED_OBSERVATION_SIGNAL",
        "signal": {
            "market": chosen["market"],
            "outcome": chosen["outcome"],
            "source_event_us": chosen["source_event_us"],
            "remaining_us": chosen["remaining_us"],
            "ask": chosen["ask"],
            "profile": PROFILE,
            "first_meaning": "first_qualifying_recorded_observation_not_actual_market_crossing",
        },
    }
