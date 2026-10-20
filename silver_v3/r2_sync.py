"""S3-compatible R2 sync; immutable Silver publication, Bronze never altered."""
import argparse,hashlib,json,os,tempfile
from pathlib import Path
from .pipeline import INPUTS,produce
def connect():
 import boto3
 required=['R2_ENDPOINT','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY']
 missing=[k for k in required if not os.environ.get(k)]
 if missing:raise RuntimeError('Missing R2 secret environment: '+', '.join(missing))
 return boto3.client('s3',region_name='auto',endpoint_url=os.environ['R2_ENDPOINT'],
  aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',default='silver_v3/bronze_objects.json')
 p.add_argument('--dry-run',action='store_true');args=p.parse_args()
 cfg=json.loads(Path(args.config).read_text(encoding='utf8'))
 release=cfg.get('medi2_release','')
 if not release or 'REPLACE_' in release or release.startswith('2020'):
  raise ValueError('MEDI-2 2020 refresh disabled; require verified newer release')
 keys=cfg['bronze_keys']
 if set(keys)!=set(INPUTS):raise ValueError('Must configure all six Bronze keys')
 if any(not k.startswith('bronze/') or 'REPLACE_WITH_REAL' in k for k in keys.values()):
  raise ValueError('Configure exact verified bronze/ object keys')
 bucket=os.getenv('R2_BUCKET','pharmacy-data-lake');client=connect()
 with tempfile.TemporaryDirectory() as tmp:
  src=Path(tmp)/'input';dst=Path(tmp)/'output';src.mkdir()
  for ds,(filename,_) in INPUTS.items():client.download_file(bucket,keys[ds],str(src/filename))
  manifest=produce(src,dst)
  fingerprint=hashlib.sha256(json.dumps({k:v['sha256'] for k,v in sorted(manifest['datasets'].items())},sort_keys=True).encode()).hexdigest()[:24]
  prefix=f'silver/v3/run={fingerprint}/'
  if args.dry_run:
   print(json.dumps({'dry_run':True,'prefix':prefix,'counts':manifest['counts']},indent=2));return
  try:
   client.head_object(Bucket=bucket,Key=prefix+'manifest.json')
   print('Already published '+prefix);return
  except client.exceptions.ClientError as exc:
   if exc.response.get('Error',{}).get('Code') not in ('404','NotFound','NoSuchKey'):raise
  for f in dst.rglob('*.csv'):
   client.upload_file(str(f),bucket,prefix+f.relative_to(dst).as_posix(),ExtraArgs={'ContentType':'text/csv'})
  client.put_object(Bucket=bucket,Key=prefix+'manifest.json',
    Body=json.dumps(manifest,ensure_ascii=False,indent=2).encode(),ContentType='application/json')
  client.put_object(Bucket=bucket,Key='silver/v3/latest.json',
    Body=json.dumps({'prefix':prefix,'manifest':prefix+'manifest.json','sha256':fingerprint}).encode(),ContentType='application/json')
  print('Published '+prefix)
if __name__=='__main__':main()
