from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq

from pflow.release import publish
from pflow.source import Reader, check_schema, fetch_products, sha


class MemoryReader(Reader):
    def __init__(self, data: bytes, corrupt: bool = False) -> None:
        super().__init__()
        self.data = data
        self.corrupt = corrupt

    def get(self, url: str, interval: tuple[int, int] | None = None) -> bytes:
        assert interval is not None
        result = self.data[interval[0] : interval[1]]
        return b"x" + result[1:] if self.corrupt and interval[0] == 4 else result


class AcquisitionTests(unittest.TestCase):
    def test_exact_range_and_full_body_rejection(self) -> None:
        response = MagicMock()
        response.url = "https://archive.pendulumflow.com/v3/fixture.parquet"
        response.status = 200
        response.headers = {}
        response.__enter__.return_value = response
        with (
            patch("pflow.source.sys.platform", "linux"),
            patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}),
            patch("pflow.source.OPEN.open", return_value=response),
            self.assertRaises(ValueError),
        ):
            Reader().get(response.url, (4, 20))
        response.read.assert_not_called()

    def test_product_range_hash_and_footer_binding(self) -> None:
        from decimal import Decimal

        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "fixture.parquet"
            table = pa.table(
                {
                    "event_type": ["best_bid_ask"],
                    "market": pa.array([bytes([1]) * 32], type=pa.binary(32)),
                    "asset_id": pa.array([bytes([2]) * 32], type=pa.binary(32)),
                    "timestamp": pa.array(
                        [datetime(2026, 9, 1, tzinfo=UTC)], type=pa.timestamp("ms", tz="UTC")
                    ),
                    "timestamp_received": pa.array(
                        [datetime(2026, 9, 1, tzinfo=UTC)], type=pa.timestamp("us", tz="UTC")
                    ),
                    "sequence": pa.array([1], type=pa.uint64()),
                    "best_ask": pa.array([Decimal("0.1234")], type=pa.decimal128(9, 4)),
                }
            )
            pq.write_table(table, original)
            data = original.read_bytes()
            end = len(data) - 8 - int.from_bytes(data[-8:-4], "little")
            manifest: dict[str, Any] = {
                "hour": "2026-09-01/00",
                "file": "fixture.parquet",
                "bytes": len(data),
                "products": {
                    "best_bid_ask": {
                        "byte_range": [4, end],
                        "row_groups": [0, 0],
                        "row_count": 1,
                        "sha256": sha(data[4:end]),
                    }
                },
            }
            file, proof = fetch_products(
                MemoryReader(data), manifest, ("best_bid_ask",), Path(directory) / "partial.parquet"
            )
            self.assertTrue(proof["products"]["best_bid_ask"]["range_sha256_verified"])
            self.assertFalse(proof["whole_file_verified"])
            file.close()
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                fetch_products(
                    MemoryReader(data, True),
                    manifest,
                    ("best_bid_ask",),
                    Path(directory) / "corrupt.parquet",
                )
            manifest["products"]["best_bid_ask"]["row_count"] = 2
            with self.assertRaisesRegex(ValueError, "row count"):
                fetch_products(
                    MemoryReader(data),
                    manifest,
                    ("best_bid_ask",),
                    Path(directory) / "bad-count.parquet",
                )

    def test_nanosecond_or_float_schema_rejected(self) -> None:
        schema = pa.schema(
            [
                ("timestamp", pa.timestamp("ns", tz="UTC")),
                ("timestamp_received", pa.timestamp("us", tz="UTC")),
                ("sequence", pa.uint64()),
                ("best_ask", pa.float64()),
            ]
        )
        with self.assertRaises(ValueError):
            check_schema(schema, "best_bid_ask")

    def test_draft_resume_verifies_bytes_before_sealing(self) -> None:
        payload = b'{"fixture":true}\n'
        name = sha(payload) + "--report.json"
        asset = {
            "name": name,
            "size": len(payload),
            "digest": "sha256:" + sha(payload),
            "state": "uploaded",
        }
        draft = {"id": 1, "draft": True, "assets": [asset]}
        sealed = {**draft, "draft": False, "prerelease": False, "immutable": True}
        events: list[str] = []

        def fake_api(path: str, method: str = "GET", body: Any = None) -> Any:
            if method == "PATCH":
                self.assertEqual(events, ["draft_bytes_read"])
                events.append("sealed")
                return sealed
            return draft

        def fake_read(item: dict[str, Any], draft: bool = False) -> bytes:
            events.append("draft_bytes_read" if draft else "sealed_bytes_read")
            return payload

        with (
            patch("pflow.release.api", side_effect=fake_api),
            patch("pflow.release.read_asset", side_effect=fake_read),
            patch("subprocess.run") as upload,
        ):
            publish("fixture", {"report.json": payload}, "f" * 40, "fixture")
        upload.assert_not_called()
        self.assertEqual(events, ["draft_bytes_read", "sealed", "sealed_bytes_read"])

    def test_interrupted_zero_byte_upload_starter_is_retried(self) -> None:
        payload = b'{"fixture":true}\n'
        name = sha(payload) + "--report.json"
        starter = {"id": 9, "name": name, "size": 0, "digest": None, "state": "starter"}
        uploaded = {
            "id": 10,
            "name": name,
            "size": len(payload),
            "digest": "sha256:" + sha(payload),
            "state": "uploaded",
        }
        draft = {"id": 1, "draft": True, "assets": [starter]}
        complete = {"id": 1, "draft": True, "assets": [uploaded]}
        sealed = {**complete, "draft": False, "prerelease": False, "immutable": True}
        events: list[str] = []

        def fake_api(path: str, method: str = "GET", body: Any = None) -> Any:
            if method == "DELETE":
                events.append("starter_deleted")
                return None
            if method == "PATCH":
                events.append("sealed")
                return sealed
            if path == "releases/1":
                return complete
            return draft

        with (
            patch("pflow.release.api", side_effect=fake_api),
            patch("pflow.release.read_asset", return_value=payload),
            patch("subprocess.run") as upload,
        ):
            publish("fixture", {"report.json": payload}, "f" * 40, "fixture")
        self.assertEqual(events, ["starter_deleted", "sealed"])
        upload.assert_called_once()


if __name__ == "__main__":
    unittest.main()
