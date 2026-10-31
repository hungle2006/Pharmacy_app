"""Fine-tune a multilingual sequence classifier on the frozen prepared split.
No disease labels are generated and no test data selects checkpoints.
"""
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score,classification_report

def compute_metrics(pred):
 logits,truth=pred;logits=logits[0] if isinstance(logits,tuple) else logits
 order=np.argsort(logits,axis=1)[:,::-1];guess=order[:,0]
 return {'accuracy':float(accuracy_score(truth,guess)),'macro_f1':float(f1_score(truth,guess,average='macro',zero_division=0)),'balanced_accuracy':float(balanced_accuracy_score(truth,guess)),'top3_accuracy':float(np.mean(np.any(order[:,:min(3,logits.shape[1])]==truth[:,None],axis=1))),'top5_accuracy':float(np.mean(np.any(order[:,:min(5,logits.shape[1])]==truth[:,None],axis=1)))}
def main(argv=None,persist_checkpoint=None):
 p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path(__file__).parent/'data/disease_train_ready.parquet');p.add_argument('--model',default='FacebookAI/xlm-roberta-base');p.add_argument('--output',type=Path,default=Path('results/xlmr_disease'));p.add_argument('--epochs',type=float,default=3);p.add_argument('--batch-size',type=int,default=8);p.add_argument('--max-length',type=int,default=256);p.add_argument('--lr',type=float,default=2e-5);p.add_argument('--allow-cpu',action='store_true');p.add_argument('--max-steps',type=int,default=-1,help='Smoke/testing only; default -1 trains all epochs');a=p.parse_args(argv)
 import torch
 from datasets import Dataset,DatasetDict
 from transformers import AutoTokenizer,AutoModelForSequenceClassification,DataCollatorWithPadding,Trainer,TrainingArguments,EarlyStoppingCallback,TrainerCallback,set_seed
 from transformers.trainer_utils import get_last_checkpoint
 if not torch.cuda.is_available() and not a.allow_cpu:raise SystemExit('Không có GPU. Chạy trên Modal hoặc thêm --allow-cpu nếu chủ động dùng CPU.')
 if not a.data.is_file():raise SystemExit('Không thấy '+str(a.data))
 a.output.mkdir(parents=True,exist_ok=True);set_seed(42)
 report_path=a.data.parent/'preparation_report.json';sha=hashlib.sha256(a.data.read_bytes()).hexdigest()
 if report_path.exists():
  report=json.loads(report_path.read_text());assert sha==report['output_sha256'],'Dataset SHA256 mismatch'
 table=pq.read_table(a.data);df=table.to_pandas();required={'text','label','label_id','group_id','split'};assert required<=set(df)
 assert set(df['split'])=={'train','validation','test'}
 assert not df['text'].isna().any() and not df['label_id'].isna().any()
 memberships=df.groupby('group_id')['split'].nunique();assert memberships.max()==1,'Group leakage'
 id2label={int(i):str(l) for i,l in zip(df['label_id'],df['label'])};assert set(id2label)==set(range(len(id2label)))
 for s in ['train','validation','test']:assert set(df.loc[df['split']==s,'label_id'])==set(id2label),'Missing labels in split'
 run_config={'data_sha256':sha,'model':a.model,'labels':id2label,'max_length':a.max_length,'learning_rate':a.lr,'batch_size':a.batch_size,'epochs':a.epochs,'max_steps':a.max_steps,'seed':42}
 config_path=a.output/'run_config.json'
 if config_path.exists():
  old=json.loads(config_path.read_text());assert old==json.loads(json.dumps(run_config)),'Output belongs to a different data/model/training configuration; choose a new output directory'
 config_path.write_text(json.dumps(run_config,ensure_ascii=False,indent=2))
 data=DatasetDict({s:Dataset.from_dict({'text':df.loc[df['split']==s,'text'].tolist(),'labels':df.loc[df['split']==s,'label_id'].astype(int).tolist()}) for s in ['train','validation','test']})
 tokenizer=AutoTokenizer.from_pretrained(a.model,use_fast=True)
 encoded=data.map(lambda batch:tokenizer(batch['text'],truncation=True,max_length=a.max_length),batched=True,remove_columns=['text'])
 model=AutoModelForSequenceClassification.from_pretrained(a.model,num_labels=len(id2label),id2label=id2label,label2id={v:k for k,v in id2label.items()},ignore_mismatched_sizes=True)
 bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported()
 args=TrainingArguments(output_dir=str(a.output),learning_rate=a.lr,num_train_epochs=a.epochs,max_steps=a.max_steps,per_device_train_batch_size=a.batch_size,per_device_eval_batch_size=a.batch_size*2,gradient_accumulation_steps=2,weight_decay=.01,warmup_ratio=.06,eval_strategy='epoch',save_strategy='epoch',load_best_model_at_end=True,metric_for_best_model='macro_f1',greater_is_better=True,save_total_limit=2,logging_steps=100,report_to='none',seed=42,data_seed=42,bf16=bf16,fp16=torch.cuda.is_available() and not bf16,dataloader_num_workers=0,eval_accumulation_steps=20)
 class Persist(TrainerCallback):
  def on_save(self,args,state,control,**kwargs):
   if persist_checkpoint:persist_checkpoint()
 callbacks=[EarlyStoppingCallback(early_stopping_patience=2),Persist()]
 trainer=Trainer(model=model,args=args,train_dataset=encoded['train'],eval_dataset=encoded['validation'],processing_class=tokenizer,data_collator=DataCollatorWithPadding(tokenizer),compute_metrics=compute_metrics,callbacks=callbacks)
 checkpoint=get_last_checkpoint(str(a.output))
 trainer.train(resume_from_checkpoint=checkpoint)
 validation=trainer.evaluate(encoded['validation'],metric_key_prefix='validation');test=trainer.predict(encoded['test'],metric_key_prefix='test');metrics={'validation':validation,'test':test.metrics,'note':'Held-out same-source synthetic/template classification, not independently verified clinical diagnostic accuracy.','dataset_sha256':sha,'best_checkpoint':trainer.state.best_model_checkpoint}
 (a.output/'evaluation.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
 logits=test.predictions[0] if isinstance(test.predictions,tuple) else test.predictions
 perclass=classification_report(test.label_ids,np.argmax(logits,axis=1),labels=list(sorted(id2label)),target_names=[id2label[i] for i in sorted(id2label)],output_dict=True,zero_division=0)
 (a.output/'per_class_test.json').write_text(json.dumps(perclass,ensure_ascii=False,indent=2))
 trainer.save_model(str(a.output/'best_model'));tokenizer.save_pretrained(a.output/'best_model')
 (a.output/'export_complete.json').write_text(json.dumps({'data_sha256':sha,'complete':True}))
 if persist_checkpoint:persist_checkpoint()
 print(json.dumps(metrics,ensure_ascii=False,indent=2));return metrics
if __name__=='__main__':main()
