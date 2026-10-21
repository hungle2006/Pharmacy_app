"""Offline ML tests: never query production from pull requests."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from ml_price.constants import FEATURES
from ml_price.train import clean_data, time_split, group_median_baseline, train

class TestPriceML(unittest.TestCase):
    def sample(self,n=400):
        rng=np.random.default_rng(42)
        rows=[]
        for i in range(n):
            group=i%9
            rows.append({
                "dav_row_id":str(i),"registration_number":f"VN-{i}",
                "ingredient":f"ingredient-{group}","strength":"500mg",
                "dosage_form":"viên nén","manufacturer":f"company-{i%5}",
                "country":"Việt Nam","package":"hộp 20 viên",
                "source_name":"SILVER_R2" if i%2 else "DAV_PUBLIC_DRUG_PRICE",
                "declaration_date":pd.Timestamp("2024-01-01")+pd.Timedelta(days=i),
                "price_vnd":float(900+group*110+rng.normal(0,45)),
            })
        return pd.DataFrame(rows)
    def test_dedupe_and_nonoverlapping_chronological_groups(self):
        raw=self.sample()
        copy=raw.iloc[[0]].copy()
        copy["dav_row_id"]="10000"
        copy["declaration_date"]=pd.Timestamp("2026-01-01")
        cleaned=clean_data(pd.concat([raw,copy],ignore_index=True))
        self.assertEqual(len(cleaned),400)
        self.assertEqual(cleaned[cleaned.registration_number=="vn-0"].dav_row_id.iloc[0],"10000")
        a,b,c=time_split(cleaned)
        self.assertFalse(set(a.product_group)&set(b.product_group))
        self.assertFalse(set(a.product_group)&set(c.product_group))
        self.assertFalse(set(b.product_group)&set(c.product_group))
        self.assertEqual(len(a)+len(b)+len(c),400)
    def test_baseline_and_train_reports(self):
        raw=self.sample()
        a,b,c=time_split(clean_data(raw))
        pred=group_median_baseline(a,c)
        self.assertEqual(len(pred),len(c))
        self.assertTrue(np.all(pred>0))
        with tempfile.TemporaryDirectory() as directory:
            report=train(raw,directory)
            self.assertIn(report["status"],("approved","rejected_baseline"))
            self.assertEqual(report["n_distinct_products"],400)
            self.assertEqual(report["currency"],"VND")
            self.assertEqual(report["unit"],"viên")
            self.assertEqual(report["features"],FEATURES)
            self.assertTrue((Path(directory)/"price_model.cbm").exists())
            self.assertEqual(json.loads((Path(directory)/"metadata.json").read_text())["status"],report["status"])
    def test_small_dataset_fails_closed(self):
        with self.assertRaises(ValueError):
            time_split(clean_data(self.sample(20)))

if __name__=="__main__":
    unittest.main()
