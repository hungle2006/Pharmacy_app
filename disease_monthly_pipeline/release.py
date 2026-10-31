"""Immutable model artifacts + atomic deployment pointer; validation-only promotion."""
from pathlib import Path,PurePosixPath
import json,math,os,urllib.request
from huggingface_hub import HfApi,hf_hub_download,snapshot_download,CommitOperationAdd
from huggingface_hub.errors import EntryNotFoundError

def read_pointer(repo,api=None,revision='main'):
 try:path=hf_hub_download(repo_id=repo,filename='deployment.json',revision=revision)
 except EntryNotFoundError:return None
 return json.loads(Path(path).read_text())
def promotion_decision(candidate,current,config,allow_new_benchmark=False):
 score=float(candidate['validation_macro_f1'])
 if not math.isfinite(score) or score<float(config['minimum_validation_macro_f1']):return False,'below_configured_validation_threshold'
 if current:
  if candidate['benchmark_sha256']!=current['benchmark_sha256'] and not allow_new_benchmark:return False,'benchmark_changed_requires_explicit_promotion'
  if candidate['benchmark_sha256']==current['benchmark_sha256'] and score+float(config['promotion_tolerance'])<float(current['validation_macro_f1']):return False,'validation_regression'
 return True,'accepted'
def model_directory(pointer,repo,cache=None):
 path=PurePosixPath(pointer['model_path'])
 if path.is_absolute() or '..' in path.parts or not str(path).startswith('versions/'):raise ValueError('Invalid model artifact path')
 root=Path(snapshot_download(repo_id=repo,revision=pointer['artifact_revision'],allow_patterns=[str(path)+'/*'],cache_dir=cache))
 result=root/str(path)
 if not (result/'model.safetensors').is_file() and not (result/'model.safetensors.index.json').is_file():raise ValueError('No safetensors model in selected release')
 return result
def validate_export(root):
 from safetensors import safe_open
 from tokenizers import Tokenizer
 root=Path(root)
 if not (root/'export_complete.json').is_file():raise ValueError('No completed model export marker')
 model=root/'best_model';cfg=json.loads((model/'config.json').read_text());labels=cfg.get('id2label',{})
 if len(labels)<2:raise ValueError('Invalid model label map')
 Tokenizer.from_file(str(model/'tokenizer.json'))
 weights=sorted(model.glob('*.safetensors'))
 if not weights:raise ValueError('Missing safetensors weights')
 classifier_ok=False
 for path in weights:
  with safe_open(path,framework='np') as f:
   for name in f.keys():
    if name.endswith('classifier.weight') or name.endswith('classifier.out_proj.weight'):
     classifier_ok=f.get_slice(name).get_shape()[0]==len(labels)
 if not classifier_ok:raise ValueError('Classification head does not match label map')
 return True

def publish(config,run_id,run_dir,prep,snapshot,allow_new_benchmark=False,api=None):
 api=api or HfApi();repo=config['model_repo'];root=Path(run_dir);validate_export(root);metrics=json.loads((root/'evaluation.json').read_text())
 active=read_pointer(repo)
 if active and active.get('run_id')==run_id:
  return {'run_id':run_id,'promoted':True,'reason':'already_promoted','artifact_revision':active['artifact_revision'],'validation_macro_f1':active['validation_macro_f1']}
 candidate={'run_id':run_id,'benchmark_sha256':prep['benchmark_sha256'],'validation_macro_f1':metrics['validation']['validation_macro_f1'],'dataset_revision':snapshot['dataset_revision'],'data_fingerprint':snapshot['data_fingerprint'],'model_path':f'versions/{run_id}/best_model','max_length':config['max_length'],'metrics':metrics}
 (root/'release.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2))
 paths=[p for p in (root/'best_model').rglob('*') if p.is_file() and p.suffix in ['.json','.safetensors','.txt','.model']]+[root/'evaluation.json',root/'per_class_test.json',root/'release.json',root/'preparation_report.json']
 operations=[CommitOperationAdd(path_in_repo=f'versions/{run_id}/'+str(p.relative_to(root)).replace('\\','/'),path_or_fileobj=str(p)) for p in paths]
 artifact=api.create_commit(repo_id=repo,repo_type='model',operations=operations,commit_message=f'Add immutable disease model run {run_id}')
 candidate['artifact_revision']=artifact.oid
 # Read pointer at the exact repo head and use parent_commit to prevent replacing a concurrent promotion.
 info=api.repo_info(repo_id=repo,repo_type='model');current=read_pointer(repo,revision=info.sha)
 accepted,reason=promotion_decision(candidate,current,config,allow_new_benchmark)
 if accepted:
  pointer=root/'deployment.json';pointer.write_text(json.dumps(candidate,ensure_ascii=False,indent=2))
  promoted=api.create_commit(repo_id=repo,repo_type='model',parent_commit=info.sha,operations=[CommitOperationAdd(path_in_repo='deployment.json',path_or_fileobj=str(pointer))],commit_message=f'Promote validated disease model {run_id}')
  candidate['pointer_commit']=promoted.oid
 result={'run_id':run_id,'promoted':accepted,'reason':reason,'artifact_revision':artifact.oid,'validation_macro_f1':candidate['validation_macro_f1']}
 (root/'publication.json').write_text(json.dumps(result,indent=2));return result

def notify_render():
 hook=os.environ.get('RENDER_DEPLOY_HOOK')
 if not hook:return {'requested':False,'reason':'hook_not_configured; proxy refreshes model pointer automatically'}
 # Do not print the secret hook URL or server response bodies.
 from urllib.parse import urlparse
 parsed=urlparse(hook)
 if parsed.scheme!='https' or parsed.hostname!='api.render.com':raise ValueError('RENDER_DEPLOY_HOOK must be an HTTPS Render API URL')
 try:
  with urllib.request.urlopen(urllib.request.Request(hook,method='POST'),timeout=30) as response:return {'requested':True,'status':response.status}
 except Exception:return {'requested':False,'reason':'deploy_hook_failed; model promotion is retained and notification can be retried'}
