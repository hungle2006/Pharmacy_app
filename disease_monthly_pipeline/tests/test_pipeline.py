import json,sys,types
from pathlib import Path
from types import SimpleNamespace
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from data_pipeline import prepare,snapshot_dataset,text_hash
from release import promotion_decision

def fixture_rows():
 rows=[]
 for split in ['train','validation','test']:
  for label in ['condition alpha','condition beta']:
   for i in range(2):
    text=f'patient reports persistent symptoms with detailed history {split} {label.split()[-1]} sample {i}'
    # Do not include the complete target name in the input.
    rows.append({'text':text,'label':label,'split':split,'language':'en','group_id':text_hash(text)})
 return rows

def write(path,rows):pq.write_table(pa.Table.from_pylist(rows),path)
def test_multi_shards_dedup_and_frozen_holdout(tmp_path):
 rows=fixture_rows();write(tmp_path/'part1.parquet',rows[:6]);write(tmp_path/'part2.parquet',rows[6:]+[rows[0]])
 first=prepare(tmp_path,['part1.parquet','part2.parquet'],tmp_path/'registry',tmp_path/'first')
 assert first['rows']==12 and first['statistics']['duplicate_occurrences_merged']==1
 # New same-class training record is admitted, unseen class is quarantined.
 extra=[{'text':'patient now describes a new combination of symptoms and onset yesterday','label':'condition alpha','language':'en'}, {'text':'patient reports several different newly observed symptoms and clinical history','label':'condition gamma','language':'en'}]
 write(tmp_path/'new.parquet',extra)
 second=prepare(tmp_path,['part1.parquet','part2.parquet','new.parquet'],tmp_path/'registry',tmp_path/'second')
 assert second['rows']==13 and second['splits']['train']==5
 assert first['benchmark_sha256']==second['benchmark_sha256']
 assert second['statistics']['new_class_rows_quarantined']==1

def test_near_holdout_and_group_id_never_become_train(tmp_path):
 rows=fixture_rows();write(tmp_path/'base.parquet',rows);prepare(tmp_path,['base.parquet'],tmp_path/'reg',tmp_path/'a')
 held=next(r for r in rows if r['split']=='test')
 new={'text':'patient presents with newly reported symptoms which require further history','label':held['label'],'language':'en','group_id':held['group_id']}
 write(tmp_path/'new.parquet',[new]);r=prepare(tmp_path,['base.parquet','new.parquet'],tmp_path/'reg',tmp_path/'b')
 assert r['rows']==12 and r['statistics']['new_or_heldout_related_rows_quarantined']==1

def test_conflicting_provided_holdout_rejected(tmp_path):
 rows=fixture_rows();bad=dict(rows[-1]);bad['label']='condition alpha';rows.append(bad);write(tmp_path/'bad.parquet',rows)
 with pytest.raises(ValueError,match='Conflicting'):prepare(tmp_path,['bad.parquet'],tmp_path/'reg',tmp_path/'out')

def test_historical_train_cannot_move_to_test(tmp_path):
 rows=fixture_rows();write(tmp_path/'base.parquet',rows);prepare(tmp_path,['base.parquet'],tmp_path/'reg',tmp_path/'a')
 moved=[dict(r) for r in rows];moved[0]['split']='test';write(tmp_path/'moved.parquet',moved)
 with pytest.raises(ValueError,match='Historical'):prepare(tmp_path,['moved.parquet'],tmp_path/'reg',tmp_path/'b')

def test_qa_not_fabricated_into_disease_labels(tmp_path):
 write(tmp_path/'base.parquet',fixture_rows());write(tmp_path/'qa.parquet',[{'question':'How should this medicine be stored safely?','answer':'Follow the label.'}])
 r=prepare(tmp_path,['base.parquet','qa.parquet'],tmp_path/'reg',tmp_path/'out')
 assert r['rows']==12 and r['statistics']['non_classification_rows_skipped']==1

def test_snapshot_pins_all_parquets_to_one_revision(tmp_path):
 write(tmp_path/'a.parquet',fixture_rows()[:1]);(tmp_path/'sub').mkdir();write(tmp_path/'sub/b.parquet',fixture_rows()[1:2]);calls=[]
 info=SimpleNamespace(sha='a'*40,siblings=[SimpleNamespace(rfilename=x) for x in ['a.parquet','sub/b.parquet','README.md']])
 api=SimpleNamespace(repo_info=lambda *a,**k:info)
 def download(**kwargs):calls.append(kwargs);return str(tmp_path)
 root,files,manifest=snapshot_dataset({'dataset_repo':'owner/data','parquet_patterns':['*.parquet','**/*.parquet']},tmp_path/'cache',api,download)
 assert len(calls)==1 and calls[0]['revision']=='a'*40
 assert files==['a.parquet','sub/b.parquet'] and len(manifest['files'])==2

def test_validation_only_promotion_guard():
 cfg={'minimum_validation_macro_f1':.2,'promotion_tolerance':0}
 incumbent={'benchmark_sha256':'x','validation_macro_f1':.5}
 assert promotion_decision({'benchmark_sha256':'x','validation_macro_f1':.49},incumbent,cfg)[0] is False
 assert promotion_decision({'benchmark_sha256':'x','validation_macro_f1':.51},incumbent,cfg)[0] is True
 assert promotion_decision({'benchmark_sha256':'y','validation_macro_f1':.99},incumbent,cfg)[0] is False
 assert promotion_decision({'benchmark_sha256':'y','validation_macro_f1':.99},incumbent,cfg,True)[0] is True
 assert promotion_decision({'benchmark_sha256':'x','validation_macro_f1':float('nan')},incumbent,cfg)[0] is False

def test_render_api_auth_and_proxy(monkeypatch):
 monkeypatch.setenv('API_KEY','local-test-key');monkeypatch.setenv('MODAL_TOKEN_ID','test');monkeypatch.setenv('MODAL_TOKEN_SECRET','test');monkeypatch.setenv('INFERENCE_BACKEND','modal')
 async def remote(text,top_k):return {'model_run':'fixture','predictions':[{'label':'fixture','score':.5}]}
 fake=SimpleNamespace(Function=SimpleNamespace(from_name=lambda *a:SimpleNamespace(remote=SimpleNamespace(aio=remote))))
 monkeypatch.setitem(sys.modules,'modal',fake)
 from fastapi.testclient import TestClient
 from server import app
 with TestClient(app) as c:
  assert c.get('/health').status_code==200
  assert c.post('/predict',json={'text':'symptom description'}).status_code==401
  r=c.post('/predict',json={'text':'symptom description'},headers={'X-API-Key':'local-test-key'})
  assert r.status_code==200 and r.json()['model_run']=='fixture'
  assert c.post('/predict',json={'text':'hi'},headers={'X-API-Key':'local-test-key'}).status_code==422

def test_publish_artifact_before_atomic_pointer_and_exclude_pickle(tmp_path,monkeypatch):
 import release
 (tmp_path/'best_model').mkdir()
 from safetensors.numpy import save_file
 import numpy as np
 from tokenizers import Tokenizer,models
 save_file({'classifier.weight':np.zeros((2,4),dtype=np.float32)},str(tmp_path/'best_model/model.safetensors'))
 Tokenizer(models.WordLevel({'[UNK]':0},unk_token='[UNK]')).save(str(tmp_path/'best_model/tokenizer.json'))
 (tmp_path/'best_model/config.json').write_text(json.dumps({'id2label':{'0':'alpha','1':'beta'}}))
 (tmp_path/'export_complete.json').write_text('{}')
 (tmp_path/'best_model/training_args.bin').write_bytes(b'not-for-inference')
 for n in ['per_class_test.json','preparation_report.json']:(tmp_path/n).write_text('{}')
 (tmp_path/'evaluation.json').write_text(json.dumps({'validation':{'validation_macro_f1':.5},'test':{'test_macro_f1':.4}}))
 calls=[]
 class API:
  def create_commit(self,**kw):calls.append(kw);return SimpleNamespace(oid='a'*40 if len(calls)==1 else 'b'*40)
  def repo_info(self,**kw):return SimpleNamespace(sha='c'*40)
 monkeypatch.setattr(release,'read_pointer',lambda *a,**k:None)
 cfg={'model_repo':'owner/model','max_length':256,'minimum_validation_macro_f1':0,'promotion_tolerance':0}
 r=release.publish(cfg,'run-fixture',tmp_path,{'benchmark_sha256':'bench'},{'dataset_revision':'data','data_fingerprint':'fp'},api=API())
 assert r['promoted'] and len(calls)==2
 assert all(x.path_in_repo.startswith('versions/') for x in calls[0]['operations'])
 assert not any(x.path_in_repo.endswith('.bin') for x in calls[0]['operations'])
 assert calls[1]['parent_commit']=='c'*40
 pointer=json.loads((tmp_path/'deployment.json').read_text())
 assert pointer['artifact_revision']=='a'*40
