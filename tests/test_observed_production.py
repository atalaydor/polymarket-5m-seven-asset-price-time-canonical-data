from __future__ import annotations

import base64
import unittest
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import patch

from pflow.inventory import parse_page, validate_inventory
from pflow.model import mapping
from pflow.observed_v1 import (
    exact_affine_qualifies,
    market_signal,
    observation_record,
    profile_fields,
    select_window,
    validate_observation,
)
from pflow.production import (
    DAY_SCHEMA,
    TRANSFORM_IMPLEMENTATION_FILES,
    _chunks,
    _day_batches,
    _existing_partition,
    _implementation_bundle_digest,
    _rolling_day_set_advances,
    _target_like,
    _work_batches,
)
from pflow.production_consumer import _validate_day
from pflow.source import canonical, sha


class ObservedProductionTests(unittest.TestCase):
    def identity(self) -> dict[str, Any]:
        value = mapping(
            {
                "slug": "btc-updown-5m-1788609600",
                "outcomes": ["Up", "Down"],
                "assets_ids": [bytes([1]) * 32, bytes([2]) * 32],
                "market": bytes([3]) * 32,
                "id": "100",
                "question": "BTC Up or Down",
            }
        )
        assert value is not None
        return value

    def observation(self, outcome: str = "UP", event_offset: int = 1) -> dict[str, Any]:
        identity = self.identity()
        event = datetime.fromtimestamp((identity["start_us"] + event_offset) / 1_000_000, UTC)
        return observation_record(
            {
                "asset_id": bytes([1 if outcome == "UP" else 2]) * 32,
                "best_ask": Decimal("0.6000"),
                "timestamp": event,
                "timestamp_received": event,
                "sequence": 7,
                "source_witness": "w1",
                "witness_set": "|w1|",
                "arrival_skew": 0,
            },
            identity,
            {
                "source_hour": event.strftime("%Y-%m-%d/%H"),
                "source_manifest_sha256": "a" * 64,
                "source_product_sha256": "b" * 64,
                "source_product_row_ordinal": 1,
            },
        )

    def test_inventory_page_and_generation_are_strict(self) -> None:
        raw = b'<a href="/v3/2026-09-05/00/"></a><a href="/v3/?page=2">next</a>'
        self.assertEqual(
            parse_page(raw, 1),
            (["2026-09-05/00"], "https://archive.pendulumflow.com/v3/?page=2"),
        )
        with self.assertRaises(ValueError):
            parse_page(raw.replace(b"page=2", b"page=3"), 1)
        for malformed in (
            b'<a href="/v3/2026-9-05/00/"></a>',
            b'<a href="/v3/2026-09-05/00/"></a><a href="?page=2">next</a>',
        ):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                parse_page(malformed, 1)
        manifest = {
            "hour": "2026-09-05/00",
            "file": "hour.parquet",
            "bytes": 1000,
            "sha256": "c" * 64,
            "products": {
                product: {
                    "byte_range": [4 + index * 100, 100 + index * 100],
                    "row_groups": [index, index],
                    "row_count": 0,
                    "sha256": f"{index + 1:064x}",
                }
                for index, product in enumerate(("new_market", "best_bid_ask", "market_resolved"))
            },
        }
        manifest_raw = canonical(manifest)
        terminal_page = b'<a href="/v3/2026-09-05/00/"></a>'
        item = {
            "hour": "2026-09-05/00",
            "manifest_sha256": sha(manifest_raw),
            "manifest_raw_base64": base64.b64encode(manifest_raw).decode(),
            "manifest": manifest,
        }
        inventory: dict[str, Any] = {
            "schema": "pendulumflow-v3-published-inventory.v1",
            "hours": [item],
            "index_pages": [
                {
                    "page": 1,
                    "url": "https://archive.pendulumflow.com/v3/",
                    "sha256": sha(terminal_page),
                    "size": len(terminal_page),
                    "content_base64": base64.b64encode(terminal_page).decode(),
                    "parsed_hours": ["2026-09-05/00"],
                    "next_page": None,
                }
            ],
        }
        inventory["generation"] = sha(canonical(inventory))
        validate_inventory(inventory)
        truncated = deepcopy(inventory)
        truncated_page = raw
        truncated["index_pages"][0].update(
            {
                "content_base64": base64.b64encode(truncated_page).decode(),
                "sha256": sha(truncated_page),
                "size": len(truncated_page),
                "next_page": "https://archive.pendulumflow.com/v3/?page=2",
            }
        )
        truncated["generation"] = sha(
            canonical({key: value for key, value in truncated.items() if key != "generation"})
        )
        with self.assertRaises(ValueError):
            validate_inventory(truncated)
        inventory["hours"] = [item, item]
        with self.assertRaises(ValueError):
            validate_inventory(inventory)

    def test_no_depth_and_repeated_observations_survive(self) -> None:
        first = self.observation(event_offset=1)
        second = self.observation(event_offset=2)
        validate_observation(first)
        self.assertNotEqual(canonical(first), canonical(second))
        for forbidden in ("quantity", "levels", "bids", "asks", "raw_payload", "liquidity"):
            with self.assertRaises(ValueError):
                validate_observation({**first, forbidden: "forbidden"})
        invalid = (
            {"certification_scope_version": 999},
            {"remaining_us": "299999999"},
            {"availability": "unknown"},
            {"source_product_row_ordinal": True},
            {"source_sequence": -1},
            {"archive_receipt_us": first["archive_receipt_us"] + 3_600_000_000},
            {"ask": "1.9999"},
        )
        for mutation in invalid:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_observation({**first, **mutation})

    def test_exact_recorded_predicate_and_equal_time_tie(self) -> None:
        up = self.observation("UP", event_offset=299_000_000)
        self.assertTrue(exact_affine_qualifies(up, "2", "0.1", "0.4"))
        self.assertFalse(exact_affine_qualifies(up, "1", "0.1", "0.4"))
        self.assertEqual(
            market_signal([up], "2", "0.1", "0.4")["status"],
            "RECORDED_OBSERVATION_SIGNAL",
        )
        down = self.observation("DOWN", event_offset=299_000_000)
        self.assertEqual(
            market_signal([up, down], "2", "0.1", "0.4")["status"],
            "INDETERMINATE_EQUAL_SOURCE_TIME",
        )

    def test_30_to_31_selects_latest_by_day(self) -> None:
        days = [{"status": "CERTIFIED", "day": f"2026-08-{day:02d}"} for day in range(1, 32)]
        selected = select_window(reversed(days))
        self.assertEqual(len(selected), 30)
        self.assertEqual(selected[0]["day"], "2026-08-02")
        failed = [*days, {"status": "EXCLUDED", "day": "2026-09-01"}]
        self.assertEqual(select_window(failed), selected)

    def test_work_batches_stay_bounded_and_complete(self) -> None:
        items = [{"id": str(index), "hours": str(index)} for index in range(301)]
        batches = _work_batches(items, 128)
        self.assertLessEqual(len(batches), 128)
        self.assertEqual([item for batch in batches for item in batch["items"]], items)
        days = [f"2026-01-{day:02d}" for day in range(1, 32)] * 9
        day_batches = _day_batches(days, 128)
        self.assertLessEqual(len(day_batches), 128)
        self.assertEqual([day for batch in day_batches for day in batch["days"]], days)

    def test_calendar_chunks_isolate_late_historical_hour(self) -> None:
        def item(hour: str) -> dict[str, Any]:
            products = {
                name: {
                    "byte_range": [4, 10],
                    "row_groups": [0, 0],
                    "row_count": 1,
                    "sha256": sha((hour + name).encode()),
                }
                for name in ("new_market", "best_bid_ask", "market_resolved")
            }
            return {
                "hour": hour,
                "manifest_sha256": sha(hour.encode()),
                "manifest": {"products": products},
            }

        original_hours = ["2026-09-05/00", "2026-09-05/02", "2026-09-05/04"]
        original = {"hours": [item(hour) for hour in original_hours]}
        added_hours = ["2026-09-05/00", "2026-09-05/01", "2026-09-05/02", "2026-09-05/04"]
        added = {"hours": [item(hour) for hour in added_hours]}
        old = _chunks(original_hours, 4, "data", original)
        new = _chunks(added_hours, 4, "data", added)
        self.assertEqual(old[-1], new[-1])
        self.assertNotEqual(old[0], new[0])

    def test_target_like_classification_catches_alternate_and_null_slugs(self) -> None:
        self.assertTrue(_target_like("btc-up-or-down-5m-1788609600", None))
        self.assertTrue(_target_like("", "Bitcoin Up or Down 5 minute market"))
        self.assertTrue(_target_like("", "Bitcoin Up or Down tomorrow"))
        self.assertTrue(_target_like("broken-slug", "Bitcoin Up or Down 5 minute market"))
        self.assertFalse(_target_like("bitcoin-up-or-down-tomorrow", "Bitcoin tomorrow"))

    def test_transform_bundle_changes_only_for_bound_inputs(self) -> None:
        base = {"production.py": b"a", "observed_v1.py": b"b"}
        self.assertNotEqual(
            _implementation_bundle_digest(base),
            _implementation_bundle_digest({**base, "observed_v1.py": b"changed"}),
        )
        self.assertFalse(any(name.startswith("docs/") for name in TRANSFORM_IMPLEMENTATION_FILES))

    def test_current_window_handles_29_to_31_without_allowing_shrink(self) -> None:
        old = [f"2026-07-{day:02d}" for day in range(1, 30)]
        incoming = [*old, "2026-07-30", "2026-07-31"][-30:]
        self.assertTrue(_rolling_day_set_advances(old, incoming))
        self.assertFalse(_rolling_day_set_advances([*old, "2026-07-30"], ["2026-07-31"]))

    def test_partition_recovery_deletes_only_empty_report_starter(self) -> None:
        release = {
            "id": 11,
            "draft": True,
            "assets": [
                {
                    "id": 12,
                    "name": "a" * 64 + "--report.json",
                    "state": "starter",
                    "size": 0,
                    "digest": None,
                }
            ],
        }
        with patch("pflow.production.api", side_effect=[release, None]) as mocked:
            self.assertIsNone(_existing_partition("tag", "schema", "partition"))
        self.assertEqual(mocked.call_args_list[-1].args, ("releases/assets/12", "DELETE"))

    def test_consumer_rejects_empty_future_or_wrong_scope_day(self) -> None:
        source = {
            "release_id": 3,
            "asset_id": 4,
            "sha256": "d" * 64,
            "size": 10,
            "partition": "e" * 64,
        }
        day: dict[str, Any] = {
            "schema": DAY_SCHEMA,
            **profile_fields(),
            "status": "CERTIFIED",
            "day": "2026-08-28",
            "claim": "fixture",
            "limitations": [
                "no historical venue-listing completeness",
                "no continuity or missed-excursion exclusion",
                "no synthetic or time-only crossings",
                "not sender execution reconstruction",
            ],
            "inventory_generation": "1" * 64,
            "inventory_last_hour": "2026-09-05/00",
            "inventory_tag": "v3-inventory-v1-" + "1" * 64,
            "inventory_sha256": "2" * 64,
            "inventory_release_id": 1,
            "catalog_generation": "3" * 64,
            "catalog_tag": "observed-catalog-v1-" + "3" * 64,
            "catalog_sha256": "4" * 64,
            "data_index_generation": "5" * 64,
            "data_index_tag": "observed-data-index-v1-" + "5" * 64,
            "data_index_sha256": "6" * 64,
            "transform": "pendulumflow-v3-observed-inventory-projection.v1",
            "transform_implementation_sha256": "8" * 64,
            "mapping_schema": "pendulumflow-v3-observed-mapping.v1",
            "observation_schema": "pendulumflow-v3-observed-observation.v1",
            "resolution_schema": "pendulumflow-v3-observed-resolution.v1",
            "market_count": 1,
            "observation_count": 2,
            "resolution_count": 1,
            "missing_sides": [],
            "missing_resolutions": [],
            "contradictory_resolutions": [],
            "source_errors": [],
            "certification_reasons": [],
            "best_ask_side_gate": "at_least_one_non_null_recorded_ask_per_outcome_token",
            "source_assets": [source],
            "mapping_data_sha256": "7" * 64,
            "mapping_data_size": 10,
            "canonical_observation_shards": [source],
            "research_import_allowed": True,
        }
        day["generation"] = sha(canonical(day))
        reference = {
            "day": day["day"],
            "generation": day["generation"],
            "tag": "observed-day-v1-" + day["generation"],
            "release_id": 2,
        }
        release = {"tag_name": reference["tag"], "id": 2}
        _validate_day(day, reference, release)
        for mutation in (
            {"market_count": 0},
            {"day": "2999-01-01"},
            {"certification_scope_version": 999},
        ):
            changed = {**day, **mutation}
            changed.pop("generation")
            changed["generation"] = sha(canonical(changed))
            changed_reference = {
                **reference,
                "day": changed["day"],
                "generation": changed["generation"],
            }
            changed_release = {
                **release,
                "tag_name": "observed-day-v1-" + changed["generation"],
            }
            changed_reference["tag"] = changed_release["tag_name"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                _validate_day(changed, changed_reference, changed_release)


if __name__ == "__main__":
    unittest.main()
