from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from pflow.continuity_probe import INTEGRITY_PRODUCTS, acquire, target_rows
from pflow.integrity import diagnose
from pflow.source import Reader, sha


class MemoryReader(Reader):
    def __init__(self, data: bytes) -> None:
        super().__init__()
        self.data = data

    def get(self, url: str, interval: tuple[int, int] | None = None) -> bytes:
        assert interval is not None
        return self.data[interval[0] : interval[1]]


class IntegrityAcquisitionTests(unittest.TestCase):
    def test_product_hash_projection_target_decode_and_corruption(self) -> None:
        schema = pa.schema(
            [
                ("event_type", pa.string()),
                ("market", pa.binary(32)),
                ("asset_id", pa.binary(32)),
                ("timestamp", pa.timestamp("ms", tz="UTC")),
                ("timestamp_received", pa.timestamp("us", tz="UTC")),
                ("sequence", pa.uint64()),
                ("source_witness", pa.string()),
                ("witness_set", pa.string()),
                ("arrival_skew", pa.int64()),
                ("best_ask", pa.decimal128(9, 4)),
                ("price", pa.decimal128(9, 4)),
                ("size", pa.decimal128(18, 6)),
                ("side", pa.string()),
                (
                    "asks",
                    pa.list_(
                        pa.struct(
                            [
                                ("price", pa.decimal128(9, 4)),
                                ("size", pa.decimal128(18, 6)),
                            ]
                        )
                    ),
                ),
            ]
        )
        market = bytes([1]) * 32
        asset = bytes([2]) * 32
        rows = []
        for i, product in enumerate(INTEGRITY_PRODUCTS):
            rows.append(
                {
                    "event_type": product,
                    "market": market,
                    "asset_id": asset,
                    "timestamp": datetime(2026, 8, 28, 11, 0, i, tzinfo=UTC),
                    "timestamp_received": datetime(2026, 8, 28, 11, 0, i, 5, tzinfo=UTC),
                    "sequence": i + 10,
                    "source_witness": "e",
                    "witness_set": "|a|e|",
                    "arrival_skew": 10,
                    "best_ask": Decimal(".5"),
                    "price": Decimal(".9"),
                    "size": Decimal("3"),
                    "side": "SELL",
                    "asks": [
                        {"price": Decimal(".5"), "size": Decimal("1")},
                        {"price": Decimal(".9"), "size": Decimal("2")},
                    ],
                }
            )
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "fixture.parquet"
            pq.write_table(pa.Table.from_pylist(rows, schema), original, row_group_size=1)
            data = original.read_bytes()
            original_file = pq.ParquetFile(original)
            ends = []
            for i in range(3):
                group = original_file.metadata.row_group(i)
                ends.append(
                    min(group.column(c).dictionary_page_offset for c in range(group.num_columns))
                )
            original_file.close()
            ends.append(len(data) - 8 - int.from_bytes(data[-8:-4], "little"))
            manifest: dict[str, Any] = {
                "hour": "2026-08-28/11",
                "file": "fixture.parquet",
                "bytes": len(data),
                "products": {
                    p: {
                        "byte_range": ends[i : i + 2],
                        "row_groups": [i, i],
                        "row_count": 1,
                        "sha256": sha(data[ends[i] : ends[i + 1]]),
                    }
                    for i, p in enumerate(INTEGRITY_PRODUCTS)
                },
            }
            parquet, proof = acquire(
                MemoryReader(data), manifest, Path(directory) / "sparse.parquet"
            )
            targets = {
                "BTC:UP": {"market": market.hex(), "token": str(int.from_bytes(asset, "big"))}
            }
            events, counters, scan = target_rows(parquet, manifest, targets)
            parquet.close()
            self.assertEqual(scan["target_rows"], 3)
            self.assertEqual(
                diagnose(events["BTC:UP"], counters["BTC:UP"])["bba_ask_disagreements"], 0
            )
            self.assertFalse(proof["whole_file_verified"])
            self.assertTrue(all(p["range_hash_verified"] for p in proof["products"]))
            bad = data[:4] + b"x" + data[5:]
            with self.assertRaisesRegex(ValueError, "product hash mismatch"):
                acquire(MemoryReader(bad), manifest, Path(directory) / "corrupt.parquet")


if __name__ == "__main__":
    unittest.main()
