"""Alternative first-party endpoints cannot import price or resolution results."""

from __future__ import annotations

import io
import json
import unittest
import urllib.error
from copy import deepcopy
from email.message import Message
from unittest.mock import patch

from pflow.catalog_access import (
    SCHEMA,
    SCOPE,
    clob,
    denial_class,
    projected_body,
    request,
    validate_report,
    validate_result,
)
from pflow.catalog_probe import PRIOR_SHA, PRIOR_TAG
from pflow.source import canonical, sha


class AccessTests(unittest.TestCase):
    def test_access_denial_never_becomes_empty_catalog(self) -> None:
        error = urllib.error.HTTPError(
            "https://gamma-api.polymarket.com/series",
            403,
            "Forbidden",
            Message(),
            io.BytesIO(b"Permission denied"),
        )
        with (
            patch("pflow.catalog_access.platform.system", return_value="Linux"),
            patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}),
            patch("pflow.catalog_access.urllib.request.OpenerDirector.open", side_effect=error),
        ):
            result = request("https://gamma-api.polymarket.com/series?limit=1", "gamma", 1000)
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["processing_status"], "HTTP_ERROR")
        self.assertIsNone(result["result"])
        self.assertTrue(result["body_complete"])
        self.assertEqual(result["denial_class"], "ACCESS_DENIED")
        self.assertEqual(denial_class(b"Winning outcome: Up"), "UNCLASSIFIED_HTTP_ERROR")
        with self.assertRaises(ValueError):
            request("https://gamma-api.polymarket.com/series", "gamma", 0)
        commit = "a" * 40
        report = dict(
            schema=SCHEMA,
            scope=SCOPE,
            commit=commit,
            workflow_run_id="1",
            identity=sha(canonical(dict(schema=SCHEMA, commit=commit, prior_sha256=PRIOR_SHA))),
            prior_tag=PRIOR_TAG,
            prior_sha256=PRIOR_SHA,
            requests=[result],
            downloaded_bytes=result["bytes"],
            network_ns=result["network_ns"],
            research_import_allowed=False,
            expected_catalog_certified=False,
            budget_exhausted=False,
        )
        validate_report(report)
        for field in ("commit", "workflow_run_id"):
            changed = dict(report, **{field: {"bestAsk": 1}})
            with self.assertRaises(ValueError):
                validate_report(changed)
        for field in ("kind", "method", "request_sha256", "observed_at", "denial_class"):
            changed = deepcopy(report)
            changed["requests"][0][field] = {"outcomePrices": [1, 0]}
            with self.assertRaises(ValueError):
                validate_report(changed)

    def test_clob_discards_prices_winners_and_depth(self) -> None:
        source = dict(
            condition_id="0x" + "a" * 64,
            question="BTC",
            active=True,
            tokens=[dict(token_id="1", outcome="Up", price=1, winner=True)],
            rewards={"min_size": 100},
            asks=[{"size": "100"}],
            volume=123,
        )
        row = clob(source)
        self.assertEqual(row["tokens"], [{"token_id": "1", "outcome": "Up"}])
        self.assertNotIn("rewards", row)
        self.assertNotIn("asks", row)
        valid = dict(rows=[row], next_cursor="LTE=", count=1, limit=1000)
        validate_result("clob_list", valid)
        row["raw_payload"] = source
        with self.assertRaises(ValueError):
            validate_result("clob_list", valid)

    def test_documented_clean_token_lookup(self) -> None:
        raw = dict(
            condition_id="0x" + "a" * 64,
            primary_token_id="1",
            secondary_token_id="2",
            winner="1",
            prices=[1, 0],
        )
        result = projected_body("clob_token", json.dumps(raw).encode())
        validate_result("clob_token", result)
        self.assertEqual(set(result), {"condition_id", "primary_token_id", "secondary_token_id"})

    def test_web_projection_and_no_ip_publication(self) -> None:
        source = dict(
            props={
                "market": dict(
                    conditionId="0x" + "a" * 64, slug="btc-5m", outcomePrices='["1","0"]', bestAsk=1
                )
            }
        )
        html = (
            '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(source) + "</script>"
        )
        result = projected_body("web", html.encode())
        validate_result("web", result)
        self.assertEqual(len(result["embedded_catalog_rows"]), 1)
        self.assertNotIn("bestAsk", result["embedded_catalog_rows"][0])
        geo = projected_body(
            "geo", b'{"blocked":true,"country":"US","region":"VA","ip":"192.0.2.1"}'
        )
        self.assertNotIn("ip", geo)


if __name__ == "__main__":
    unittest.main()
