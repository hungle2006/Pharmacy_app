"""Data-grounded verification of lecture-aligned RxNorm Report 4."""
import csv
import tempfile
import unittest
from pathlib import Path

from silver_mapping.rxnorm_report4 import compute_report4, render_sections, summary, quantile
from silver_mapping.rxnorm_eda import analyze

class Report4Test(unittest.TestCase):
    def test_population_statistics(self):
        d=summary([2,4,4,4,5,5,7,9])
        self.assertEqual(d["mean"],5)
        self.assertEqual(d["median"],4.5)
        self.assertEqual(d["mode"],4)
        self.assertEqual(d["variance"],4)
        self.assertEqual(d["std_dev"],2)
        self.assertEqual(d["q1"],4)
        self.assertEqual(d["q3"],5.5)

    def test_empty_and_constant(self):
        self.assertIsNone(quantile([],0.5))
        d=summary([4,4,4])
        self.assertEqual(d["std_dev"],0)
        self.assertEqual(d["outliers"],0)

    def test_reports_use_actual_source_rows_and_mapping_does_not_claim_verification(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            input_file=p/"silver.csv"
            rows=[
                {"normalized_name":"alpha","rxcui":"100","display_name":"alpha","tty":"IN","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
                {"normalized_name":"alpha oral tablet","rxcui":"101","display_name":"alpha oral tablet","tty":"SCD","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
                {"normalized_name":"alpha solution","rxcui":"101","display_name":"alpha solution","tty":"SY","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
                {"normalized_name":"beta","rxcui":"102","display_name":"beta","tty":"IN","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
                {"normalized_name":"beta oral tablet","rxcui":"103","display_name":"beta oral tablet","tty":"SCD","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
            ]
            with input_file.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]))
                w.writeheader();w.writerows(rows)
            report=analyze(input_file,p/"mapping.csv",p/"eda.json",p/"eda.html")
            stats=report["report_4_statistics"]
            self.assertEqual(stats["n_terms"],5)
            self.assertEqual(stats["n_rxcui"],4)
            self.assertEqual(sum(x["count"] for x in stats["histogram_name_length"]),5)
            self.assertEqual(sum(x["count"] for x in stats["tty_composition"]),5)
            self.assertEqual(sum(x["count"] for x in stats["histogram_terms_per_rxcui"]),4)
            self.assertEqual(stats["name_length"]["n"],5)
            self.assertEqual(stats["terms_per_rxcui"]["max"],2)
            self.assertEqual(len(stats["scatter_illustrative"]),4)
            self.assertFalse(report["mapping_handoff"]["clinical_verified"])
            view=p.joinpath("eda.html").read_text(encoding="utf-8")
            for keyword in ("Histogram","Box plot","Scatter plot","Doughnut chart","Standard deviation","Report 04"):
                self.assertIn(keyword,view)
            self.assertIn('CANDIDATE',view) if report["mapping_handoff"].get("mapping_status_distribution") else None

if __name__=="__main__":
    unittest.main()
