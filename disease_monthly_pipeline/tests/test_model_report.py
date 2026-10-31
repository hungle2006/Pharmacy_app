import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_report import public_report

def test_missing_checkpoint_is_explicit():
 assert public_report(None)=={'status':'not_trained'}

def test_only_promoted_numeric_scores_are_exposed():
 pointer={'run_id':'run-1','dataset_revision':'abc','benchmark_sha256':'xyz','metrics':{'best_checkpoint':'/private/path','test':{'test_accuracy':.8,'test_macro_f1':.7,'test_top5_accuracy':float('nan'),'test_balanced_accuracy':True},'validation':{'validation_macro_f1':.75}}}
 result=public_report(pointer)
 assert result['metrics']=={'validation':{'macro_f1':.75},'test':{'accuracy':.8,'macro_f1':.7}}
 assert 'private' not in str(result)

def test_report_endpoint_requires_key_and_uses_lightweight_modal_function(monkeypatch):
 from types import SimpleNamespace
 monkeypatch.setenv('API_KEY','test-only-key')
 monkeypatch.setenv('MODAL_TOKEN_ID','fixture')
 monkeypatch.setenv('MODAL_TOKEN_SECRET','fixture')
 monkeypatch.setenv('INFERENCE_BACKEND','modal')
 calls=[]
 async def remote():return {'status':'not_trained'}
 def function(app,name):
  calls.append(name)
  return SimpleNamespace(remote=SimpleNamespace(aio=remote))
 monkeypatch.setitem(sys.modules,'modal',SimpleNamespace(Function=SimpleNamespace(from_name=function)))
 from fastapi.testclient import TestClient
 from server import app
 with TestClient(app) as client:
  assert client.get('/report').status_code==401
  assert calls==[]
  result=client.get('/report',headers={'X-API-Key':'test-only-key'})
  assert result.status_code==200 and result.json()=={'status':'not_trained'}
  assert calls==['report']
