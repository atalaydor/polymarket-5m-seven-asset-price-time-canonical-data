import unittest

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


if __name__ == "__main__":
    unittest.main()
