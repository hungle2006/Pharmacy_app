"""Offline validation of multi-segment routing, catalog selection and safety."""
import json
import tempfile
import unittest
from pathlib import Path

from ml_price.segments import canonical, segment_id
from ml_price.train_catalog import train_catalog
from ml_price.tests.test_train import TestPriceML


class TestPriceSegments(unittest.TestCase):
    def test_canonical_unicode_units_are_same_id(self):
        self.assertEqual(segment_id(" KK nhập khẩu ", "lọ"),
                         segment_id("kk nhập khẩu", "lọ"))
        self.assertNotEqual(segment_id("KK nhập khẩu", "viên"),
                            segment_id("KK trong nước", "viên"))
        self.assertNotEqual(segment_id("KK nhập khẩu", "viên"),
                            segment_id("KK nhập khẩu", "lọ"))
        self.assertEqual(canonical(" VIÊN "), "viên")

    def test_train_catalog_keeps_segments_isolated_and_quality_gated(self):
        baseline = TestPriceML().sample(400)
        baseline["price_type"] = "KK trong nước"
        baseline["unit"] = "Viên"
        other = TestPriceML().sample(40)
        other["dav_row_id"] = [f"rare-{i}" for i in range(len(other))]
        other["registration_number"] = [f"RARE-{i}" for i in range(len(other))]
        other["price_type"] = "KK nhập khẩu"
        other["unit"] = "Lọ"
        with tempfile.TemporaryDirectory() as directory:
            report = train_catalog(
                __import__("pandas").concat([baseline, other], ignore_index=True),
                directory=directory)
            self.assertEqual(report["evaluated_segments"], 1)
            self.assertEqual(len(report["segments"]), 2)
            approved_or_rejected = [x for x in report["segments"] if x["status"] in ("approved", "rejected_baseline")]
            self.assertEqual(len(approved_or_rejected), 1)
            self.assertEqual(approved_or_rejected[0]["n_raw"], 400)
            i = approved_or_rejected[0]["id"]
            metadata = json.loads((Path(directory) / "segments" / i / "metadata.json").read_text())
            self.assertEqual(metadata["price_type"], "kk trong nước")
            self.assertEqual(metadata["unit"], "viên")
            self.assertEqual(metadata["n_initial_rows"], 400)
            self.assertEqual(report["insufficient_segments"], 1)
            self.assertTrue((Path(directory) / "catalog.json").exists())


if __name__ == "__main__":
    unittest.main()
