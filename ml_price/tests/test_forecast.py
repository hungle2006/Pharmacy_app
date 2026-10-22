"""Credential-free checks for historical-only, leakage-free forecast creation."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from ml_price.forecast import clean_observations, make_examples, time_split, fit_forecast, HORIZONS
from ml_price.serve import app, market_forecast
from ml_price.market_store import store
from fastapi import HTTPException

class TestFutureForecast(unittest.TestCase):
    def sample(self):
        rows=[]
        for drug in range(30):
            for n in range(30):
                dt=pd.Timestamp("2017-01-15",tz="UTC")+pd.DateOffset(months=n*3)
                price=1000+drug*37+int(n*13+np.sin(n/3+drug)*19)
                rows.append({
                    "dav_row_id":str(drug*100+n),
                    "registration_number":f"VN-{drug+1000}",
                    "ingredient":f"ingredient-{drug%5}",
                    "strength":"500mg",
                    "dosage_form":"Viên nén",
                    "manufacturer":f"manufacturer-{drug%3}",
                    "country":"Việt Nam","package":"Hộp 20 viên",
                    "product_package":"Hộp 20 viên",
                    "price_type":"KK nhập khẩu","unit":"Viên",
                    "declaration_date":dt,"price_vnd":price,
                })
        return pd.DataFrame(rows)

    def test_price_pairs_only_use_real_later_observations(self):
        raw=self.sample()
        obs=clean_observations(raw)
        samples=make_examples(obs)
        self.assertGreater(len(samples),100)
        self.assertTrue(set(samples.horizon_months.unique()).issubset(set(HORIZONS)))
        self.assertTrue((samples.target_date>samples.origin_date).all())
        self.assertTrue((samples.target_price>0).all())
        split=time_split(samples)
        self.assertIsNotNone(split)
        train,val,test=split
        self.assertLess(train.target_date.max(),val.origin_date.min())
        self.assertLess(val.target_date.max(),test.origin_date.min())

    def test_duplicates_and_mismatched_price_units(self):
        raw=self.sample()
        problem=raw.iloc[[0]].copy()
        problem["registration_number"]="VD-21799-14"
        problem["product_package"]="Hộp 10 vỉ x 10 viên"
        problem["unit"]="Ống"
        problem["package"]="Hộp 5 ống x 3 ml"
        dedup=pd.concat([raw,raw.iloc[[0]],problem],ignore_index=True)
        cleaned=clean_observations(dedup)
        self.assertEqual(len(cleaned),len(raw))
        self.assertFalse(cleaned.registration_number.eq("vd-21799-14").any())

    def test_quality_gate_and_no_synthetic_forecast_if_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            result=fit_forecast(self.sample(),path)
            self.assertEqual(result["kind"],"future-declared-price-forecast")
            self.assertIn(result["status"],("approved","rejected_quality_gate","insufficient_history"))
            self.assertTrue((Path(path)/"report.json").is_file())
            self.assertEqual(json.loads((Path(path)/"report.json").read_text())["status"],result["status"])
            if result["status"]!="approved":
                self.assertFalse((Path(path)/"forecast_model.cbm").exists())

    def test_old_per_product_forecast_route_is_disabled(self):
        urls=[route.path for route in app.routes]
        self.assertNotIn("/forecast-price",urls)
        self.assertNotIn("/predict-price",urls)
        self.assertIn("/market-forecast",urls)

    def test_report_unavailable_without_published_R2(self):
        original_report=store.report
        original_check=store.updated_at
        try:
            import time
            store.report=None
            store.updated_at=time.monotonic()
            with self.assertRaises(HTTPException) as error:
                market_forecast()
            self.assertEqual(error.exception.status_code,503)
        finally:
            store.report=original_report
            store.updated_at=original_check
