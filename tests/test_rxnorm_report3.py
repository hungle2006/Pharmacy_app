import csv
import math
import tempfile
import unittest
from pathlib import Path
from silver_mapping.rxnorm_report3 import (
    student_t_two_sided,chi_square_survival,regularized_beta,
    pearson,ranks,welch,profile,render_report3
)
from silver_mapping.rxnorm_eda import analyze

class RxnormReport3StatisticalTests(unittest.TestCase):
    def test_student_t_p_values(self):
        self.assertAlmostEqual(student_t_two_sided(0,12),1,places=8)
        self.assertAlmostEqual(student_t_two_sided(2.22813885,10),.05,places=3)
        self.assertAlmostEqual(regularized_beta(2,3,.5),.6875,places=6)

    def test_chi_square_p(self):
        self.assertAlmostEqual(chi_square_survival(3.841458820694124,1),.05,places=5)

    def test_welch_and_effect_size(self):
        vals_a=[10+i%7 for i in range(30)]
        vals_b=[18+i%9 for i in range(33)]
        t=welch(vals_a,vals_b,"IN vs SCD")
        self.assertEqual(t["status"],"computed")
        self.assertLess(t["p_value"],.05)
        self.assertLess(t["difference"],0)
        self.assertLess(t["cohen_d"],0)
        self.assertEqual(len(t["ci95_normal_approx"]),2)

    def test_pearson_spearman(self):
        self.assertAlmostEqual(pearson([1,2,3],[3,2,1]),-1,places=6)
        self.assertEqual(ranks([1,2,2,4]),[1,2.5,2.5,4])

    def test_real_pipeline_grain_and_skips(self):
        with tempfile.TemporaryDirectory() as d:
            wd=Path(d);source=wd/"silver.csv"
            fields=["normalized_name","rxcui","display_name","tty","sab","silver_qc_status"]
            rows=[]
            for k in range(30):
                rows.extend([
                    {"normalized_name":"alpha "+str(k),"rxcui":str(k+1),"display_name":"A"* (15+k%10),"tty":"IN","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
                    {"normalized_name":"beta "+str(k),"rxcui":str(k+100),"display_name":"B"*(30+k%13),"tty":"SCD","sab":"RXNORM","silver_qc_status":"ACCEPTED"},
                ])
            # Two term types on same concept -> exclude from pairwise independent groups.
            rows.append({"normalized_name":"alpha second","rxcui":"1","display_name":"second term","tty":"SCD","sab":"RXNORM","silver_qc_status":"ACCEPTED"})
            with source.open("w",encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            result=analyze(source,wd/"ready.csv",wd/"report.json",wd/"report.html")
            m=result["report_3_multivariate"]
            self.assertEqual(m["analyzed_rows"],61)
            self.assertEqual(m["concepts"],60)
            self.assertEqual(m["welch_t_tests"][0]["overlapping_rxcui_excluded"],1)
            self.assertEqual(m["welch_t_tests"][0]["status"],"computed")
            self.assertEqual(m["welch_t_tests"][0]["n_a"],29)
            self.assertEqual(m["welch_t_tests"][0]["n_b"],30)
            self.assertEqual(len(m["correlations"]),4)
            self.assertEqual(m["lexical_coherence"]["n_comparable_rxcui"],1)
            self.assertTrue(any("Cronbach" in item["test"] for item in m["not_applicable"]))
            self.assertEqual(m["chi_square"]["n_rows"],61)
            self.assertFalse(result["mapping_handoff"]["clinical_verified"])
            html=wd.joinpath("report.html").read_text()
            # Every new Report 3 test displays its formula, substitution, and presenter guidance.
            for term in ("Missing%(c)", "Readiness%", "Variance", "Pearson r",
                         "Spearman ρ", "Welch's t-test", "Welch–Satterthwaite",
                         "Cohen's d", "CI₉₅%", "Holm", "Chi-square Pearson",
                         "Cramér's V", "Jaccard", "Coherence", "Cách nói"):
                self.assertIn(term.replace("'", "&#x27;"), html)
            for anchor in ("r3-correlation", "r3-welch", "r3-chi2", "r3-coherence"):
                self.assertIn(anchor, html)
            for word in ("Welch","Coherence","Cramér","Spearman","Report 3","Report 4"):
                self.assertIn(word,html)

if __name__=="__main__":unittest.main()
