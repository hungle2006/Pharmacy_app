"""Offline smoke tests: no R2 credentials and no source downloads needed."""
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "pipeline" / "bronze"
sys.path.insert(0, str(ROOT))
import medi_watch
import rxnorm_pipeline

class BronzeSmoke(unittest.TestCase):
    def test_rrf_to_csv_fields_and_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            zipfile_path = tmp / "fixture.zip"
            def row(rxcui, lang, sab, tty, name, suppress):
                fields = [""] * 18
                fields[0] = rxcui
                fields[1] = lang
                fields[11] = sab
                fields[12] = tty
                fields[14] = name
                fields[16] = suppress
                return "|".join(fields) + "|\n"
            content = (
                row("123", "ENG", "RXNORM", "SCD", "Aspirin 100 MG", "N") +
                row("124", "ENG", "RXNORM", "SBD", "Aspirín 100 MG", "N") +
                row("125", "SPA", "RXNORM", "SCD", "Spanish", "N") +
                row("126", "ENG", "OTHER", "SCD", "Other", "N") +
                row("127", "ENG", "RXNORM", "SCD", "Suppressed", "Y")
            ).encode("utf-8")
            with zipfile.ZipFile(zipfile_path, "w") as out:
                out.writestr("rxnorm/RXNCONSO.RRF", content)
            conn = rxnorm_pipeline.convert(zipfile_path, tmp / "records.sqlite")
            result = conn.execute("SELECT * FROM r ORDER BY rxcui").fetchall()
            self.assertEqual(
                result,
                [
                    ("aspirin 100 mg", "123", "Aspirin 100 MG", "SCD", "RXNORM"),
                    ("aspirin 100 mg", "124", "Aspirín 100 MG", "SBD", "RXNORM"),
                ],
            )
            conn.close()

    def test_medi_monitor_ignores_legacy_and_flags_new(self):
        old = '<p>MEDI-2 HPS released 2020</p><a href="/downloads/medi2.csv">MEDI-2 HPS</a>'
        self.assertEqual(medi_watch.inspect(old)["versions_after_medi2"], [])
        self.assertEqual(medi_watch.inspect(old)["candidate_hps_links"], [])
        recent = '<p>MEDI-3 HPS released</p><a href="/datasets/medi3.csv">MEDI-3 HPS</a>'
        status = medi_watch.inspect(recent)
        self.assertEqual(status["versions_after_medi2"], [3])
        self.assertEqual(len(status["candidate_hps_links"]), 1)

    def test_dav_retries_transient_504(self):
        import requests
        from crawl_dav import get_page, make_payload

        class Response:
            status_code = 200
            def json(self):
                return {"result": {"items": [{"id": 1}], "totalCount": 1}}
            def raise_for_status(self):
                return None

        class Session:
            def __init__(self):
                self.calls = 0
            def post(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise requests.exceptions.HTTPError("504 Gateway Time-out")
                return Response()

        session = Session()
        with patch("crawl_dav.time.sleep", return_value=None):
            result = get_page(session, "https://example.org", 0, 50, retries=2)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(session.calls, 2)

    def test_nlm_licensed_free_release_selection(self):
        html = '''
        <a href="https://download.nlm.nih.gov/umls/kss/rxnorm/RxNorm_full_prescribe_01052026.zip">Jan</a>
        <a href="https://download.nlm.nih.gov/umls/kss/rxnorm/RxNorm_full_prescribe_10052026.zip">Oct</a>
        <a href="https://download.nlm.nih.gov/umls/kss/rxnorm/RxNorm_full_12012027.zip">Full licensed</a>
        '''
        class Response:
            url = rxnorm_pipeline.PAGE
            text = html
            def raise_for_status(self): pass
        with patch.object(rxnorm_pipeline.requests, "get", return_value=Response()):
            url, name = rxnorm_pipeline.latest()
        self.assertEqual(name, "RxNorm_full_prescribe_10052026.zip")
        self.assertTrue(url.startswith("https://download.nlm.nih.gov/"))

if __name__ == "__main__":
    unittest.main()
