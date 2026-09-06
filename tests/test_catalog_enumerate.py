"""Pagination evidence must account for every returned row without claiming authority."""

from __future__ import annotations

import unittest
from copy import deepcopy
from typing import Any

from pflow.catalog_enumerate import ENUM_SCHEMA, specification, stable, summary, validate
from pflow.catalog_probe import PRIOR_SHA, PRIOR_TAG, SCHEMA, SCOPE, project, scan
from pflow.source import canonical, sha


class Reader:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = iter(rows)
        self.ledger: list[dict[str, Any]] = []

    def get(self, url: str) -> tuple[Any, dict[str, Any]]:
        value = next(self.rows)
        request = dict(
            url=url,
            observed_at="2026-09-06T00:00:00Z",
            http_date=None,
            status=200,
            bytes=len(canonical(value)),
            sha256=sha(canonical(value)),
            network_ns=1,
        )
        self.ledger.append(request)
        return value, request


def report_fixture(name: str, pages: list[Any]) -> dict[str, Any]:
    spec = specification(name)
    commit = "a" * 40
    reader = Reader(pages)
    result = scan(reader, spec["path"], spec["parameters"], spec["kind"], spec["max_pages"])  # type: ignore[arg-type]
    evidence = dict(
        schema=SCHEMA,
        identity=sha(canonical(dict(schema=SCHEMA, commit=commit, prior_sha256=PRIOR_SHA))),
        commit=commit,
        workflow_run_id="1",
        prior_tag=PRIOR_TAG,
        prior_sha256=PRIOR_SHA,
        semantic_profile="PENDULUMFLOW_V3_OBSERVED",
        profile_version=1,
        research_import_allowed=False,
        expected_catalog_certified=False,
        scans=[result],
        slug_checks=[],
        requests=reader.ledger,
        downloaded_bytes=sum(x["bytes"] for x in reader.ledger),
        network_ns=len(reader.ledger),
        foreign_price_outcome_depth_fields_retained=False,
        scope=SCOPE,
    )
    return dict(
        schema=ENUM_SCHEMA,
        identity=sha(canonical(dict(schema=ENUM_SCHEMA, specification=spec, commit=commit))),
        commit=commit,
        specification=spec,
        evidence=evidence,
    )


class EnumerationTests(unittest.TestCase):
    def test_offset_clamp_requires_empty_page_and_uses_actual_return_count(self) -> None:
        reader = Reader([[{"id": str(i)} for i in range(50)], [{"id": "50"}], []])
        result = scan(reader, "/series", {"limit": "100"}, "series", 3)  # type: ignore[arg-type]
        self.assertTrue(result["terminal_observed"])
        self.assertEqual(len(result["rows"]), 51)
        self.assertIn("offset=50", reader.ledger[1]["url"])
        self.assertIn("offset=51", reader.ledger[2]["url"])
        report = report_fixture("series-complete-ascending", [[{"id": "1"}], []])
        validate(report, report["specification"], report["commit"])

    def test_query_scope_is_independent_bounded_and_explicit(self) -> None:
        self.assertNotIn("closed", specification("series-ascending")["parameters"])
        self.assertEqual(specification("series-descending")["parameters"]["ascending"], "false")
        for closed in ("true", "false"):
            spec = specification("2026-08-28-markets-" + closed)
            self.assertEqual(spec["parameters"]["closed"], closed)
            self.assertEqual(spec["parameters"]["end_date_max"], "2026-08-29T00:05:00Z")
        with self.assertRaises(ValueError):
            specification("arbitrary-user-url")

    def test_stable_membership_excludes_live_values_and_preserves_identity(self) -> None:
        row = project(
            {
                "id": "1",
                "conditionId": "x",
                "active": True,
                "clobTokenIds": '["11","22"]',
                "outcomes": '["Up","Down"]',
                "events": [{"id": "2"}, {"id": "3"}],
            },
            "market",
        )
        changed = deepcopy(row)
        changed["active"] = False
        changed["updatedAt"] = "later"
        changed["events"].reverse()
        self.assertEqual(stable(row, "market"), stable(changed, "market"))
        changed["clobTokenIds"].reverse()
        self.assertNotEqual(stable(row, "market"), stable(changed, "market"))

    def test_validator_detects_false_terminal_cursor_row_and_request_claims(self) -> None:
        rows = [{"id": str(i)} for i in range(100)]
        report = report_fixture(
            "2026-08-28-markets-true", [{"markets": rows, "next_cursor": "next"}, {"markets": []}]
        )
        validate(report, report["specification"], report["commit"])
        self.assertFalse(summary(report)["expected_catalog_certified"])
        for field, value in (
            ("terminal_observed", False),
            ("duplicate_ids", ["1"]),
            ("error", "HTTP_403"),
            ("rows", []),
        ):
            changed = deepcopy(report)
            changed["evidence"]["scans"][0][field] = value
            with self.assertRaises(ValueError):
                validate(changed, report["specification"], report["commit"])
        changed = deepcopy(report)
        changed["evidence"]["requests"][1]["url"] += "wrong"
        with self.assertRaises(ValueError):
            validate(changed, report["specification"], report["commit"])


if __name__ == "__main__":
    unittest.main()
