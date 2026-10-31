from pathlib import Path
import hashlib,json,os,shutil
from data_pipeline import snapshot_dataset,prepare
from release import read_pointer,model_directory,publish,notify_render
ROOT=Path(__file__).parent
def month():
 from datetime import datetime
 from zoneinfo import ZoneInfo
 return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m")

def config():return json.loads((ROOT/'config.json').read_text())
def prepare_run(storage,force=False,submission_id='manual'):
 c=config();storage=Path(storage);storage.mkdir(parents=True,exist_ok=True)
 root,files,snapshot=snapshot_dataset(c,storage/'hf_cache')
 signature=hashlib.sha256(json.dumps({'config':c,'data':snapshot['data_fingerprint']},sort_keys=True).encode()).hexdigest()
 period=month();last=storage/'last_processed.json'
 if not force and last.exists():
  previous=json.loads(last.read_text())
  if previous['signature']==signature and previous.get('period')==period:return {'status':'skipped_completed_this_month','signature':signature}
  if c['skip_unchanged'] and previous['signature']==signature:return {'status':'skipped_unchanged','signature':signature}
 safe=''.join(x for x in submission_id if x.isalnum() or x in '-_')[:64]
 run_id='run-'+period+'-'+signature[:20]+('-'+safe if force else '')
 run=storage/'runs'/run_id;run.mkdir(parents=True,exist_ok=True)
 # A partial run keeps its frozen dataset and model config so an interruption resumes exactly.
 context=run/'context.json'
 if context.exists():return json.loads(context.read_text())
 prep=prepare(root,files,storage/'benchmarks'/c['benchmark_version'],run/'data')
 seed=c['base_model']
 active=read_pointer(c['model_repo'])
 if active and active['benchmark_sha256']==prep['benchmark_sha256']:
  seed=str(model_directory(active,c['model_repo'],cache=str(storage/'hf_cache')))
 result={'status':'prepared','period':period,'signature':signature,'run_id':run_id,'run_dir':str(run),'seed_model':seed,'snapshot':snapshot,'preparation':prep}
 context.write_text(json.dumps(result,ensure_ascii=False,indent=2));return result

def train_run(context,persist=None,allow_cpu=False,model_override=None,max_steps=None):
 from train import main
 c=config();run=Path(context['run_dir']);data=run/'data/disease_train_ready.parquet';out=run/'training';out.mkdir(exist_ok=True)
 if (out/'export_complete.json').is_file() and (out/'evaluation.json').is_file() and (out/'best_model/config.json').is_file():
  shutil.copy2(run/'data/preparation_report.json',out/'preparation_report.json')
  return json.loads((out/'evaluation.json').read_text())
 # Existing training script verifies the preparation hash before any tokenization.
 argv=['--data',str(data),'--output',str(out),'--model',model_override or context['seed_model'],'--epochs',str(c['epochs']),'--batch-size',str(c['batch_size']),'--max-length',str(c['max_length']),'--lr',str(c['learning_rate'])]
 if allow_cpu:argv.append('--allow-cpu')
 if max_steps is not None:argv+=['--max-steps',str(max_steps)]
 metrics=main(argv,persist_checkpoint=persist)
 shutil.copy2(run/'data/preparation_report.json',out/'preparation_report.json')
 return metrics

def finish_run(context,storage,allow_new_benchmark=False):
 run=Path(context['run_dir']);result=publish(config(),context['run_id'],run/'training',context['preparation'],context['snapshot'],allow_new_benchmark)
 if result['promoted']:result['render']=notify_render()
 # Avoid duplicate submissions in the same month; a new calendar month gets a fresh training run.
 target=Path(storage)/'last_processed.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps({'signature':context['signature'],'period':context['period'],'result':result}));temp.replace(target)
 (run/'status.json').write_text(json.dumps({'status':'completed',**result},indent=2));return result
