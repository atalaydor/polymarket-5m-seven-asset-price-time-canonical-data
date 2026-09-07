import unittest
from unittest.mock import MagicMock, patch

from pflow.bounded_v1 import (
    POPULATION_CLAIM,
    PROFILE,
    SCOPE,
    _mapping_relation,
    _resolution_relation,
    profile_fields,
    require_import_profile,
    verify_window,
)
from pflow.salvage import _day_batches, certify_missing_days, coverage_summary


class BoundedProfileTests(unittest.TestCase):
    def test_profile_is_distinct_and_non_exhaustive(self) -> None:
        fields = profile_fields()
        self.assertEqual(PROFILE, "PENDULUMFLOW_V3_OBSERVED_BOUNDED_V1")
        self.assertEqual(fields["certification_scope"], SCOPE)
        self.assertFalse(fields["population_exhaustive"])
        self.assertFalse(fields["unresolved_conditions_out_of_scope"])
        self.assertFalse(fields["continuity_between_observations_certified"])
        self.assertFalse(fields["time_only_crossings_permitted"])
        self.assertFalse(fields["canonical_depth_fields_permitted"])
        self.assertIn("no claim", POPULATION_CLAIM)

    def test_stronger_profile_imports_fail_before_io(self) -> None:
        for profile in ("PENDULUMFLOW_V3_OBSERVED", "OWN_RECORDER_EXACT"):
            with self.assertRaisesRegex(ValueError, "cannot satisfy requested profile"):
                verify_window("ignored", "ignored", profile)
        require_import_profile(PROFILE)

    def test_mapping_and_resolution_orientation_are_exact(self) -> None:
        mapping = {
            "asset": "BTC",
            "start_us": 1,
            "end_us": 2,
            "up_token": "10",
            "down_token": "20",
        }
        observation = {
            "asset": "BTC",
            "start_us": 1,
            "end_us": 2,
            "outcome": "UP",
            "token": "10",
        }
        resolution = {"asset": "BTC", "winning_outcome": "DOWN", "winning_token": "20"}
        self.assertTrue(_mapping_relation(observation, mapping))
        self.assertTrue(_resolution_relation(resolution, mapping))
        observation["token"] = "20"
        resolution["winning_token"] = "10"
        self.assertFalse(_mapping_relation(observation, mapping))
        self.assertFalse(_resolution_relation(resolution, mapping))

    def test_salvage_coverage_selects_only_full_utc_days(self) -> None:
        hours = [f"2026-08-18/{hour:02d}" for hour in range(6, 24)]
        hours += [f"2026-08-19/{hour:02d}" for hour in range(24)]
        hours += [f"2026-08-20/{hour:02d}" for hour in range(12)]
        inventory = {
            "hours": [
                {"hour": hour, "manifest": {"bytes": index + 1}} for index, hour in enumerate(hours)
            ]
        }
        result = coverage_summary(inventory)
        self.assertEqual(result["first_hour"], "2026-08-18/06")
        self.assertEqual(result["last_hour"], "2026-08-20/11")
        self.assertEqual(result["complete_utc_days"], ["2026-08-19"])
        self.assertEqual(
            [item["day"] for item in result["partial_utc_days"]],
            [
                "2026-08-18",
                "2026-08-20",
            ],
        )

    def test_salvage_batches_are_bounded_and_order_preserving(self) -> None:
        days = [f"2026-08-{day:02d}" for day in range(1, 9)]
        self.assertEqual(
            _day_batches(days),
            [
                {"days": days[0:3]},
                {"days": days[3:6]},
                {"days": days[6:8]},
            ],
        )

    @patch("pflow.salvage.certify_day")
    @patch("pflow.salvage._terminal_days")
    def test_salvage_batch_reuses_terminal_siblings(
        self, terminal: MagicMock, certify: MagicMock
    ) -> None:
        terminal.return_value = {"2026-08-19": ({}, {}, {})}
        certify_missing_days(["2026-08-19", "2026-08-20"])
        certify.assert_called_once()
        self.assertEqual(certify.call_args.args[-1], "2026-08-20")


if __name__ == "__main__":
    unittest.main()
