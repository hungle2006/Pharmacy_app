import csv,json,tempfile,unittest
from pathlib import Path
from botocore.exceptions import ClientError
from silver_auto.etl import source_digest
from silver_auto.r2_runner import process
def absent(key):
 return ClientError({"Error":{"Code":"404","Message":key}},"HeadObject")
class FakeR2:
 def __init__(self):self.objects={}
 def head_object(self,Bucket,Key):
  if Key not in self.objects:raise absent(Key)
  d,m=self.objects[Key];return {'ContentLength':len(d),'Metadata':m}
 def get_object(self,Bucket,Key):
  if Key not in self.objects:raise absent(Key)
  import io
  return {'Body':io.BytesIO(self.objects[Key][0])}
 def download_file(self,bucket,key,path):
  Path(path).write_bytes(self.objects[key][0])
 def upload_file(self,path,bucket,key,ExtraArgs=None):
  self.objects[key]=(Path(path).read_bytes(),(ExtraArgs or {}).get('Metadata',{}))
 def put_object(self,Bucket,Key,Body,**kwargs):
  self.objects[Key]=(Body if isinstance(Body,bytes) else Body.encode(),{})
 def list_objects_v2(self,Bucket,Prefix,MaxKeys=1000,**kwargs):
  return {'Contents':[{'Key':k} for k in self.objects if k.startswith(Prefix)],'IsTruncated':False}
 def delete_object(self,Bucket,Key):
  self.objects.pop(Key,None)
def example():
 raw={'dav_row_id':'1','dav_drug_name':'Thuốc mẫu',
   'dav_active_ingredient_raw':'paracetamol','dav_strength':'500 MG',
   'dav_dosage_form':'Viên nén'}
 fields=list(raw)
 import io
 buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=fields+
  ['__operation','__ingested_utc','__row_hash']);writer.writeheader()
 writer.writerow({**raw,'__operation':'INSERT','__ingested_utc':'2026-10-20T01:00:00+00:00',
   '__row_hash':source_digest(raw,fields)})
 return buf.getvalue().encode('utf8')
class TestR2Runner(unittest.TestCase):
 def test_atomic_publish_and_idempotent(self):
  s=FakeR2();s.objects['bronze/dav.csv']=(example(),{})
  with tempfile.TemporaryDirectory() as td:
   a=process(s,'dav',td,False)
   self.assertEqual(a['state'],'published')
   manifest=json.loads(s.objects['_control/silver/dav.json'][0])
   self.assertEqual(manifest['silver_key'],'silver/dav.csv')
   self.assertIn('silver/dav.csv',s.objects)
   self.assertEqual(len([k for k in s.objects if k.startswith('silver/')]),1)
   b=process(s,'dav',td,False)
   self.assertEqual(b['state'],'unchanged')
 def test_replaces_in_place_and_cleans_legacy_after_verification(self):
  s=FakeR2()
  s.objects['bronze/dav.csv']=(example(),{})
  s.objects['silver/v4/dav/version=old/all.csv']=(b'old',{})
  s.objects['silver/dav/sha256=old/snapshot.csv.gz']=(b'old',{})
  with tempfile.TemporaryDirectory() as td:
   first=process(s,'dav',td,False,True)
   self.assertEqual(first['legacy_removed'],2)
   self.assertEqual(sorted(k for k in s.objects if k.startswith('silver/')),['silver/dav.csv'])
   self.assertEqual(process(s,'dav',td,False,True)['state'],'unchanged')
 def test_dry_run_never_publishes(self):
  s=FakeR2();s.objects['bronze/dav.csv']=(example(),{})
  with tempfile.TemporaryDirectory() as td:
   res=process(s,'dav',td,True)
  self.assertEqual(res['state'],'dry_run')
  self.assertFalse(any(x.startswith('silver/') for x in s.objects))
 def test_missing_bronze_skipped(self):
  s=FakeR2()
  with tempfile.TemporaryDirectory() as td:
   self.assertEqual(process(s,'dav',td,False)['state'],'skipped')
 def test_medi_blocked_when_unapproved(self):
  import os
  saved=os.environ.pop('MEDI_HPS_APPROVED_RELEASE',None)
  try:
   s=FakeR2()
   with tempfile.TemporaryDirectory() as td:
    self.assertEqual(process(s,'medi_hps',td,False)['state'],'skipped')
  finally:
   if saved is not None:os.environ['MEDI_HPS_APPROVED_RELEASE']=saved
if __name__=='__main__':unittest.main()
