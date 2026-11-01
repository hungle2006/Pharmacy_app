import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pytest
from balancing import class_weights,coverage,make_loss
from ddxplus import render,import_cases

def test_balanced_weights_equalize_train_mass_without_resampling():
 ids=[0]*8+[1]*145
 weights,report=class_weights(ids,2)
 assert np.allclose(weights*np.array([8,145]),len(ids)/2)
 assert np.isclose(np.mean(weights[ids]),1)
 assert report['weighted_train_mass_ratio']==pytest.approx(1)
 assert class_weights(ids,2,'none')[0].tolist()==[1,1]
 with pytest.raises(ValueError):class_weights([0],2)

def evidence_fixture():
 return {
 'A':{'is_antecedent':False,'data_type':'B','question_en':'Do you feel shivering and chills?','default_value':0},
 'B':{'is_antecedent':False,'data_type':'B','question_en':'Are you sweating through clothing at night?','default_value':0},
 'C':{'is_antecedent':False,'data_type':'B','question_en':'Is your appetite much lower than usual?','default_value':0},
 'H':{'is_antecedent':True,'data_type':'B','question_en':'Have you already been diagnosed with TARGET?','default_value':0},
 'D':{'is_antecedent':False,'data_type':'C','question_en':'What color are the spots?','default_value':'V0','value_meaning':{'V0':{'en':'NA'},'V1':{'en':'red'}}},
 'N':{'is_antecedent':False,'data_type':'C','question_en':'Undocumented pain scale?','default_value':0,'value_meaning':{}}}

def source_fixture():
 return {'label_map':{'Source condition':'Nhãn chuẩn'},'max_per_label':2,'max_rows_scanned':20,'files':{'train':{'id':123,'sha256':'pinned'}},'notice':'fixture','license_url':'https://example.org/license'}

def test_render_preserves_values_and_omits_antecedents_defaults_unanchored_scales():
 text,fingerprint,n=render("['A','B','C','H','D_@_V0','N_@_3']",evidence_fixture())
 assert n==3 and 'TARGET' not in text and 'scale' not in text and 'color' not in text
 assert render("['A','B','C','D_@_V1']",evidence_fixture())[0].endswith('red.')
 assert render("['C','B','A']",evidence_fixture())[1]==fingerprint
 with pytest.raises(ValueError):render("['UNKNOWN']",evidence_fixture())

def test_ddx_only_pathology_used_and_demographic_variants_not_counted():
 base=[{'text':'A distinct existing narrative from a frozen holdout record','label':'Nhãn chuẩn','label_id':0,'group_id':'held','split':'test'}]
 case={'PATHOLOGY':'Source condition','EVIDENCES':"['A','B','C']",'AGE':'18','DIFFERENTIAL_DIAGNOSIS':'NEVER COPY THIS DIAGNOSIS'}
 cases=[case,{**case,'AGE':'65'},{**case,'PATHOLOGY':'unmapped subtype'}]
 base.append({'text':'An independent original training observation with an unrelated symptom pattern','label':'Nhãn chuẩn','label_id':0,'group_id':'training','split':'train'})
 original=copy.deepcopy(base)
 result,report=import_cases(base,source_fixture(),cases,evidence_fixture())
 assert base==original and result[0]==original[0]
 assert len(result)==3 and report['accepted']==1
 assert result[2]['split']=='train' and result[2]['source_kind']=='synthetic_structured_evidence'
 assert 'DIAGNOSIS' not in result[2]['text'] and '18' not in result[2]['text'] and '65' not in result[2]['text']
 result2,report2=import_cases(result,source_fixture(),cases,evidence_fixture())
 assert result2==result and report2['accepted']==0

def test_ddx_holdout_duplicates_rejected_and_target_not_overshot():
 text=render("['A','B','C']",evidence_fixture())[0]
 base=[{'text':text,'label':'Nhãn chuẩn','label_id':0,'group_id':'held','split':'validation'},{'text':'Unrelated original training description about joint stiffness lasting several weeks','label':'Nhãn chuẩn','label_id':0,'group_id':'train','split':'train'}]
 result,report=import_cases(base,source_fixture(),[{'PATHOLOGY':'Source condition','EVIDENCES':"['A','B','C']"}],evidence_fixture())
 assert result==base and report['accepted']==0
 assert report['statistics']['duplicate_or_near_existing']==1

def test_weighted_gradient_accumulation_matches_full_effective_batch():
 torch=pytest.importorskip('torch')
 logits=torch.tensor([[2.,0.],[0.,1.],[1.,0.]],requires_grad=True)
 labels=torch.tensor([0,1,1]);loss=make_loss(np.array([3.,.5],dtype=np.float32))
 full=loss({'logits':logits},labels)
 grad=torch.autograd.grad(full,logits)[0]
 micro=loss({'logits':logits[:1]},labels[:1],num_items_in_batch=3)+loss({'logits':logits[1:]},labels[1:],num_items_in_batch=3)
 assert torch.allclose(full,micro)
 assert torch.allclose(grad,torch.autograd.grad(micro,logits)[0])
 # Weight cannot cancel out in a one-example microbatch.
 plain=torch.nn.functional.cross_entropy(logits[:1],labels[:1])
 assert torch.allclose(loss({'logits':logits[:1]},labels[:1]),3*plain)

def test_hf_trainer_compute_loss_api_smoke(tmp_path):
 torch=pytest.importorskip('torch');transformers=pytest.importorskip('transformers')
 from transformers.modeling_outputs import SequenceClassifierOutput
 class Tiny(torch.nn.Module):
  def __init__(self):super().__init__();self.layer=torch.nn.Linear(2,2)
  def forward(self,input_ids,labels=None):return SequenceClassifierOutput(logits=self.layer(input_ids.float()))
 data=[{'input_ids':torch.tensor([1.,0.]),'labels':torch.tensor(0)},{'input_ids':torch.tensor([0.,1.]),'labels':torch.tensor(1)}]*4
 model=Tiny();before=model.layer.weight.detach().clone()
 args=transformers.TrainingArguments(output_dir=str(tmp_path),max_steps=2,per_device_train_batch_size=2,gradient_accumulation_steps=2,use_cpu=True,save_strategy='no',report_to='none',disable_tqdm=True,optim='adamw_torch',learning_rate=.01)
 trainer=transformers.Trainer(model=model,args=args,train_dataset=data,compute_loss_func=make_loss([2.,.5]))
 result=trainer.train()
 assert result.global_step==2 and np.isfinite(result.training_loss)
 assert not torch.equal(before,model.layer.weight.detach())

def test_preparation_retains_source_metadata_without_changing_benchmark(tmp_path):
 import pyarrow as pa,pyarrow.parquet as pq
 from data_pipeline import prepare
 rows=[]
 for split in ['train','validation','test']:
  for idx,label in enumerate(['condition alpha','condition beta']):
   rows.append({'text':f'Unique symptom narrative and detailed history {split} individual {idx}','label':label,'language':'en','split':split,'group_id':split+str(idx),'source_kind':'synthetic_structured_evidence' if split=='train' else None,'source_url':'https://example.org/source','source_files':['https://example.org/source']})
 pq.write_table(pa.Table.from_pylist(rows),tmp_path/'input.parquet')
 a=prepare(tmp_path,['input.parquet'],tmp_path/'registry',tmp_path/'first')
 result=pq.read_table(tmp_path/'first/disease_train_ready.parquet').to_pylist()
 assert all(r['source_kind']=='synthetic_structured_evidence' for r in result if r['split']=='train')
 assert all(r['source_files']==['https://example.org/source'] for r in result)
 b=prepare(tmp_path,['input.parquet'],tmp_path/'registry',tmp_path/'second')
 assert a['benchmark_sha256']==b['benchmark_sha256']
