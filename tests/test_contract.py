from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import patch

from pflow.model import certification_reasons, mapping, micros, quote, validate_quote
from pflow.release import verify_release
from pflow.source import canonical, product_contract, sha, valid_url


class ContractTests(unittest.TestCase):
    def identity(self) -> dict[str, Any]:
        result = mapping(
            {
                "slug": "btc-updown-5m-1788609600",
                "outcomes": ["Down", "Up"],
                "assets_ids": [bytes([1]) * 32, bytes([2]) * 32],
                "market": bytes([3]) * 32,
                "id": "100",
                "question": "BTC Up or Down",
            }
        )
        assert result is not None
        return result

    def row(self) -> dict[str, Any]:
        return {
            "best_ask": Decimal("0.1234"),
            "asset_id": bytes([2]) * 32,
            "timestamp": datetime(2026, 9, 5, 12, tzinfo=UTC),
            "timestamp_received": datetime(2026, 9, 5, 12, 0, 0, 123457, tzinfo=UTC),
            "sequence": 2**63 + 123,
            "source_witness": "e",
            "witness_set": "|b|e|",
            "arrival_skew": 43,
        }

    def test_exact_prices_times_and_repeated_receipts(self) -> None:
        row = self.row()
        first = quote(row, self.identity(), "2026-09-05/12", "f" * 64, 0)
        validate_quote(first)
        self.assertEqual(first["ask"], "0.1234")
        self.assertEqual(first["archive_receipt_us"] % 1_000_000, 123457)
        row["timestamp_received"] = row["timestamp_received"].replace(microsecond=123458)
        second = quote(row, self.identity(), "2026-09-05/12", "f" * 64, 1)
        self.assertNotEqual(canonical(first), canonical(second))
        self.assertEqual(first["source_sequence"], 2**63 + 123)

    def test_null_is_not_known_absence(self) -> None:
        row = self.row()
        row["best_ask"] = None
        value = quote(row, self.identity(), "2026-09-05/12", "f" * 64, 0)
        self.assertEqual(value["availability"], "source_null_unknown_reason")
        self.assertEqual(value["continuity"], "unproven")

    def test_depth_and_raw_escape_hatches_rejected(self) -> None:
        value = quote(self.row(), self.identity(), "2026-09-05/12", "f" * 64, 0)
        for key in ("size", "quantity", "bids", "asks", "liquidity", "raw_payload"):
            with self.assertRaises(ValueError):
                validate_quote({**value, key: "anything"})
        for product in ("book", "price_change", "last_trade_price"):
            with self.assertRaises(ValueError):
                product_contract({}, product)

    def test_float_intermediate_rejected(self) -> None:
        row = self.row()
        row["best_ask"] = 0.1234
        with self.assertRaises(ValueError):
            quote(row, self.identity(), "2026-09-05/12", "f" * 64, 0)

    def test_outcome_alignment_and_naive_time(self) -> None:
        self.assertEqual(self.identity()["up_token"], str(int.from_bytes(bytes([2]) * 32, "big")))
        with self.assertRaises(ValueError):
            micros(datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            mapping({"slug": "btc-updown-5m-1788609600", "outcomes": ["Yes", "No"]})

    def test_missing_delayed_boundary_and_ambiguity_fail_closed(self) -> None:
        reasons = certification_reasons({"complete_utc_day": True, "source_integrity": True})
        for gate in (
            "independent_target_universe",
            "target_continuity",
            "opening_state",
            "both_side_history",
            "boundary_dependencies",
            "official_resolutions",
            "unique_mapping",
        ):
            self.assertIn(gate, reasons)

    def test_scope_url_and_ranges(self) -> None:
        for url in (
            "http://archive.pendulumflow.com/v3/",
            "https://example.com/v3/",
            "https://archive.pendulumflow.com/pmxt/",
        ):
            with self.assertRaises(ValueError):
                valid_url(url)
        bad = {
            "bytes": 500,
            "products": {
                "best_bid_ask": {"byte_range": [4, 501], "row_groups": [0, 1], "sha256": "0" * 64}
            },
        }
        with self.assertRaises(ValueError):
            product_contract(bad, "best_bid_ask")

    def test_sealed_verification_rejects_partial_mutable_and_corrupt(self) -> None:
        payload = canonical({"evidence": "fixture"})
        name = sha(payload) + "--fixture.json"
        release: dict[str, Any] = {
            "draft": False,
            "prerelease": False,
            "immutable": True,
            "assets": [{"name": name, "state": "uploaded"}],
        }
        with patch("pflow.release.read_asset", return_value=payload):
            verify_release(release, {name: payload})
            changes: list[dict[str, Any]] = [{"draft": True}, {"immutable": False}, {"assets": []}]
            for change in changes:
                with self.assertRaises(ValueError):
                    verify_release({**release, **change}, {name: payload})
        with (
            patch("pflow.release.read_asset", return_value=b"corrupt"),
            self.assertRaises(ValueError),
        ):
            verify_release(release, {name: payload})


if __name__ == "__main__":
    unittest.main()
