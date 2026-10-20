import csv,hashlib,json,tempfile,unittest
from pathlib import Path
from silver_auto.etl import source_digest,load_current,write_outputs,text_norm

def bronze(path, rows):
 fields=['dav_row_id','dav_drug_name','dav_active_ingredient_raw','dav_strength','dav_dosage_form']
 with path.open('w',encoding='utf8',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=fields+['__operation','__ingested_utc','__row_hash'])
  writer.writeheader()
  for raw,op in rows:
   writer.writerow({**raw,'__operation':op,'__ingested_utc':'2026-10-20T00:00:00Z',
    '__row_hash':source_digest(raw,fields)})
class SilverAutoTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_latest_snapshot_and_remove(self):
  a={'dav_row_id':'A','dav_drug_name':'Thuốc Đau','dav_active_ingredient_raw':'Paracetamol',
     'dav_strength':'500 MG','dav_dosage_form':'Viên nén'}
  b={**a,'dav_strength':'250 MG'}
  c={**a,'dav_row_id':'B'}
  bronze(self.root/'bronze.csv',[(a,'INSERT'),(b,'UPDATE'),(c,'INSERT'),(c,'REMOVE')])
  fields,active,stats=load_current('dav',self.root/'bronze.csv')
  self.assertEqual(stats['events'],4)
  self.assertEqual(stats['active'],1)
  self.assertEqual(active[0]['dav_strength'],'250 MG')
  report=write_outputs('dav',self.root/'bronze.csv',self.root/'out','hash')
  self.assertEqual(report['active_rows'],1)
  self.assertEqual(report['accepted'],1)
  with (self.root/'out/all.csv').open(encoding='utf8',newline='') as f:
   row=list(csv.DictReader(f))[0]
  self.assertEqual(row['silver_drug_name_norm'],'thuoc dau')
 def test_corruption_fails_closed(self):
  raw={'dav_row_id':'X','dav_drug_name':'Sample','dav_active_ingredient_raw':'X',
       'dav_strength':'50 MG','dav_dosage_form':'Tablet'}
  bronze(self.root/'bad.csv',[(raw,'INSERT')])
  path=self.root/'bad.csv'
  path.write_text(path.read_text().replace('50 MG','500 MG'))
  with self.assertRaisesRegex(ValueError,'integrity mismatch'):
   load_current('dav',path)
 def test_no_clinical_autoapproval(self):
  self.assertEqual(text_norm('Đường dùng'),'duong dung')
  raw={'dav_row_id':'Z','dav_drug_name':'Drug','dav_active_ingredient_raw':'A+B',
       'dav_strength':'100MG/5ML','dav_dosage_form':'Solution'}
  bronze(self.root/'in.csv',[(raw,'INSERT')])
  rep=write_outputs('dav',self.root/'in.csv',self.root/'out','hash')
  self.assertEqual(rep['review'],1)
  with (self.root/'out/review.csv').open() as f:r=list(csv.DictReader(f))[0]
  self.assertEqual(r['silver_mapping_verified'],'false')
if __name__=="__main__":unittest.main()
