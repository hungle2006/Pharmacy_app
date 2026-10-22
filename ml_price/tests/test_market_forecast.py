"""Tests for the aggregate DAV market price outlook, not per-drug forecasts."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from ml_price.market_forecast import (
    HORIZONS, build_market_report, evaluate_horizon, make_market_pairs,
    out_of_time_split, stats,
)
from ml_price.forecast import clean_observations

class MarketForecastTest(unittest.TestCase):
    def records(self,changing=True):
        data=[]
        for product in range(20):
            for month in range(72):
                at=pd.Timestamp("2020-01-16",tz="UTC")+pd.DateOffset(months=month)
                price=1000*(1+product/5)*np.exp((.01 if changing else 0)*month)
                data.append({
                    "dav_row_id":str(product*100+month),
                    "registration_number":f"VD-{product}",
                    "ingredient":f"Ingredient {product%5}",
                    "strength":"100mg","dosage_form":"Viên nén",
                    "manufacturer":"Factory A","country":"Việt Nam",
                    "package":"Hộp 10 viên","product_package":"Hộp 10 viên",
                    "declaration_date":at,"price_vnd":round(price,2),
                    "price_type":"KK TRONG NƯỚC","unit":"viên",
                })
        return pd.DataFrame(data)

    def test_only_matching_registration_type_unit_and_later_prices(self):
        cleaned=clean_observations(self.records())
        pairs=make_market_pairs(cleaned)
        self.assertGreater(len(pairs),300)
        self.assertTrue(pairs.target_date.gt(pairs.origin_date).all())
        self.assertEqual(set(pairs.horizon_months.unique()),set(HORIZONS))
        self.assertEqual(pairs.registration_number.nunique(),20)
        self.assertTrue(pairs.log_change.gt(0).all())

    def test_out_of_time_split_prevents_future_labels(self):
        pairs=make_market_pairs(clean_observations(self.records()))
        tr,va,te=out_of_time_split(pairs[pairs.horizon_months.eq(6)])
        self.assertLess(tr.target_date.max(),va.origin_date.min())
        self.assertLess(va.target_date.max(),te.origin_date.min())

    def test_trend_only_report_and_quality_gated_predictions(self):
        with tempfile.TemporaryDirectory() as folder:
            report=build_market_report(self.records(changing=True),folder)
            self.assertEqual(report["kind"],"market-declaration-price-trend")
            self.assertGreater(report["paired_observations"],100)
            self.assertEqual(set(report["horizons"]),{"1","3","6","12"})
            for h,info in report["horizons"].items():
                self.assertGreater(info["n_pairs"],0)
                self.assertGreater(info["historical_change_pct"],0)
                self.assertTrue(
                    info["forecast_change_pct"] is None or info["status"]=="approved")
            parsed=json.loads((Path(folder)/"report.json").read_text())
            self.assertEqual(parsed["approved_horizons"],report["approved_horizons"])

    def test_unchanged_prices_not_invented_as_increases(self):
        with tempfile.TemporaryDirectory() as folder:
            report=build_market_report(self.records(changing=False),folder)
            for h,info in report["horizons"].items():
                self.assertEqual(info["historical_change_pct"],0)
                self.assertEqual(info["share_unchanged_pct"],100)
                self.assertIsNone(info["forecast_change_pct"])
                self.assertNotEqual(info["status"],"approved")

    def test_extreme_ratio_excluded_and_units_not_pooled_as_price_levels(self):
        raw=self.records()
        ix=raw.index[-1]
        raw.loc[ix,"price_vnd"]=raw.loc[ix,"price_vnd"]*1000
        cleaned=clean_observations(raw)
        pairs=make_market_pairs(cleaned)
        self.assertLess(float(pairs.log_change.max()),np.log(8)+1e-7)
        self.assertTrue((pairs["unit"]=="viên").all())
        sample=stats(pairs[pairs.horizon_months.eq(3)])
        self.assertEqual(round(sample["share_up_pct"]+sample["share_down_pct"]+
                               sample["share_unchanged_pct"],1),100)
if __name__=="__main__":
    unittest.main()
