import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline/bronze"))
from dav_history import classify_snapshot
from test_compact_csv import FakeR2
from compact_csv import merge_snapshot


def record(**updates):
    return dict(dav_row_id="1", dav_registration_number="VD-1", dav_drug_name="Drug",
                dav_active_ingredient_raw="A", dav_strength="500 mg", dav_dosage_form="Tablet",
                dav_manufacturer="Maker", dav_country="VN", dav_package="Box 10 tablets",
                dav_unit="tablet", dav_price_type="KK", dav_declaring_unit="Company",
                dav_declaration_date="2025-01-01", dav_price_vnd="1000",
                dav_retail_price_vnd="", **{}) | updates


class DavHistoryTests(unittest.TestCase):
    def test_repeat_crawl_never_creates_a_declaration(self):
        old = record()
        self.assertEqual(classify_snapshot({"1": old}, {"1": old}),
                         {"missing_unverified": 0, "unchanged": 1})

    def test_same_id_price_or_date_edit_requires_review(self):
        old = record()
        for changes, flag in [({"dav_price_vnd": "1100"}, "price_revision_review"),
                              ({"dav_declaration_date": "2025-04-01"}, "source_date_revision_review"),
                              ({"dav_unit": "box"}, "identity_revision_review")]:
            counts = classify_snapshot({"1": old}, {"1": old | changes})
            self.assertEqual(counts[flag], 1)
            self.assertNotIn("new_declaration_price_changed", counts)

    def test_new_id_later_date_can_compare_changed_or_unchanged_price(self):
        old = record()
        for price, label in [("1100", "new_declaration_price_changed"),
                             ("1000.00", "new_declaration_price_unchanged")]:
            new = record(dav_row_id="2", dav_declaration_date="2025-04-01", dav_price_vnd=price)
            counts = classify_snapshot({"1": old}, {"1": old, "2": new})
            self.assertEqual(counts[label], 1)

    def test_pack_or_price_type_change_is_not_a_price_comparison(self):
        old = record()
        for field in ["dav_package", "dav_unit", "dav_price_type", "dav_manufacturer"]:
            new = record(dav_row_id="2", dav_declaration_date="2025-04-01", **{field: "different"})
            counts = classify_snapshot({"1": old}, {"2": new})
            self.assertEqual(counts["new_record_without_comparable_prior"], 1)

    def test_same_day_duplicate_and_missing_dates_not_new_temporal_change(self):
        old = record()
        for day in ["2025-01-01", "", "not-a-date"]:
            new = record(dav_row_id="2", dav_declaration_date=day, dav_price_vnd="1100")
            counts = classify_snapshot({"1": old}, {"2": new})
            self.assertNotIn("new_declaration_price_changed", counts)

    def test_full_ingestion_sequence_retains_old_values_and_is_idempotent(self):
        s3 = FakeR2()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "incoming.csv"
            def ingest(rows, **options):
                with path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(record()))
                    writer.writeheader(); writer.writerows(rows)
                return merge_snapshot(s3, "dav", path, **options)
            a = record()
            ingest([a])
            self.assertEqual(ingest([a])["new_events"], 0)
            b = record(dav_row_id="2", dav_declaration_date="2025-04-01", dav_price_vnd="1100")
            self.assertEqual(ingest([a, b])["dav_audit"]["new_declaration_price_changed"], 1)
            self.assertEqual(ingest([a, b | {"dav_price_vnd": "1200"}])["dav_audit"]["price_revision_review"], 1)
            history = list(csv.DictReader(io.StringIO(s3.items["bronze/dav.csv"][0].decode())))
            self.assertEqual([r["dav_price_vnd"] for r in history], ["1000", "1100", "1200"])
            previous = s3.items["bronze/dav.csv"][0]
            with self.assertRaisesRegex(ValueError, "expected 2"):
                ingest([a], expected_count=2)
            self.assertEqual(previous, s3.items["bronze/dav.csv"][0])


if __name__ == "__main__":
    unittest.main()
