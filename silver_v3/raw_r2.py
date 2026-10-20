"""Rebuild raw Bronze sources, publish immutable STAGING only after manual approval."""
import argparse,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
def main():
 import boto3
 p=argparse.ArgumentParser();p.add_argument('--config',default='silver_v3/raw_keys.json')
 p.add_argument('--publish',action='store_true');a=p.parse_args()
 config=json.loads(Path(a.config).read_text('utf8'));keys=config['bronze_keys']
 expected=('dav_csv','rxnorm_raw_xlsx','icd10_vietnam_raw_xlsx','medi2_raw_xlsx')
 if set(keys)!=set(expected):raise ValueError('Expected four source keys')
 if any(not key.startswith('bronze/') or 'REPLACE_' in key for key in keys.values()):
  raise ValueError('Configure exact Bronze object keys')
 release=config.get('release',{}).get('medi2','')
 if not release or 'REPLACE_' in release or release.startswith('2020'):
  raise ValueError('MEDI2 2020 automatic refresh disabled; configure verified newer release')
 required=('R2_ENDPOINT','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY')
 if any(not os.getenv(k) for k in required):raise RuntimeError('Missing R2 secrets')
 s3=boto3.client('s3',endpoint_url=os.environ['R2_ENDPOINT'],region_name='auto',
  aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'])
 bucket=os.getenv('R2_BUCKET','pharmacy-data-lake')
 metadata={n:s3.head_object(Bucket=bucket,Key=key) for n,key in keys.items()}
 fingerprint=hashlib.sha256(json.dumps({k:{'key':keys[k],'etag':metadata[k]['ETag'],
  'size':metadata[k]['ContentLength']} for k in sorted(keys)},sort_keys=True).encode()).hexdigest()[:24]
 prefix=f'silver/v3/rebuilt-staging/run={fingerprint}/'
 try:
  s3.head_object(Bucket=bucket,Key=prefix+'manifest.json')
  print('UNCHANGED: '+prefix);return
 except s3.exceptions.ClientError as e:
  if e.response.get('Error',{}).get('Code') not in ('404','NotFound','NoSuchKey'):raise
 with tempfile.TemporaryDirectory() as tmp:
  raw=Path(tmp)/'raw';raw.mkdir()
  files={}
  for name in expected:
   f=raw/(name+Path(keys[name]).suffix)
   s3.download_file(bucket,keys[name],str(f));files[name]=f
  out=Path(tmp)/'rebuilt'
  subprocess.run([sys.executable,'-m','silver_v3.rebuild_raw',
   '--dav-csv',str(files['dav_csv']),'--rxnorm-raw-xlsx',str(files['rxnorm_raw_xlsx']),
   '--icd10-vietnam-raw-xlsx',str(files['icd10_vietnam_raw_xlsx']),
   '--medi2-raw-xlsx',str(files['medi2_raw_xlsx']),'--output-dir',str(out)],check=True)
  manifest={'source_keys':keys,'source_etags':{k:metadata[k]['ETag'] for k in keys},
   'medi2_release':release,'fingerprint':fingerprint,'warning':'STAGING_ONLY_UNCURATED_MAPPING'}
  (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
  if a.publish:
   for f in out.rglob('*'):
    if f.is_file() and f.name!='manifest.json':
     s3.upload_file(str(f),bucket,prefix+f.relative_to(out).as_posix())
   s3.upload_file(str(out/'manifest.json'),bucket,prefix+'manifest.json')
   print('Published staging '+prefix)
  else:print('DRY RUN, no R2 writes: '+json.dumps(manifest,ensure_ascii=False))
if __name__=='__main__':main()
