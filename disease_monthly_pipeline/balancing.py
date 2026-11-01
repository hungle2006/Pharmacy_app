"""Train-only class weights; no duplicate rows, no holdout resampling."""
import collections
import numpy as np

def class_weights(label_ids,num_labels,mode='balanced'):
 counts=np.bincount(np.asarray(label_ids,dtype=int),minlength=num_labels)
 if len(counts)!=num_labels or np.any(counts<=0):raise ValueError('Every class needs a positive TRAIN count')
 if mode not in {'none','balanced'}:raise ValueError('Unknown class weighting')
 weights=np.ones(num_labels,dtype=np.float32) if mode=='none' else (counts.sum()/(num_labels*counts)).astype(np.float32)
 return weights,{'mode':mode,'counts':counts.tolist(),'weights':weights.tolist(),'count_ratio_max_min':float(counts.max()/counts.min()),'weighted_train_mass_ratio':float((counts*weights).max()/(counts*weights).min()),'note':'TRAIN-only weights. Equal total loss mass is not additional independent observations.'}

def make_loss(weights):
 """Trainer compute_loss_func: weighted sum / effective batch item count.
 Fixed item denominator preserves weights even in single-class microbatches.
 """
 def loss(outputs,labels,num_items_in_batch=None):
  import torch
  logits=outputs['logits'] if isinstance(outputs,dict) else outputs.logits
  w=torch.as_tensor(weights,device=logits.device,dtype=torch.float32)
  total=torch.nn.functional.cross_entropy(logits.float(),labels,weight=w,reduction='sum')
  denominator=num_items_in_batch if num_items_in_batch is not None else labels.numel()
  return total/denominator
 return loss

def coverage(rows,target):
 counts=collections.Counter(r['label'] for r in rows if r['split']=='train');values=list(counts.values())
 return {'labels':len(counts),'train_rows':sum(values),'target_train_per_label':target,'labels_below_target':sum(n<target for n in values),'labels_under_20':sum(n<20 for n in values),'independent_rows_still_needed':sum(max(0,target-n) for n in values),'minimum_train':min(values),'maximum_train':max(values),'note':'Target is an acquisition quota, not proof of sufficient data or diagnostic performance.'}
