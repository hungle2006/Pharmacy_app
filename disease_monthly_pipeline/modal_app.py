"""Persistent deployed functions: GitHub submits background work; Modal owns completion."""
from pathlib import Path
import modal
ROOT=Path(__file__).parent
app=modal.App('disease-monthly-pipeline')
volume=modal.Volume.from_name('disease-monthly-storage',create_if_missing=True,version=2)
secrets=[modal.Secret.from_name('disease-training')]
locks=modal.Dict.from_name('disease-monthly-locks',create_if_missing=True)
source=['config.json','data_pipeline.py','prepare_train_ready.py','release.py','pipeline.py','train.py','inference.py','model_report.py','enrichment.py','enrichment_config.json','crawl_sources.json','published_sources.py','published_sources.json','diagnostics.py','balancing.py','ddxplus.py','ddxplus_sources.json','SOURCE_NOTICES.md','web_collectors.py','web_collectors.json']
image=modal.Image.debian_slim(python_version='3.11').pip_install_from_requirements(str(ROOT/'requirements-train.txt'))
for name in source:image=image.add_local_file(str(ROOT/name),'/app/'+name)

def environment():
 import os,sys
 os.environ['HF_HOME']='/storage/hf_home'
 os.environ['MODEL_CACHE']='/storage/hf_cache'
 sys.path.insert(0,'/app')

@app.function(image=image,cpu=4,memory=8192,timeout=3600,volumes={'/storage':volume},secrets=secrets)
def prepare_data(force=False,submission_id='manual'):
 environment();volume.reload()
 # Dataset publication has its own lock; training always uses its pinned snapshot.
 result=refresh_dataset.remote()
 if result.get('status') in {'failed','already_running'}:raise RuntimeError('Dataset refresh is not ready; retry preparation after it completes')
 volume.reload()
 from pipeline import prepare_run
 result=prepare_run('/storage',force,submission_id);volume.commit();return result

@app.function(image=image,gpu='L4',cpu=4,memory=16384,timeout=79200,volumes={'/storage':volume},secrets=secrets)
def train_gpu(context):
 environment();volume.reload()
 from pipeline import train_run
 try:return train_run(context,persist=volume.commit)
 finally:volume.commit()

def _pipeline_body(force=False,submission_id='manual',allow_new_benchmark=False):
 environment()
 context=prepare_data.remote(force,submission_id)
 if context['status'].startswith('skipped'):return context
 try:
  train_gpu.remote(context)
  volume.reload()
  from pipeline import finish_run
  result=finish_run(context,'/storage',allow_new_benchmark);volume.commit();return result
 except Exception:
  volume.reload()
  # No partial model is promoted. Do not echo exception messages that can include authenticated URLs.
  import json
  from pathlib import Path
  path=Path(context['run_dir'])/'status.json';path.write_text(json.dumps({'status':'failed','run_id':context['run_id'],'resume':'same dataset/config run can resume; inspect Modal logs privately'}));volume.commit()
  raise

@app.function(image=image,cpu=.125,memory=512,timeout=86400,max_containers=1,volumes={'/storage':volume},secrets=secrets)
def pipeline(force=False,submission_id='manual',allow_new_benchmark=False,wait_for_lock=False):
 import uuid,time,json
 token=uuid.uuid4().hex;deadline=time.monotonic()+(1800 if wait_for_lock else 0)
 def record(status,**extra):
  volume.reload()
  path=Path('/storage/maintenance_status.json');temp=path.with_suffix('.tmp')
  temp.write_text(json.dumps({'status':status,'submission_id':submission_id,'updated_at_unix':time.time(),**extra}));temp.replace(path);volume.commit()
 while not locks.put('active',{'token':token,'started_at':time.time()},skip_if_exists=True):
  if not wait_for_lock or time.monotonic()>=deadline:
   return {'status':'already_running','note':'No duplicate GPU training started; retry after the active operation finishes'}
  record('waiting_for_existing_operation')
  time.sleep(60)
 try:
  record('preparing_and_training')
  result=_pipeline_body(force,submission_id,allow_new_benchmark)
  record('completed',result=result)
  return result
 except Exception as error:
  record('failed',error_type=type(error).__name__)
  raise
 finally:
  if locks.get('active',{}).get('token')==token:locks.pop('active',None)

@app.function(image=image,cpu=2,memory=8192,timeout=300,max_containers=2,scaledown_window=60,volumes={'/storage':volume},secrets=secrets)
def predict(text,top_k=5):
 environment()
 from inference import predict_text
 return predict_text(text,top_k)

@app.function(image=image,cpu=.125,memory=512,timeout=120,max_containers=2,volumes={'/storage':volume},secrets=secrets)
def report():
 environment()
 from model_report import get_report
 return get_report()

@app.function(image=image,cpu=4,memory=8192,timeout=3600,max_containers=1,volumes={'/storage':volume},secrets=secrets)
def refresh_dataset():
 import uuid,time
 environment();volume.reload();token=uuid.uuid4().hex
 if not locks.put('dataset_refresh',{'token':token,'started_at':time.time()},skip_if_exists=True):return {'status':'already_running'}
 try:
  from enrichment import run
  return run('/storage',publish=True)
 except Exception as error:
  import traceback
  frames=[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__) if Path(f.filename).name in ['enrichment.py','data_pipeline.py','modal_app.py','published_sources.py','ddxplus.py','web_collectors.py']]
  return {'status':'failed','error_type':type(error).__name__,'error_frames':frames}
 finally:
  volume.commit()
  if locks.get('dataset_refresh',{}).get('token')==token:locks.pop('dataset_refresh',None)


@app.function(image=image,cpu=.125,memory=512,timeout=120,max_containers=1,volumes={'/storage':volume},secrets=secrets)
def operations_status():
 """Read-only operation summaries, never credentials or patient text."""
 import time,json
 environment();volume.reload()
 active=locks.get('active',{})
 result={'dataset_refresh_active':bool(locks.get('dataset_refresh',{})),'active_operation':bool(active),'active_age_seconds':max(0,int(time.time()-active['started_at'])) if active else None}
 path=Path('/storage/maintenance_status.json')
 if path.is_file():result['maintenance']=json.loads(path.read_text())
 runs=sorted(Path('/storage/runs').glob('*/context.json'),key=lambda p:p.stat().st_mtime,reverse=True)
 if runs:
  run=runs[0].parent;result['latest_run_id']=run.name
  for name in ['status.json','training/evaluation.json','training/publication.json']:
   p=run/name
   if p.is_file():result[name.replace('/','_')]=json.loads(p.read_text())
 return result
