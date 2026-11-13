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

    def test_irregular_in_window_events_all_counted_not_nearest_day(self):
        raw=self.sample().iloc[:4].copy()
        raw["registration_number"]="VN-EVENT"
        raw["dav_row_id"]=["event-0","event-1","event-2","event-3"]
        raw["declaration_date"]=pd.to_datetime(
            ["2024-01-01","2024-01-11","2024-02-10","2024-03-20"],utc=True)
        raw["price_vnd"]=[1000,1300,1100,1500]
        events=clean_observations(raw)
        ex=make_examples(events,as_of="2024-07-01")
        row=ex[(ex.origin_date.eq(pd.Timestamp("2024-01-01",tz="UTC")))
               & ex.horizon_months.eq(3)].iloc[0]
        self.assertEqual(row.events_in_window,3)
        self.assertEqual(row.price_moves_in_window,3)
        self.assertEqual(row.target_price,1500)
        self.assertEqual(row.target_date,pd.Timestamp("2024-04-01",tz="UTC"))
        self.assertEqual(row.observed_target_date,pd.Timestamp("2024-03-20",tz="UTC"))
        self.assertEqual(row.days_after_last_event,12)
        self.assertGreater(row.total_abs_log_move,0.9)
        self.assertEqual(row.past_filings_90d,0)
        self.assertEqual(row.label_type,"CONDITIONAL_LAST_OBSERVED_FILING_IN_WINDOW")

    def test_no_new_filing_is_censored_not_flat_and_unfinished_is_excluded(self):
        raw=self.sample().iloc[:1].copy()
        events=clean_observations(raw)
        elapsed=make_examples(events,as_of="2026-11-13")
        self.assertTrue(elapsed.empty)
        self.assertEqual(elapsed.attrs["label_audit"]["3"]["no_observed_filing"],1)
        early=make_examples(events,as_of="2017-02-01")
        self.assertTrue(early.empty)
        self.assertEqual(early.attrs["label_audit"]["3"]["unfinished_windows"],1)

    def test_verified_repeated_filing_date_preserved_same_source_id(self):
        raw=self.sample().iloc[:2].copy()
        raw["dav_row_id"]="verified-filing"
        raw["source_date_basis"]="dav_filing_date"
        events=clean_observations(raw)
        self.assertEqual(len(events),2)
        self.assertGreater(len(make_examples(events,as_of="2026-11-13")),0)

    def test_history_features_cannot_see_future_events(self):
        raw=self.sample().iloc[:3].copy()
        raw["declaration_date"]=pd.to_datetime(
            ["2024-01-01","2024-02-01","2024-03-01"],utc=True)
        two=clean_observations(raw.iloc[:2])
        three=clean_observations(raw)
        a=make_examples(two,as_of="2024-12-01")
        b=make_examples(three,as_of="2024-12-01")
        origin=pd.Timestamp("2024-01-01",tz="UTC")
        a=a[a.origin_date.eq(origin)&a.horizon_months.eq(3)].iloc[0]
        b=b[b.origin_date.eq(origin)&b.horizon_months.eq(3)].iloc[0]
        for feature in ["past_filings_90d","past_filings_365d","past_abs_log_move_365d",
                        "previous_change","days_since_previous"]:
            self.assertEqual(a[feature],b[feature])
        self.assertEqual(a.events_in_window,1)
        self.assertEqual(b.events_in_window,2)

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

    def test_packaging_changes_do_not_form_temporal_pairs(self):
        raw = self.sample().iloc[:2].copy()
        raw.loc[raw.index[1], "package"] = "Box 100 tablets"
        self.assertTrue(make_examples(clean_observations(raw)).empty)

    def test_revised_id_and_conflicting_same_day_prices_require_review(self):
        raw = self.sample().iloc[:2].copy()
        raw["dav_row_id"] = "one-source-filing"
        self.assertTrue(clean_observations(raw).empty)
        raw = self.sample().iloc[:2].copy()
        raw["declaration_date"] = raw.iloc[0].declaration_date
        # Even a small disagreement must not be resolved by arbitrary ID order.
        self.assertTrue(clean_observations(raw).empty)

    def test_cross_source_numeric_id_collision_is_excluded(self):
        raw = self.sample().iloc[:2].copy()
        raw["source_name"] = "SILVER_R2"
        raw["price_source"] = "DAV_PUBLIC_DRUG_PRICE"
        self.assertTrue(clean_observations(raw).empty)

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
