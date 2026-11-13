"""Mock the public source; no live DAV traffic or credentials in these tests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline/bronze"))
from crawl_dav import crawl, DAVError


class DavCrawlTests(unittest.TestCase):
    def run_pages(self, pages, root, max_rows=None):
        session = Mock()
        with patch("crawl_dav.prepare_session", return_value=(session, "https://example.org/prices")), \
             patch("crawl_dav.get_page", side_effect=pages), patch("crawl_dav.time.sleep"):
            return crawl(Path(root), "https://example.org", 2, max_rows, 0)

    def test_complete_snapshot_has_source_date_provenance(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.run_pages([
                {"items": [{"id": 1}, {"id": 2}], "totalCount": 3},
                {"items": [{"id": 3}], "totalCount": 3},
            ], root)
            manifest = json.loads(next(Path(root).glob("dav_crawl_manifest_*.json")).read_text())
            self.assertTrue(path.exists())
            self.assertTrue(manifest["snapshot_complete"])
            self.assertEqual(manifest["source_date_field"], "ngayTiepNhan")
            self.assertEqual(manifest["records_written"], 3)

    def test_truncated_or_unstable_snapshot_is_not_published(self):
        for pages in [
            [{"items": [{"id": 1}], "totalCount": 3}],
            [{"items": [{"id": 1}, {"id": 2}], "totalCount": 3},
             {"items": [], "totalCount": 3}],
            [{"items": [{"id": 1}, {"id": 2}], "totalCount": 3},
             {"items": [{"id": 3}], "totalCount": 4},
             {"items": [], "totalCount": 4}],
        ]:
            with self.subTest(pages=pages), tempfile.TemporaryDirectory() as root:
                with self.assertRaises(DAVError): self.run_pages(pages, root)
                self.assertEqual(list(Path(root).glob("dav_gia_ban_buon_*.csv")), [])
                self.assertEqual(list(Path(root).glob("dav_crawl_manifest_*.json")), [])

    def test_conflicting_repeated_id_or_missing_id_fails_closed(self):
        for items in [[{"id": 1}, {"id": 1, "giaBanBuonDuKien": 12}], [{"tenThuoc": "no-id"}]]:
            with self.subTest(items=items), tempfile.TemporaryDirectory() as root:
                with self.assertRaises(DAVError):
                    self.run_pages([{"items": items, "totalCount": len(items)}], root)

    def test_max_rows_is_explicitly_marked_partial(self):
        with tempfile.TemporaryDirectory() as root:
            self.run_pages([{"items": [{"id": 1}, {"id": 2}], "totalCount": 20}], root, max_rows=1)
            manifest = json.loads(next(Path(root).glob("dav_crawl_manifest_*.json")).read_text())
            self.assertFalse(manifest["snapshot_complete"])


if __name__ == "__main__": unittest.main()
