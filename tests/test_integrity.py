from __future__ import annotations

import unittest
from dataclasses import replace
from decimal import Decimal as D

from pflow.integrity import Counters, Event, State, diagnose, require_counter_export
from pflow.model import certification_reasons
from pflow.source import canonical, product_contract


def book(time: int, size: str = "2", hour: str = "2026-08-28/11") -> Event:
    return Event(
        "book",
        hour,
        time,
        time + 10,
        time,
        "a",
        "|a|e|",
        asks=((D(".5"), D("1")), (D(".9"), D(size))),
    )


def delta(time: int, price: str, size: str, ask: str) -> Event:
    return Event(
        "price_change",
        "2026-08-28/11",
        time,
        time + 10,
        time,
        "a",
        "|a|e|",
        ask=D(ask),
        price=D(price),
        size=D(size),
        side="SELL",
    )


def bba(time: int, ask: str) -> Event:
    return Event(
        "best_bid_ask",
        "2026-08-28/11",
        time,
        time + 11,
        time + 1,
        "a",
        "|a|e|",
        ask=D(ask),
    )


class IntegrityTests(unittest.TestCase):
    def test_missing_persistent_change_is_detected_and_next_book_resets(self) -> None:
        events = [book(100), delta(200, ".45", "2", ".45"), bba(200, ".45")]
        self.assertEqual(diagnose(events)["bba_ask_disagreements"], 0)
        missing = diagnose([events[0], events[2]])
        self.assertEqual(missing["bba_ask_disagreements"], 1)
        restored = diagnose([*events, book(300), bba(301, ".5")])
        self.assertEqual(restored["anchor_state_disagreements"], 1)
        self.assertEqual(restored["bba_ask_disagreements"], 0)

    def test_unrecorded_reverted_excursion_is_not_identifiable(self) -> None:
        # A common later non-touch update gives the last snapshot the same
        # state AND last-change timestamp in both venue histories.
        common = [
            book(100),
            delta(400, ".9", "3", ".5"),
            bba(400, ".5"),
            replace(book(400, "3", "2026-08-28/12"), receipt_us=510, sequence=500),
        ]
        hidden = [
            delta(200, ".45", "2", ".45"),
            bba(200, ".45"),
            delta(300, ".45", "0", ".5"),
            bba(300, ".5"),
        ]
        venue_with_excursion = [common[0], *hidden, *common[1:]]

        def admitted(venue: list[Event]) -> list[Event]:
            # Collector sequence is allocated on admission, not venue emission.
            retained = [e for e in venue if e.event_us not in {200, 300}]
            return [replace(e, sequence=i + 1000) for i, e in enumerate(retained)]

        a, b = admitted(common), admitted(venue_with_excursion)
        self.assertEqual(a, b)
        self.assertEqual(canonical(diagnose(a)), canonical(diagnose(b)))
        self.assertEqual(diagnose(a)["anchor_state_disagreements"], 0)
        self.assertEqual(diagnose(a)["delta_ask_disagreements"], 0)
        self.assertEqual(diagnose(a)["bba_ask_disagreements"], 0)
        self.assertEqual(diagnose(a)["non_successor_local_sequences"], 0)
        self.assertEqual(diagnose(a)["boundary_carried_states"], 1)
        without, with_excursion = State(), State()
        without.apply(common[0])
        with_excursion.apply(common[0])
        with_excursion.apply(hidden[0])
        self.assertNotEqual(without.best(), with_excursion.best())
        self.assertIn("target_continuity", certification_reasons({}))

    def test_unchanged_receipts_ambiguity_and_witnesses_are_not_collapsed(self) -> None:
        events = [
            book(100),
            delta(200, ".45", "2", ".45"),
            replace(delta(200, ".45", "0", ".5"), receipt_us=212, sequence=202),
            bba(200, ".5"),
            bba(300, ".5"),
        ]
        counts = diagnose(events)
        self.assertEqual(counts["ambiguous_source_time_bba"], 1)
        self.assertEqual(counts["unchanged_bba_later_receipts"], 1)
        self.assertEqual(counts["multiple_witness_rows"], 5)
        self.assertEqual(
            diagnose([events[0], replace(events[0], witness="e")])["distinct_selected_witnesses"], 2
        )

    def test_only_fixed_diagnostic_counts_leave_replay(self) -> None:
        valid = diagnose([book(100)])
        require_counter_export(valid)
        for forbidden in ("asks", "bids", "quantity", "raw_payload", "depth_hash"):
            with self.assertRaises(ValueError):
                require_counter_export({**valid, forbidden: 1})
        with self.assertRaises(ValueError):
            require_counter_export({**valid, "rows": True})
        with self.assertRaises(ValueError):
            State().apply(replace(book(100), asks=((D(".5"), D("-1")),)))
        # The existing production-facing acquisition allowlist is unchanged.
        for product in ("book", "price_change"):
            with self.assertRaises(ValueError):
                product_contract({}, product)

    def test_missing_clocks_remain_explicit(self) -> None:
        result = diagnose([], Counters(missing_clock_rows=2, missing_witness_rows=1))
        self.assertEqual(result["rows"], 0)
        self.assertEqual(result["missing_clock_rows"], 2)


if __name__ == "__main__":
    unittest.main()
