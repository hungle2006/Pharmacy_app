import unittest
import pandas as pd
from ml_price.feature_dataset import latest_snapshot, snapshot_fingerprint
from ml_price.tests.test_feature_price import FeaturePriceTests

class LatestDatasetTests(unittest.TestCase):
    def sample(self):
        return FeaturePriceTests().sample().iloc[:3].copy()

    def test_newest_source_date_not_crawl_time_or_price(self):
        raw=self.sample(); newer=raw.iloc[[0]].copy()
        newer['declaration_date']='2025-12-01';newer['price_vnd']=500
        raw['source_observed_at']='2026-11-13'
        result,a=latest_snapshot(pd.concat([raw,newer],ignore_index=True))
        self.assertEqual(result.loc[result.product_group.eq('REG:vn-0'),'price_vnd'].iloc[0],500)
        self.assertEqual(a['n_selected'],3)

    def test_latest_conflict_excluded_without_old_price_fallback(self):
        raw=self.sample();extra=raw.iloc[[0,0]].copy()
        extra['declaration_date']='2025-12-01';extra['price_vnd']=[500,700]
        result,a=latest_snapshot(pd.concat([raw,extra],ignore_index=True))
        self.assertNotIn('REG:vn-0',set(result.product_group))
        self.assertEqual(a['excluded_conflicting_latest_products'],1)

    def test_newest_missing_ingredient_does_not_revive_older_price(self):
        raw=self.sample();extra=raw.iloc[[0]].copy()
        extra['declaration_date']='2025-12-01';extra['ingredient']=None
        result,a=latest_snapshot(pd.concat([raw,extra],ignore_index=True))
        self.assertNotIn('REG:vn-0',set(result.product_group))

    def test_exact_recrawls_and_order_do_not_change_hash(self):
        raw=self.sample()
        self.assertEqual(snapshot_fingerprint(raw),snapshot_fingerprint(pd.concat([raw,raw]).sample(frac=1)))
        updated=raw.copy();updated.loc[updated.index[0],'price_vnd']+=1
        self.assertNotEqual(snapshot_fingerprint(raw),snapshot_fingerprint(updated))

    def test_corrected_filing_date_supersedes_later_legacy_reception(self):
        raw=self.sample().iloc[[0]].copy()
        raw['declaration_date']='2025-06-10'
        fixed=raw.copy();fixed['declaration_date']='2025-06-01'
        fixed['source_date_basis']='dav_filing_date';fixed['price_vnd']=777
        result,a=latest_snapshot(pd.concat([raw,fixed],ignore_index=True))
        self.assertEqual(result.price_vnd.iloc[0],777)
        self.assertEqual(a['excluded_superseded_legacy_rows'],1)

    def test_empty_or_all_invalid_snapshot_is_safe(self):
        raw=self.sample();raw['price_vnd']=0
        result,a=latest_snapshot(raw)
        self.assertEqual(len(result),0)
        self.assertEqual(a['excluded_invalid'],3)
        self.assertEqual(a['n_selected'],0)

    def test_asof_unknown_and_future_dates(self):
        raw=self.sample();raw['source_date_basis']=['UNKNOWN','dav_filing_date','LEGACY_UNVERIFIED']
        raw.loc[raw.index[1],'declaration_date']='2099-01-01'
        result,a=latest_snapshot(raw,as_of='2026-01-01')
        self.assertEqual(len(result),1)
        self.assertEqual(a['excluded_invalid'],2)

if __name__=='__main__':unittest.main()
