"""Small public report from the promoted pointer; never downloads model weights."""
import json, math
from pathlib import Path
from release import read_pointer

def public_report(pointer):
 if pointer is None:return {'status':'not_trained'}
 metrics={}
 for split in ['validation','test']:
  metrics[split]={}
  for metric in ['accuracy','macro_f1','balanced_accuracy','top3_accuracy','top5_accuracy']:
   value=pointer.get('metrics',{}).get(split,{}).get(f'{split}_{metric}')
   if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=1:metrics[split][metric]=value
 return {'status':'ready','model_run':pointer['run_id'],'dataset_revision':pointer['dataset_revision'],'benchmark_sha256':pointer['benchmark_sha256'],'metrics':metrics}

def get_report():
 config=json.loads((Path(__file__).parent/'config.json').read_text())
 return public_report(read_pointer(config['model_repo']))
