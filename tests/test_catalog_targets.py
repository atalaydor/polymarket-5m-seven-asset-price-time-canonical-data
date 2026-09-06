"""First-party interval diagnostics preserve ambiguity and exact metadata roles."""

import unittest
from typing import Any

from pflow.catalog_probe import project
from pflow.catalog_series_detail import SCHEMA, projection, validate
from pflow.catalog_targets import SERIES_SHA, instant, interval, queries
from pflow.source import canonical, sha


class TargetTests(unittest.TestCase):
    def test_declared_truncation_cannot_claim_whole_series_response(self) -> None:
        commit = "a" * 40
        report: dict[str, Any] = dict(
            schema=SCHEMA,
            identity=sha(
                canonical(dict(schema=SCHEMA, asset="BTC", commit=commit, series_sha256=SERIES_SHA))
            ),
            asset="BTC",
            commit=commit,
            series_sha256=SERIES_SHA,
            request=dict(
                url="https://gamma-api.polymarket.com/series/10684",
                observed_at="2026-09-06T00:00:00Z",
                http_date=None,
                status=200,
                bytes=10,
                declared_bytes=20,
                network_ns=1,
                body_complete=False,
                sha256="b" * 64,
                hash_scope="downloaded_prefix_only",
            ),
            metadata=None,
            expected_catalog_certified=False,
            research_import_allowed=False,
        )
        validate(report, "BTC", commit)
        report["request"]["body_complete"] = True
        report["request"]["hash_scope"] = "whole_response"
        with self.assertRaises(ValueError):
            validate(report, "BTC", commit)

    def test_series_detail_never_preserves_foreign_research_fields(self) -> None:
        row = projection(
            dict(
                id="10684",
                volume="123",
                events=[
                    dict(
                        id="1",
                        bestAsk="0.99",
                        markets=[
                            dict(
                                id="2", outcomePrices='["1","0"]', winner=True, bids=[{"size": "2"}]
                            )
                        ],
                    )
                ],
            )
        )
        self.assertNotIn("volume", row["series"])
        self.assertNotIn("bestAsk", row["events"][0])
        self.assertNotIn("winner", row["events"][0]["markets"][0])
        self.assertEqual(row, projection(dict(row["series"], events=row["events"])))
        self.assertIsNone(projection(dict(id="10684"))["events"])

    def test_first_party_identity_interval_and_orientation_are_cross_checked(self) -> None:
        raw = dict(
            id="1",
            slug="btc-updown-5m-1787918400",
            startTime="2026-08-28T12:00:00Z",
            endDate="2026-08-28T12:05:00Z",
            series=[dict(id="10684")],
            markets=[
                dict(
                    id="2",
                    conditionId="0x" + "a" * 64,
                    eventStartTime="2026-08-28T12:00:00Z",
                    endDate="2026-08-28T12:05:00Z",
                    outcomes='["Up","Down"]',
                    clobTokenIds='["11","22"]',
                    outcomePrices='["1","0"]',
                    bestAsk="0.9",
                    winner="Up",
                )
            ],
        )
        result = interval(project(raw, "event"), "BTC")
        self.assertEqual(result["errors"], [])
        row = project(raw, "event")
        row["markets"][0]["outcomes"].reverse()
        self.assertNotIn("UNPROVEN_TOKEN_ORIENTATION", interval(row, "BTC")["errors"])
        row["markets"][0]["clobTokenIds"] = ["11", "11"]
        self.assertIn("UNPROVEN_TOKEN_ORIENTATION", interval(row, "BTC")["errors"])
        row["startTime"] = None
        self.assertIn("UNPROVEN_5M_INTERVAL", interval(row, "BTC")["errors"])
        self.assertNotIn("winner", str(result))

    def test_exact_timestamp_and_query_bounds(self) -> None:
        self.assertEqual(instant("1970-01-01T00:00:00.000001Z"), 1)
        with self.assertRaises(ValueError):
            instant("1970-01-01T00:00:00.0000001Z")
        with self.assertRaises(ValueError):
            instant("2026-08-28T00:00:00")
        q = queries("DOGE")
        self.assertEqual(len(q), 10)
        self.assertEqual({x["series_id"] for x in q}, {"11325"})
        self.assertEqual(sum("end_date_min" not in x for x in q), 4)
        self.assertEqual({x["closed"] for x in q}, {"true", "false"})


if __name__ == "__main__":
    unittest.main()
