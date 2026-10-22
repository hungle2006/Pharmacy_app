"""Market-level price trend and no-leakage regression tests, without Neon keys."""
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import numpy as np

from ml_price.market_forecast import (make_market_report, sample_stats, train_change,
                                       MIN_TRAIN, MIN_VALIDATION, MIN_TEST, horizon_time_split)
from ml_price.forecast import clean_observations, make_examples, time_split
from ml_price.tests.test_forecast import TestFutureForecast


class TestMarketTrends(unittest.TestCase):
    def test_market_summary_uses_same_medicine_relative_changes(self):
        ex=pd.DataFrame([
            {"registration_number":"a","origin_date":pd.Timestamp("2023-01-01",tz="UTC"),
             "target_date":pd.Timestamp("2023-07-01",tz="UTC"),"last_price":1000.0,"target_price":1100.0},
            {"registration_number":"a","origin_date":pd.Timestamp("2024-01-01",tz="UTC"),
             "target_date":pd.Timestamp("2024-07-01",tz="UTC"),"last_price":2000.0,"target_price":2200.0},
            {"registration_number":"b","origin_date":pd.Timestamp("2024-01-01",tz="UTC"),
             "target_date":pd.Timestamp("2024-07-01",tz="UTC"),"last_price":30000.0,"target_price":30000.0},
            {"registration_number":"c","origin_date":pd.Timestamp("2024-01-01",tz="UTC"),
             "target_date":pd.Timestamp("2024-07-01",tz="UTC"),"last_price":10000.0,"target_price":9000.0},
        ])
        stat=sample_stats(ex)
        self.assertEqual(stat["n_pairs"],4)
        self.assertEqual(stat["n_products"],3)
        self.assertAlmostEqual(stat["historical_change_pct"],0,places=3)
        self.assertAlmostEqual(stat["share_increase_pct"],100/3,places=1)
        self.assertAlmostEqual(stat["share_stable_pct"],100/3,places=1)
        self.assertAlmostEqual(stat["share_decrease_pct"],100/3,places=1)

    def test_fitted_report_contains_3_6_12_and_cannot_fabricate_approved_values(self):
        sample=TestFutureForecast().sample()
        with tempfile.TemporaryDirectory() as root:
            report=make_market_report(sample,root)
            self.assertEqual(report["kind"],"dav-market-price-trend")
            self.assertEqual(set(report["horizons"]),{"3","6","12"})
            self.assertGreater(report["labeled_pairs"],0)
            for item in report["horizons"].values():
                self.assertGreater(item["n_pairs"],0)
                self.assertIn(item["status"],("approved","insufficient_history","rejected_quality_gate"))
                if item["status"]!="approved":
                    self.assertIsNone(item["forecast_change_pct"])
                else:
                    self.assertGreaterEqual(item["test_gain_fraction"],.01)
            on_disk=json.loads((Path(root)/"report.json").read_text(encoding="utf-8"))
            self.assertEqual(on_disk["approved_horizons"],report["approved_horizons"])

    def test_independent_horizon_splits_embargo_future_labels(self):
        rows=[]
        for horizon, days in [(3,91),(6,183),(12,365)]:
            for i in range(150):
                origin=pd.Timestamp("2015-01-01",tz="UTC")+pd.Timedelta(days=i*35)
                rows.append({"horizon_months":horizon,"origin_date":origin,
                             "target_date":origin+pd.Timedelta(days=days),
                             "registration_number":f"drug-{horizon}-{i}"})
        examples=pd.DataFrame(rows)
        for horizon in (3,6,12):
            split=horizon_time_split(examples,horizon)
            self.assertIsNotNone(split, f"No split for horizon {horizon}")
            train,val,test=split
            self.assertTrue(train.horizon_months.eq(horizon).all())
            self.assertLess(train.target_date.max(),val.origin_date.min())
            self.assertLess(val.target_date.max(),test.origin_date.min())

    def test_constant_prices_do_not_fake_forecast(self):
        sample=TestFutureForecast().sample()
        sample["price_vnd"]=1000
        with tempfile.TemporaryDirectory() as root:
            report=make_market_report(sample,root)
            self.assertEqual(report["approved_horizons"],[])
            for item in report["horizons"].values():
                self.assertIsNone(item["forecast_change_pct"])
                self.assertEqual(item["historical_change_pct"],0)

    def test_strict_future_temporal_embargo(self):
        sample=TestFutureForecast().sample()
        rows=make_examples(clean_observations(sample))
        train,val,test=time_split(rows)
        self.assertLess(train.target_date.max(),val.origin_date.min())
        self.assertLess(val.target_date.max(),test.origin_date.min())
        selected=train_change(train,val,test,6)
        self.assertIsNotNone(selected["status"])
        if selected["status"]!="approved":
            self.assertIsNone(selected.get("forecast_change_pct"))


if __name__=="__main__":
    unittest.main()
