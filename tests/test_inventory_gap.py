from __future__ import annotations

import unittest

from pflow.inventory_gap import summarize_index
from pflow.source import canonical, sha


class InventoryGapTests(unittest.TestCase):
    def test_summary_reconciles_partition_union_and_denies_authority(self) -> None:
        value = {
            "schema": "pendulumflow-v3-observed-data-index.v1",
            "profile": "PENDULUMFLOW_V3_OBSERVED",
            "profile_version": 1,
            "certification_scope": "PINNED_PUBLISHED_PENDULUMFLOW_V3_INVENTORY",
            "certification_scope_version": 1,
            "inventory_generation": "a" * 64,
            "inventory_tag": "inventory",
            "inventory_sha256": "b" * 64,
            "catalog_generation": "c" * 64,
            "catalog_tag": "catalog",
            "catalog_sha256": "d" * 64,
            "generation": "e" * 64,
            "complete_expected_partition_set": True,
            "target_membership_reconciled": False,
            "unresolved_condition_references": ["condition-1", "condition-2"],
            "unresolved_conditionless_rows": {"best_bid_ask": 0, "market_resolved": 0},
            "partitions": [
                {"unresolved_condition_references": ["condition-1"]},
                {"unresolved_condition_references": ["condition-1", "condition-2"]},
            ],
            "measurements": {
                "downloaded_bytes": 123,
                "network_seconds_us": 4,
                "wall_seconds_us": 5,
            },
        }
        value["generation"] = sha(
            canonical({key: item for key, item in value.items() if key != "generation"})
        )
        report = summarize_index(value)
        self.assertEqual(report["unresolved_unique_condition_count"], 2)
        self.assertEqual(report["partition_condition_reference_count"], 3)
        self.assertEqual(
            report["unresolved_condition_set_sha256"],
            sha(canonical(["condition-1", "condition-2"])),
        )
        self.assertFalse(report["diagnostic_research_import_allowed"])
        self.assertEqual(report["diagnostic_certified_days"], [])
        self.assertEqual(report["profile"], "PENDULUMFLOW_V3_OBSERVED")

    def test_summary_rejects_unreconciled_global_and_partition_sets(self) -> None:
        value = {
            "schema": "pendulumflow-v3-observed-data-index.v1",
            "profile": "PENDULUMFLOW_V3_OBSERVED",
            "profile_version": 1,
            "certification_scope": "PINNED_PUBLISHED_PENDULUMFLOW_V3_INVENTORY",
            "certification_scope_version": 1,
            "complete_expected_partition_set": True,
            "target_membership_reconciled": False,
            "unresolved_condition_references": ["condition-1"],
            "unresolved_conditionless_rows": {},
            "partitions": [{"unresolved_condition_references": ["condition-2"]}],
            "measurements": {},
        }
        value["generation"] = sha(canonical(value))
        with self.assertRaises(ValueError):
            summarize_index(value)


if __name__ == "__main__":
    unittest.main()
