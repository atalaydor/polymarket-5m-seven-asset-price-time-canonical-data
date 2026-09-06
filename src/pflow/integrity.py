"""Transient ask-state diagnostics. Agreement is NOT a continuity certificate.

No serializer accepts an Event or State. The only export is fixed integer counters.
Local receipt/sequence order is a diagnostic hypothesis within ONE selected witness;
merging it does not reconstruct the copies discarded from other witnesses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class Event:
    product: str
    hour: str
    event_us: int
    receipt_us: int
    sequence: int
    witness: str
    witnesses: str
    ask: Decimal | None = None
    price: Decimal | None = None
    size: Decimal | None = None
    side: str | None = None
    asks: tuple[tuple[Decimal, Decimal], ...] = ()


@dataclass
class Counters:
    rows: int = 0
    book_rows: int = 0
    price_change_rows: int = 0
    best_bid_ask_rows: int = 0
    multiple_witness_rows: int = 0
    distinct_selected_witnesses: int = 0
    boundary_carried_states: int = 0
    non_successor_local_sequences: int = 0
    non_increasing_local_sequences: int = 0
    source_time_regressions: int = 0
    equal_local_order_keys: int = 0
    anchor_comparisons: int = 0
    anchor_state_disagreements: int = 0
    equal_ask_at_later_anchor: int = 0
    unanchored_delta_rows: int = 0
    delta_ask_comparisons: int = 0
    delta_ask_disagreements: int = 0
    bba_ask_comparisons: int = 0
    bba_ask_disagreements: int = 0
    unchanged_bba_later_receipts: int = 0
    ambiguous_source_time_bba: int = 0
    bba_delta_same_time_comparisons: int = 0
    bba_delta_same_time_disagreements: int = 0
    missing_clock_rows: int = 0
    missing_witness_rows: int = 0


@dataclass
class State:
    levels: dict[Decimal, Decimal] = field(default_factory=dict)
    anchored: bool = False

    def best(self) -> Decimal | None:
        return min(self.levels, default=None)

    def apply(self, event: Event) -> None:
        if event.product == "book":
            if len({p for p, _ in event.asks}) != len(event.asks):
                raise ValueError("duplicate snapshot price")
            self.levels = {}
            for price, size in event.asks:
                self.assign(price, size)
            self.anchored = True
        elif event.product == "price_change":
            if event.side not in {"BUY", "SELL"}:
                raise ValueError("unknown change side")
            if event.price is None or event.size is None:
                raise ValueError("missing exact delta")
            if event.side == "SELL" and self.anchored:
                self.assign(event.price, event.size)

    def assign(self, price: Decimal, size: Decimal) -> None:
        if not isinstance(price, Decimal) or not isinstance(size, Decimal):
            raise ValueError("float/non-exact depth rejected")
        if not price.is_finite() or not size.is_finite() or not 0 <= price <= 1 or size < 0:
            raise ValueError("invalid transient level")
        if size == 0:
            self.levels.pop(price, None)
        else:
            self.levels[price] = size


def diagnose(events: list[Event], counters: Counters | None = None) -> dict[str, int]:
    result = counters or Counters()
    witnesses = sorted({event.witness for event in events})
    result.distinct_selected_witnesses = len(witnesses)
    # Candidate same-source-time comparison; ambiguous millisecond buckets are
    # counted and excluded, never tie-broken into invented venue ordering.
    delta_asks: dict[tuple[str, int], set[Decimal | None]] = {}
    for event in events:
        if event.product == "price_change":
            delta_asks.setdefault((event.witness, event.event_us), set()).add(event.ask)
    for witness in witnesses:
        state = State()
        previous: Event | None = None
        previous_bba: Event | None = None
        local = sorted(
            (e for e in events if e.witness == witness),
            key=lambda e: (e.receipt_us, e.sequence),
        )
        for event in local:
            result.rows += 1
            result.multiple_witness_rows += len(event.witnesses.strip("|").split("|")) > 1
            if previous is not None:
                result.non_successor_local_sequences += event.sequence != previous.sequence + 1
                result.non_increasing_local_sequences += event.sequence <= previous.sequence
                result.source_time_regressions += event.event_us < previous.event_us
                result.equal_local_order_keys += (event.receipt_us, event.sequence) == (
                    previous.receipt_us,
                    previous.sequence,
                )
                result.boundary_carried_states += state.anchored and event.hour != previous.hour
            if event.product == "book":
                result.book_rows += 1
                before = state.levels.copy() if state.anchored else None
                best_before = state.best()
                state.apply(event)
                if before is not None:
                    result.anchor_comparisons += 1
                    result.anchor_state_disagreements += state.levels != before
                    result.equal_ask_at_later_anchor += state.best() == best_before
            elif event.product == "price_change":
                result.price_change_rows += 1
                result.unanchored_delta_rows += not state.anchored
                state.apply(event)
                if state.anchored and event.ask is not None:
                    result.delta_ask_comparisons += 1
                    result.delta_ask_disagreements += state.best() != event.ask
            elif event.product == "best_bid_ask":
                result.best_bid_ask_rows += 1
                if state.anchored and event.ask is not None:
                    result.bba_ask_comparisons += 1
                    result.bba_ask_disagreements += state.best() != event.ask
                if previous_bba is not None:
                    result.unchanged_bba_later_receipts += (
                        event.ask == previous_bba.ask and event.receipt_us > previous_bba.receipt_us
                    )
                previous_bba = event
                candidates = delta_asks.get((witness, event.event_us), set())
                if len(candidates) > 1:
                    result.ambiguous_source_time_bba += 1
                elif candidates and None not in candidates and event.ask is not None:
                    result.bba_delta_same_time_comparisons += 1
                    result.bba_delta_same_time_disagreements += event.ask not in candidates
            else:
                raise ValueError("unexpected integrity product")
            previous = event
    return {key: int(value) for key, value in asdict(result).items()}


def require_counter_export(value: dict[str, int]) -> None:
    if value.keys() != asdict(Counters()).keys():
        raise ValueError("only fixed diagnostic counter fields may be exported")
    if any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError("diagnostic exports accept only non-negative integer counters")
