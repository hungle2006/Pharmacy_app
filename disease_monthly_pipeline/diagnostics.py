"""Aggregate-only custom evaluation. Never upload patient text or tune on test."""
import collections
import numpy as np
from sklearn.metrics import accuracy_score,f1_score,balanced_accuracy_score

def metrics(y,p):
 return {'n':len(y),'accuracy':float(accuracy_score(y,p)),'macro_f1':float(f1_score(y,p,labels=np.unique(y),average='macro',zero_division=0)),'balanced_accuracy':float(balanced_accuracy_score(y,p))}
def evaluate(logits,truth,metadata,train_counts,id2label,majority_label):
 logits=np.asarray(logits);truth=np.asarray(truth);prediction=logits.argmax(1)
 assert len(truth)==len(metadata)==len(logits)
 shifted=logits-logits.max(1,keepdims=True);prob=np.exp(shifted);prob/=prob.sum(1,keepdims=True);confidence=prob.max(1)
 correct=prediction==truth;bins=[];ece=0
 for i in range(10):
  selected=(confidence>=i/10)&(confidence<(i+1)/10 if i<9 else confidence<=1)
  if selected.any():
   acc=float(correct[selected].mean());conf=float(confidence[selected].mean());n=int(selected.sum());ece+=n/len(truth)*abs(acc-conf);bins.append({'lower':i/10,'upper':(i+1)/10,'n':n,'accuracy':acc,'confidence':conf})
 def slices(field):
  groups=collections.defaultdict(list)
  for i,r in enumerate(metadata):groups[str(r.get(field) or 'unknown')].append(i)
  return {k:metrics(truth[v],prediction[v]) for k,v in groups.items()}
 buckets=collections.defaultdict(list)
 for i,label in enumerate(truth):
  n=train_counts[int(label)];key='train_under_20' if n<20 else 'train_20_to_49' if n<50 else 'train_50_or_more';buckets[key].append(i)
 confusion=collections.Counter((int(a),int(b)) for a,b in zip(truth,prediction) if a!=b)
 absent=[id2label[int(i)] for i in np.unique(truth) if not np.any((truth==i)&correct)]
 return {'overall':metrics(truth,prediction),'majority_train_baseline_accuracy':float(np.mean(truth==majority_label)),'by_language':slices('language'),'by_source_kind':slices('source_kind'),'by_train_support':{k:metrics(truth[v],prediction[v]) for k,v in buckets.items()},'zero_recall_labels':absent,'top_confusions':[{'true':id2label[a],'predicted':id2label[b],'count':n} for (a,b),n in confusion.most_common(50)],'uncalibrated_ece_10bins':ece,'calibration_bins':bins,'note':'Slice macro-F1 uses labels observed in that slice. Confidence is uncalibrated. No source-held-out or clinical generalization claim follows from same-source test scores.'}
