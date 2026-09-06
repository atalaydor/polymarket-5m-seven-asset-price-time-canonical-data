"""Catalog metadata must never become a foreign price/outcome data channel."""

from __future__ import annotations

import unittest
from copy import deepcopy
from typing import Any

import test_contract

from pflow.catalog_probe import (
    PRIOR_SHA,
    PRIOR_TAG,
    SCAN_SCOPE,
    SCHEMA,
    SCOPE,
    prior_identities,
    project,
    scan,
    validate_report,
)
from pflow.model import ASSETS, quote
from pflow.source import canonical, sha


class FakeReader:
    def __init__(self, pages: list[Any]) -> None:
        self.pages = iter(pages)
        self.urls: list[str] = []

    def get(self, url: str) -> tuple[Any, dict[str, Any]]:
        self.urls.append(url)
        return next(self.pages), {"url": url, "status": 200}


class CatalogTests(unittest.TestCase):
    def test_foreign_data_removed_at_every_level(self) -> None:
        raw = {
            "id": "1",
            "outcomes": '["Up","Down"]',
            "clobTokenIds": '["11","22"]',
            "bestAsk": 0.99,
            "outcomePrices": '["1","0"]',
            "winner": True,
            "bids": [{"price": "0.2", "size": "100"}],
            "raw_payload": {"secret": 1},
            "events": [{"id": "2", "volume": 100, "series": [{"id": "3", "liquidity": 5}]}],
        }
        projected = project(raw, "market")
        self.assertEqual(projected["outcomes"], ["Up", "Down"])
        self.assertEqual(project(projected, "market"), projected)
        self.assertNotIn("bestAsk", projected)
        self.assertNotIn("winner", projected)
        self.assertNotIn("volume", projected["events"][0])
        self.assertNotIn("liquidity", projected["events"][0]["series"][0])
        with self.assertRaises(ValueError):
            project({"clobTokenIds": '[{"price":1}]'}, "market")

    def test_terminal_cursor_and_no_silent_cap(self) -> None:
        reader = FakeReader([{"markets": [{"id": "1"}], "next_cursor": "next"}, {"markets": []}])
        result = scan(reader, "/markets/keyset", {"limit": "1"}, "market", 2)  # type: ignore[arg-type]
        self.assertTrue(result["terminal_observed"])
        self.assertIn("after_cursor=next", reader.urls[1])
        capped = FakeReader([{"markets": [{"id": "1"}], "next_cursor": "next"}])
        result = scan(capped, "/markets/keyset", {"limit": "1"}, "market", 1)  # type: ignore[arg-type]
        self.assertFalse(result["terminal_observed"])
        full_terminal = FakeReader([{"markets": [{"id": "1"}]}])
        result = scan(full_terminal, "/markets/keyset", {"limit": "1"}, "market", 1)  # type: ignore[arg-type]
        self.assertTrue(result["terminal_observed"])

    def test_nullable_relations_remain_explicit(self) -> None:
        row = project({"events": None}, "market")
        self.assertIsNone(row["events"])
        self.assertEqual(project(row, "market"), row)

    def test_seven_asset_seed_excludes_prices(self) -> None:
        fixture = test_contract.ContractTests()
        sample = quote(fixture.row(), fixture.identity(), "2026-09-05/12", "f" * 64, 0)
        samples = {}
        for asset in ASSETS:
            for side in ("UP", "DOWN"):
                samples[asset + ":" + side] = dict(
                    sample, asset=asset, outcome=side, token="1" if side == "UP" else "2"
                )
        result = prior_identities({"quote_samples": samples})
        self.assertEqual(set(result), set(ASSETS))
        self.assertFalse(any("ask" in row for row in result.values()))
        del samples["HYPE:DOWN"]
        with self.assertRaises(KeyError):
            prior_identities({"quote_samples": samples})

    def test_report_has_no_unchecked_payload_extension(self) -> None:
        commit = "a" * 40
        identity = sha(canonical({"schema": SCHEMA, "commit": commit, "prior_sha256": PRIOR_SHA}))
        request = dict(
            url="https://gamma-api.polymarket.com/markets?limit=1",
            observed_at="2026-09-06T10:00:00Z",
            http_date=None,
            status=200,
            bytes=2,
            sha256="a" * 64,
            network_ns=1,
        )
        report: dict[str, Any] = dict(
            schema=SCHEMA,
            identity=identity,
            commit=commit,
            workflow_run_id="1",
            prior_tag=PRIOR_TAG,
            prior_sha256=PRIOR_SHA,
            semantic_profile="PENDULUMFLOW_V3_OBSERVED",
            profile_version=1,
            research_import_allowed=False,
            expected_catalog_certified=False,
            scans=[
                dict(
                    path="/markets",
                    parameters={"limit": "1"},
                    pages=[dict(request=request, row_count=1, next_cursor=None)],
                    rows=[project({"id": "1"}, "market")],
                    terminal_observed=False,
                    error=None,
                    page_budget=1,
                    duplicate_ids=[],
                    scope=SCAN_SCOPE,
                )
            ],
            slug_checks=[],
            requests=[request],
            downloaded_bytes=2,
            network_ns=1,
            foreign_price_outcome_depth_fields_retained=False,
            scope=SCOPE,
        )
        validate_report(report, identity)
        for route in (
            (),
            ("requests", 0),
            ("scans", 0),
            ("scans", 0, "pages", 0),
            ("scans", 0, "rows", 0),
        ):
            modified = deepcopy(report)
            current = modified
            for key in route:
                current = current[key]  # type: ignore[index]
            current["raw_payload"] = {"bestAsk": "0.5", "winner": True}
            with self.assertRaises(ValueError):
                validate_report(modified, identity)
        changed = dict(report, expected_catalog_certified=True)
        with self.assertRaises(ValueError):
            validate_report(changed, identity)


if __name__ == "__main__":
    unittest.main()
