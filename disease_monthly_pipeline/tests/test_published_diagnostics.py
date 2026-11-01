import sys,collections,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from published_sources import import_rows
from diagnostics import evaluate
import numpy as np

def test_source_original_test_and_existing_holdouts_never_become_train():
 rows=[{'text':'A distinct existing history with pain and fatigue lasting several days','label':'Sốt rét','label_id':0,'split':'test'}]
 text='I feel very cold and shiver each night with a fever and sweating all over my body.'
 source={'repo':'fixture','revision':'pinned','train_file':'train.jsonl','label_map':{'malaria':'Sốt rét'},'max_per_label':20,'kind':'published_synthetic','notice':'fixture'}
 imported=[{'input_text':text,'output_text':'malaria'},{'input_text':rows[0]['text'],'output_text':'malaria'},{'input_text':'I have malaria with fever and sweating and aches across my entire body.','output_text':'malaria'}]
 result,report=import_rows(rows,source,imported,[{'input_text':text}],target=100)
 assert result==rows and report['accepted']==0
 assert report['statistics']['near_original_source_test']==1
 assert report['statistics']['duplicate_or_near_existing']==1
 assert report['statistics']['target_name_in_input']==1

def test_source_cap_and_immutable_holdouts():
 source={'repo':'fixture','revision':'pinned','train_file':'train.jsonl','label_map':{'malaria':'Sốt rét'},'max_per_label':1,'kind':'published_synthetic','notice':'fixture'}
 rows=[{'text':'An unrelated initial sample in a frozen test split','label':'Sốt rét','label_id':0,'split':'test'}]
 candidates=[{'input_text':'I feel cold and shiver each night with fever and sweating all over my body.','output_text':'malaria'},{'input_text':'Yesterday I began feeling sick with repeated chills and very high body temperature.','output_text':'malaria'}]
 result,report=import_rows(rows,source,candidates,[])
 assert len(result)==2 and result[0]==rows[0] and result[1]['split']=='train'
 assert report['accepted']==1 and result[1]['source_kind']=='published_synthetic'

def test_custom_metrics_expose_language_gap_confusion_and_train_only_baseline():
 logits=np.array([[3.,0.],[2.,1.],[2.,1.],[0.,3.]])
 result=evaluate(logits,[0,1,1,1],[{'language':'vi'},{'language':'vi'},{'language':'en'},{'language':'en'}],{0:100,1:8},{0:'A',1:'B'},0)
 assert result['overall']['accuracy']==.5
 assert result['by_train_support']['train_under_20']['n']==3
 assert result['top_confusions'][0]=={'true':'B','predicted':'A','count':2}
 assert result['majority_train_baseline_accuracy']==.25
 assert result['uncalibrated_ece_10bins']>=0
 assert 'text' not in json.dumps(result)
