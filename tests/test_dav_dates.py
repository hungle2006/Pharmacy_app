"""Date lineage and additive Bronze migration, without external services."""
import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'pipeline/bronze'))
from crawl_dav import convert
from compact_csv import merge_snapshot, digest
from silver_auto.etl import evaluate, load_current
from test_compact_csv import FakeR2, create_csv


class DateLineageTests(unittest.TestCase):
    def test_source_dates_are_separate_and_never_fabricated(self):
        row=convert({'id':1,'ngayKK_KKL':'2026-01-01T12:00:00+07:00',
                     'ngayTiepNhan':'2026-01-04T15:00:00+07:00'},'https://example.org')
        result=evaluate('dav',row)
        self.assertEqual(result['silver_price_date'],'2026-01-01')
        self.assertEqual(result['silver_price_date_basis'],'dav_filing_date')
        self.assertEqual(row['dav_reception_date'],'2026-01-04T15:00:00+07:00')
        result=evaluate('dav',convert({'id':1,'ngayTiepNhan':'2026-01-04'},'https://example.org'))
        self.assertEqual(result['silver_price_date'],'')
        self.assertEqual(result['silver_price_date_basis'],'UNKNOWN')

    def test_invalid_date_fallback_is_publication_not_reception(self):
        for value in ['2026-02-30','2999-01-01','2026/01/01']:
            result=evaluate('dav',{'dav_filing_date':value,'dav_publication_date':'2026-01-02',
                                  'dav_reception_date':'2026-01-05'})
            self.assertEqual(result['silver_price_date'],'2026-01-02')
            self.assertEqual(result['silver_price_date_basis'],'dav_publication_date')

    def test_migrate_old_history_without_losing_values_or_repeating_events(self):
        s3=FakeR2()
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'in.csv'
            create_csv(path,[{'dav_row_id':'1','dav_price_vnd':'100'}])
            merge_snapshot(s3,'dav',path)
            create_csv(path,[{'dav_row_id':'1','dav_price_vnd':'110'}])
            merge_snapshot(s3,'dav',path)
            new={'dav_row_id':'1','dav_price_vnd':'110','dav_filing_date':'2026-01-01',
                 'dav_publication_date':'','dav_reception_date':'2026-01-03'}
            with path.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(new));w.writeheader();w.writerow(new)
            result=merge_snapshot(s3,'dav',path)
            self.assertEqual(result['schema_extension']['old_rows_preserved'],2)
            rows=list(csv.DictReader(io.StringIO(s3.items['bronze/dav.csv'][0].decode())))
            self.assertEqual([r['dav_price_vnd'] for r in rows],['100','110','110'])
            self.assertEqual(rows[0]['dav_filing_date'],'')
            fields=list(new)
            self.assertTrue(all(r['__row_hash']==digest(r,fields) for r in rows))
            self.assertEqual(merge_snapshot(s3,'dav',path)['new_events'],0)
            history=Path(root)/'history.csv';history.write_bytes(s3.items['bronze/dav.csv'][0])
            _,current,_=load_current('dav',history)
            self.assertEqual(current[0]['dav_filing_date'],'2026-01-01')

if __name__=='__main__':unittest.main()
