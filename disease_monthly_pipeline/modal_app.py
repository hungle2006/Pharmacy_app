"""Persistent deployed functions: GitHub submits background work; Modal owns completion."""
from pathlib import Path
import modal
ROOT=Path(__file__).parent
app=modal.App('disease-monthly-pipeline')
volume=modal.Volume.from_name('disease-monthly-storage',create_if_missing=True,version=2)
secrets=[modal.Secret.from_name('disease-training')]
locks=modal.Dict.from_name('disease-monthly-locks',create_if_missing=True)
source=['config.json','data_pipeline.py','prepare_train_ready.py','release.py','pipeline.py','train.py','inference.py']
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
def pipeline(force=False,submission_id='manual',allow_new_benchmark=False):
 import uuid,time
 token=uuid.uuid4().hex
 if not locks.put('active',{'token':token,'started_at':time.time()},skip_if_exists=True):
  return {'status':'already_running','note':'No duplicate GPU training was started'}
 try:return _pipeline_body(force,submission_id,allow_new_benchmark)
 finally:
  if locks.get('active',{}).get('token')==token:locks.pop('active',None)

@app.function(image=image,cpu=2,memory=8192,timeout=300,max_containers=2,scaledown_window=60,volumes={'/storage':volume},secrets=secrets)
def predict(text,top_k=5):
 environment()
 from inference import predict_text
 return predict_text(text,top_k)
