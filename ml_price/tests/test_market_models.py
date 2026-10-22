"""Regressions for time-embargoed market candidate selection."""
import unittest
import numpy as np
import pandas as pd

from ml_price.market_models import rolling_folds, fit_predict, evaluate_market_horizon


def fixture(n=180, horizon=6, signal=True):
    rows=[]
    for i in range(n):
        origin=pd.Timestamp('2005-01-01',tz='UTC')+pd.Timedelta(days=35*i)
        registration=f'reg{i%38}'
        group='A' if i%2 else 'B'
        ratio = (.09 if group=='A' else -.06) if signal else 0.
        rows.append(dict(horizon_months=horizon, registration_number=registration,
                         origin_date=origin, target_date=origin+pd.Timedelta(days=183),
                         last_price=1000., target_price=1000.*np.exp(ratio),
                         ingredient=group, price_type='kind', unit='viên',
                         previous_change=0., days_since_previous=183.))
    return pd.DataFrame(rows)

class MarketModelsTests(unittest.TestCase):
    def test_rolling_embargo(self):
        folds=rolling_folds(fixture(),6)
        self.assertGreaterEqual(len(folds),2)
        for train,validation,start,end in folds:
            self.assertLess(train.target_date.max(),validation.origin_date.min())
            self.assertLess(validation.target_date.max(),end)

    def test_all_candidates_finite(self):
        f=fixture()
        train=f.iloc[:120]; query=f.iloc[120:]
        for model in ('time_weighted','hierarchical','temporal_ridge'):
            p=fit_predict(train,query,model)
            self.assertEqual(len(p),len(query))
            self.assertTrue(np.isfinite(p).all())

    def test_strong_group_signal_can_pass_untouched_holdout(self):
        observations=[]
        for i in range(38):
            for year in (2022, 2023):
                observations.append(dict(
                    registration_number=f'reg{i}',price_type='kind',unit='viên',
                    date=pd.Timestamp(f'{year}-01-01',tz='UTC'),
                    price_vnd=1000 if year==2022 else 1090,
                    ingredient='A' if i%2 else 'B',strength='10mg',
                    dosage_form='tablet',manufacturer='maker',country='VN',package='box'))
        result=evaluate_market_horizon(fixture(),6,pd.DataFrame(observations))
        self.assertEqual(result['status'],'approved')
        self.assertEqual(result['selected_model'],'hierarchical')
        self.assertGreater(result['test_gain_fraction'],.01)
        self.assertEqual(len(result['test_gain_ci95_pct_points']),2)
        self.assertEqual(len(result['forecast_sample_ci90_pct']),2)

    def test_constant_prices_cannot_approve(self):
        result=evaluate_market_horizon(fixture(signal=False),6)
        self.assertNotEqual(result['status'],'approved')
        self.assertIsNone(result['forecast_change_pct'])
        self.assertIn('model_comparison',result)

    def test_report_candidate_diagnostics_without_current_references(self):
        result=evaluate_market_horizon(fixture(signal=True),6)
        self.assertNotEqual(result['status'],'approved')
        self.assertIsNone(result['forecast_change_pct'])
        self.assertGreaterEqual(result['n_walkforward_folds'],2)
        self.assertEqual({c['name'] for c in result['model_comparison']},
                         {'time_weighted','hierarchical','temporal_ridge'})

if __name__=='__main__': unittest.main()
