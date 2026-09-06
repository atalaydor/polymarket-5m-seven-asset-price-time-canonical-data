import unittest
from datetime import UTC, datetime
from typing import Any

from pflow.target_salvage import (
    TARGET_SCOPE,
    _day_entries,
    _mapping_relation,
    scope_fields,
)


def event(slot: int) -> dict[str, Any]:
    start = int(datetime(2026, 8, 25, tzinfo=UTC).timestamp()) + slot * 300
    end = start + 300
    condition = f"0x{slot + 1:064x}"
    return {
        "id": str(1000 + slot),
        "slug": f"btc-updown-5m-{start}",
        "startTime": datetime.fromtimestamp(start, UTC).isoformat().replace("+00:00", "Z"),
        "endDate": datetime.fromtimestamp(end, UTC).isoformat().replace("+00:00", "Z"),
        "series": [{"id": "10684"}],
        "markets": [
            {
                "id": str(2000 + slot),
                "conditionId": condition,
                "eventStartTime": datetime.fromtimestamp(start, UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "endDate": datetime.fromtimestamp(end, UTC).isoformat().replace("+00:00", "Z"),
                "clobTokenIds": [str(3000 + slot * 2), str(3001 + slot * 2)],
                "outcomes": ["Up", "Down"],
            }
        ],
    }


def report() -> dict[str, Any]:
    parameters = {
        "closed": "true",
        "end_date_min": "2026-08-25T00:00:00Z",
    }
    return {
        "evidence": {
            "scans": [
                {
                    "parameters": parameters,
                    "error": None,
                    "terminal_observed": True,
                    "duplicate_ids": [],
                    "rows": [event(slot) for slot in range(288)],
                },
                {
                    "parameters": {
                        "closed": "false",
                        "end_date_min": "2026-08-25T00:00:00Z",
                    },
                    "error": None,
                    "terminal_observed": True,
                    "duplicate_ids": [],
                    "rows": [],
                },
            ]
        }
    }


class TargetSalvageTests(unittest.TestCase):
    def test_target_day_is_exact_terminal_positive_catalog(self) -> None:
        rows = _day_entries(report(), "BTC", "2026-08-25")
        self.assertEqual(len(rows), 288)
        self.assertEqual(rows[0]["up_token"], "3000")
        self.assertEqual(rows[-1]["down_token"], str(3001 + 287 * 2))

    def test_target_day_rejects_silent_slot_loss(self) -> None:
        value = report()
        value["evidence"]["scans"][0]["rows"].pop()
        with self.assertRaisesRegex(ValueError, "not 288"):
            _day_entries(value, "BTC", "2026-08-25")

    def test_target_day_rejects_orientation_ambiguity(self) -> None:
        value = report()
        market = value["evidence"]["scans"][0]["rows"][0]["markets"][0]
        market["outcomes"] = ["Yes", "No"]
        with self.assertRaisesRegex(ValueError, "identity is ambiguous"):
            _day_entries(value, "BTC", "2026-08-25")

    def test_join_requires_authoritative_orientation(self) -> None:
        target = _day_entries(report(), "BTC", "2026-08-25")[0]
        mapping = dict(target)
        mapping["up_token"], mapping["down_token"] = mapping["down_token"], mapping["up_token"]
        self.assertFalse(_mapping_relation(target, mapping))

    def test_scope_is_mechanically_distinct_and_zero_continuity(self) -> None:
        value = scope_fields()
        self.assertEqual(value["certification_scope"], TARGET_SCOPE)
        self.assertFalse(value["continuity_between_observations_certified"])
        self.assertFalse(value["historical_deleted_listing_completeness_claimed"])


if __name__ == "__main__":
    unittest.main()
