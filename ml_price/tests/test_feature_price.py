"""Meaningful leakage, numerical and train/serve parity checks; no live DB."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from ml_price.tests.test_train import TestPriceML
from ml_price.feature_price import prepare,split_dates,fit_segment
from ml_price.feature_schema import normalize,interval
from ml_price.feature_store import FeatureStore
from ml_price.segments import segment_id

class FeaturePriceTests(unittest.TestCase):
    def sample(self):
        d=TestPriceML().sample(600)
        d['price_type']='expected_wholesale_price_vat';d['unit']='viên'
        return d

    def test_future_nonfinite_rows_and_registration_duplicates_do_not_leak(self):
        raw=self.sample();extra=raw.iloc[[0,1,2]].copy()
        extra.loc[extra.index[0],'price_vnd']=np.inf
        extra.loc[extra.index[1],'declaration_date']=pd.Timestamp('2099-01-01')
        extra.loc[extra.index[2],'declaration_date']=pd.Timestamp('2026-01-01')
        cleaned=prepare(pd.concat([raw,extra],ignore_index=True))
        self.assertEqual(len(cleaned),600)
        parts=split_dates(cleaned)
        self.assertEqual(sum(map(len,parts)),600)
        for i in range(3):
            self.assertLess(parts[i].declaration_date.max(),parts[i+1].declaration_date.min())
            for j in range(i+1,4):self.assertFalse(set(parts[i].product_group)&set(parts[j].product_group))
        self.assertEqual(normalize('  PARACETAMOL  500mg '),'paracetamol 500mg')

    def test_same_day_groups_are_never_split_between_cohorts(self):
        raw=self.sample();raw['declaration_date']=pd.Timestamp('2025-01-01')
        with self.assertRaisesRegex(ValueError,'DATE_SEPARATION'):split_dates(prepare(raw))

    def test_interval_nonnegative_ordered_and_calibrated_in_log_space(self):
        p=np.array([0.,100.,100000.]);a,b=interval(p,.5)
        self.assertTrue(np.all(a>=0));self.assertTrue(np.all(a<=p));self.assertTrue(np.all(b>=p))

    def test_real_training_bundle_and_serving_reproduce_heldout_predictions(self):
        with tempfile.TemporaryDirectory() as temp:
            r=fit_segment(self.sample(),temp,'testversion',iterations=30)
            self.assertEqual(sum(r['error_bins'][i]['value'] for i in range(6)),r['n_test'])
            self.assertEqual(sum(r['n_'+x] for x in ['train','validation','calibration','test']),r['n_clean'])
            self.assertGreater(r['n_calibration'],0)
            self.assertIn(r['status'],['approved','experimental'])
            self.assertEqual(len(r['validation_candidates']),3)
            metadata=json.loads((Path(temp)/'metadata.json').read_text())
            from catboost import CatBoostRegressor
            model=CatBoostRegressor();model.load_model(str(Path(temp)/'model.cbm'))
            store=FeatureStore();store.report={'version':'testversion','segments':[r]};store.checked=__import__('time').monotonic()
            store.models[r['id']]=(model,metadata)
            row=r['examples'][0];data={**row['features'],'price_type':r['price_type'],'unit':r['unit']}
            actual=store.predict(data)
            self.assertAlmostEqual(actual['prediction_vnd'],row['predicted_price_vnd'],places=2)
            self.assertLessEqual(actual['lower_vnd'],actual['prediction_vnd'])
            self.assertGreaterEqual(actual['upper_vnd'],actual['prediction_vnd'])
            with self.assertRaisesRegex(ValueError,'UNKNOWN_INGREDIENT'):store.predict({**data,'ingredient':'never in training'})
            with self.assertRaisesRegex(ValueError,'UNSUPPORTED_PRICE_SEGMENT'):store.predict({**data,'unit':'new-unit'})
            self.assertNotIn('baseline_priors',r)

if __name__=='__main__':unittest.main()
