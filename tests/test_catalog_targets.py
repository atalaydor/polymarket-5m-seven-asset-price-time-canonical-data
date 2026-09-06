"""First-party interval diagnostics preserve ambiguity and exact metadata roles."""

import unittest

from pflow.catalog_probe import project
from pflow.catalog_targets import instant, interval, queries


class TargetTests(unittest.TestCase):
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
        self.assertIn("UNPROVEN_TOKEN_ORIENTATION", interval(row, "BTC")["errors"])
        row["startTime"] = None
        self.assertIn("UNPROVEN_5M_INTERVAL", interval(row, "BTC")["errors"])
        self.assertNotIn("winner", str(result))

    def test_exact_timestamp_and_query_bounds(self) -> None:
        self.assertEqual(instant("1970-01-01T00:00:00.000001Z"), 1)
        with self.assertRaises(ValueError):
            instant("2026-08-28T00:00:00")
        q = queries("DOGE")
        self.assertEqual(len(q), 10)
        self.assertEqual({x["series_id"] for x in q}, {"11325"})
        self.assertEqual(sum("end_date_min" not in x for x in q), 4)
        self.assertEqual({x["closed"] for x in q}, {"true", "false"})


if __name__ == "__main__":
    unittest.main()
