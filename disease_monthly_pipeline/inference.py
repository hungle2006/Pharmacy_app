"""Load only the promoted immutable safetensors artifact. Refresh pointer every 60 seconds."""
import time,threading,os,json
from pathlib import Path
from release import read_pointer,model_directory
_loaded=None;_last_check=0;_pointer=None;_lock=threading.Lock()
def predict_text(text,top_k=5):
 global _loaded,_last_check,_pointer
 if not isinstance(text,str) or not 5<=len(text.strip())<=4000:raise ValueError('text must contain 5 to 4000 characters')
 def config():return json.loads((Path(__file__).parent/'config.json').read_text())
 import torch
 from transformers import AutoTokenizer,AutoModelForSequenceClassification
 with _lock:
  now=time.monotonic();repo=config()['model_repo']
  if _pointer is None or now-_last_check>60:
   try:
    pointer=read_pointer(repo)
    if pointer is None:raise RuntimeError('No trained model has been promoted yet')
    if _loaded is None or pointer['artifact_revision']!=_pointer['artifact_revision']:
     path=model_directory(pointer,repo,cache=os.environ.get('MODEL_CACHE','/tmp/disease_hf_cache'))
     tokenizer=AutoTokenizer.from_pretrained(path,trust_remote_code=False)
     model=AutoModelForSequenceClassification.from_pretrained(path,trust_remote_code=False,use_safetensors=True);model.eval()
     _loaded=(tokenizer,model)
    _pointer=pointer;_last_check=now
   except Exception:
    if _loaded is None:raise
    # A failed refresh keeps serving the previously loaded immutable model, retry after 60 seconds.
    _last_check=now
  tokenizer,model=_loaded
  encoded=tokenizer(text,return_tensors='pt',truncation=True,max_length=_pointer['max_length'])
  with torch.no_grad():prob=model(**encoded).logits.softmax(-1)[0]
  scores,ids=prob.topk(min(max(1,int(top_k)),len(prob)))
  return {'model_run':_pointer['run_id'],'artifact_revision':_pointer['artifact_revision'],'predictions':[{'label':model.config.id2label[int(i)],'score':float(s)} for s,i in zip(scores,ids)],'score_type':'uncalibrated_softmax','scope':'research disease/condition labels; not clinical diagnoses'}
