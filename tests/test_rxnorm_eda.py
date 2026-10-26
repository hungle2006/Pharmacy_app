import csv
import json
import tempfile
import unittest
from pathlib import Path
from silver_mapping.rxnorm_eda import analyze

COLUMNS=["normalized_name","rxcui","display_name","tty","sab","silver_qc_status"]
def write_rows(path, rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

class RxnormEdaTests(unittest.TestCase):
    def test_report3_report4_and_mapping_handoff(self):
        with tempfile.TemporaryDirectory() as d:
            t=Path(d);p=t/"silver.csv";out=t/"mapping.csv";r=t/"eda.json";h=t/"eda.html"
            rows=[
                {"normalized_name":"acetaminophen","rxcui":"100","display_name":"Acetaminophen","tty":"IN","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
                {"normalized_name":"acetaminophen 500 mg oral tablet","rxcui":"101","display_name":"Acetaminophen 500 MG Oral Tablet","tty":"SCD","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
                {"normalized_name":"acetaminophen","rxcui":"100","display_name":"Acetaminophen","tty":"IN","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
            ]
            write_rows(p,rows)
            report=analyze(p,out,r,h)
            self.assertEqual(report["report_3_eda"]["total_rows"],3)
            self.assertEqual(report["report_3_eda"]["mapping_ready_rows"],2)
            self.assertEqual(report["report_3_eda"]["excluded_rows"],1)
            self.assertEqual(report["report_3_eda"]["distinct_rxcui_mapping_ready"],2)
            self.assertEqual(report["report_3_eda"]["excluded_reasons"][0]["label"],"DUPLICATE_CONCEPT_TERM")
            self.assertTrue(r.exists() and h.exists())
            self.assertIn("Report 3",h.read_text())
            self.assertIn("Report 4",h.read_text())
            with out.open() as file:
                rows=list(csv.DictReader(file))
            self.assertEqual(len(rows),2)
            self.assertEqual(list(rows[0]),["normalized_name","rxcui","display_name","tty","sab"])
            self.assertFalse(report["mapping_handoff"]["clinical_verified"])

    def test_reject_incomplete_input(self):
        with tempfile.TemporaryDirectory() as d:
            t=Path(d)
            write_rows(t/"silver.csv",[
                {"normalized_name":"","rxcui":"","display_name":"Unknown","tty":"IN","sab":"RXNORM","silver_qc_status":"REJECTED"},
                {"normalized_name":"","rxcui":"2","display_name":"A","tty":"SCD","sab":"RXNORM","silver_qc_status":"ACCEPTED"}
            ])
            with self.assertRaises(ValueError):
                analyze(t/"silver.csv",t/"ready.csv",t/"report.json")
    def test_normalize_does_not_remove_greek_letter(self):
        from silver_mapping.rxnorm_eda import normalized
        self.assertEqual(normalized("β Lactam / 5-MG"),"β lactam 5 mg")

if __name__=="__main__":
    unittest.main()
