"""Offline ML tests: never query production from pull requests."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from ml_price.constants import FEATURES
from ml_price.train import clean_data, time_split, group_median_baseline, predict_vnd, train
from ml_price.baseline import build_priors, predict_with_priors, blend_predictions

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
            self.assertIn(report["target_transform"], ("log1p", "identity"))
            self.assertEqual(set(report["validation_mae_vnd"]), {"log_rmse", "vnd_mae"})
            self.assertEqual(set(report["blend_weights"]), {"0", "1", "2", "3"})
            self.assertIn("baseline_priors", report)
            self.assertTrue((Path(directory)/"price_model.cbm").exists())
            self.assertEqual(json.loads((Path(directory)/"metadata.json").read_text())["status"],report["status"])
    def test_prediction_target_transforms(self):
        class ConstantModel:
            def __init__(self, value):
                self.value = value
            def predict(self, features):
                return np.full(len(features), self.value)

        features = pd.DataFrame({"x": [1, 2]})
        np.testing.assert_allclose(predict_vnd(ConstantModel(np.log1p(500)), features, "log1p"), [500, 500])
        np.testing.assert_allclose(predict_vnd(ConstantModel(500), features, "identity"), [500, 500])
        np.testing.assert_allclose(predict_vnd(ConstantModel(-7), features, "identity"), [0, 0])
        with self.assertRaises(ValueError):
            predict_vnd(ConstantModel(100), features, "unknown")

    def test_persisted_priors_reproduce_train_only_baseline(self):
        df=clean_data(self.sample())
        tr,va,te=time_split(df)
        priors=build_priors(tr)
        observed, levels=predict_with_priors(te[FEATURES],priors)
        expected=group_median_baseline(tr,te)
        np.testing.assert_allclose(observed,expected)
        self.assertEqual(len(levels),len(te))
        np.testing.assert_allclose(blend_predictions(observed, observed*2, levels,
                                  {"0":0.0,"1":0.5,"2":1.0,"3":0.25}),
                                  observed * (1 + np.asarray([{"0":0.0,"1":0.5,"2":1.0,"3":0.25}[str(int(v))] for v in levels])))
        novel=te[FEATURES].iloc[[0]].copy()
        novel.loc[:, "ingredient"]="NOT_SEEN_IN_TRAIN"
        fallback,novel_levels=predict_with_priors(novel,priors)
        self.assertEqual(novel_levels[0],0)
        self.assertAlmostEqual(fallback[0],priors["fallback"])

    def test_small_dataset_fails_closed(self):
        with self.assertRaises(ValueError):
            time_split(clean_data(self.sample(20)))

if __name__=="__main__":
    unittest.main()
