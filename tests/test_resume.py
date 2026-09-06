from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from pflow.consumer import verify
from pflow.probe import run
from pflow.source import canonical, sha


class ResumeTests(unittest.TestCase):
    def report(self) -> tuple[dict[str, Any], MagicMock]:
        hours = ["2026-08-27/11", "2026-08-27/12", "2026-08-27/13"]
        raw = b"fixture-manifest"
        sources = dict.fromkeys(hours, sha(raw))
        identity = sha(
            canonical(
                {
                    "schema": "source-probe-partition.v1",
                    "hour": hours[1],
                    "history": 1,
                    "after": 1,
                    "sources": sources,
                    "transform_commit": "f" * 40,
                }
            )
        )
        reader = MagicMock()
        reader.inventory.return_value = ({h + "/manifest.json": sha(raw) for h in hours}, b"ledger")
        reader.manifest.return_value = ({}, raw)
        return {
            "schema": "pendulumflow-source-canary.v1",
            "partition_identity": identity,
            "hour": hours[1],
            "source_versions": {h: {"manifest_sha256": sha(raw)} for h in hours},
            "transform_commit": "f" * 40,
            "research_authority": False,
            "certified_days": [],
            "quote_samples": {},
        }, reader

    def test_sealed_checkpoint_reused_without_payload_and_wrong_binding_rejected(self) -> None:
        for wrong in (False, True):
            report, reader = self.report()
            if wrong:
                report["transform_commit"] = "e" * 40
            data = canonical(report)
            previous = {
                "id": 123,
                "draft": False,
                "immutable": True,
                "assets": [{"name": sha(data) + "--report.json"}],
            }
            with (
                patch("pflow.probe.Reader", return_value=reader),
                patch("pflow.probe.current_commit", return_value="f" * 40),
                patch("pflow.probe.api", return_value=previous),
                patch("pflow.probe.read_asset", return_value=data),
                patch("pflow.probe.verify_release") as verify_release,
                patch("pflow.probe.fetch_products") as fetch,
            ):
                if wrong:
                    with self.assertRaisesRegex(ValueError, "binding"):
                        run("2026-08-27/12", 1, 1)
                    verify_release.assert_not_called()
                else:
                    self.assertEqual(run("2026-08-27/12", 1, 1)["id"], 123)
                    verify_release.assert_called_once()
                fetch.assert_not_called()

    def test_pinned_consumer_rejects_research_import(self) -> None:
        report, _ = self.report()
        data = canonical(report)
        digest = sha(data)
        release = {
            "id": 123,
            "immutable": True,
            "assets": [{"id": 456, "name": digest + "--report.json"}],
        }
        tag = "source-probe-" + report["partition_identity"]
        with (
            patch("pflow.consumer.api", return_value=release),
            patch("pflow.consumer.read_asset", return_value=data),
            patch("pflow.consumer.verify_release"),
        ):
            with self.assertRaisesRegex(ValueError, "NO_RESEARCH_AUTHORITY"):
                verify(tag, digest)
            self.assertFalse(verify(tag, digest, evidence_only=True)["research_import_allowed"])
            with self.assertRaises(ValueError):
                verify(tag, "a" * 64, evidence_only=True)


if __name__ == "__main__":
    unittest.main()
