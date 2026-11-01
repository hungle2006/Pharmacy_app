import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from enrichment import enrich,extract,canonical,Duplicates
import pytest

HTML='''<main><h1>Signs and Symptoms of Cholera</h1><h2>Early symptoms</h2><figure>© third-party photo, excluded</figure><ul><li>Watery diarrhea, sometimes described as rice-water stools because they are milky white</li><li>Vomiting and painful muscle cramps</li><li>Restlessness or irritability</li></ul><h2>Treatment</h2><p>Not part of input</p></main>'''
def fixture():
 import json
 root=Path(__file__).resolve().parents[1]
 config=json.loads((root/'enrichment_config.json').read_text());registry=json.loads((root/'crawl_sources.json').read_text());registry['sources']=registry['sources'][:1];config['published_sources_enabled']=False
 rows=[{'text':f'unique existing observation {i} and distinct symptom history','label':'Tả','label_id':0,'split':s,'group_id':s,'record_id':str(i),'source_files':['old'],'language':'vi'} for i,s in enumerate(['train','validation','test'])]
 return rows,config,registry
def test_extract_only_verbatim_symptom_list_not_caption_or_treatment():
 rows,c,r=fixture();text,error=extract(HTML,r['sources'][0]);assert error is None
 assert 'third-party' not in text and 'Treatment' not in text and 'Watery diarrhea' in text
def test_add_once_to_train_and_keep_holdouts_exact():
 rows,c,r=fixture();original=copy.deepcopy(rows)
 final,state,report=enrich(rows,c,r,lambda u:HTML,search=lambda *a:[])
 assert rows==original and final[:3]==original and len(final)==4
 assert final[-1]['label_id']==0 and final[-1]['split']=='train' and final[-1]['source_kind']=='knowledge_symptom_excerpt'
 repeated,_,_=enrich(final,c,r,lambda u:pytest.fail('page already ingested'),state,search=lambda *a:[])
 assert repeated==final and report['added_by_label']=={'Tả':1}
def test_wrong_title_and_named_target_fail_closed():
 rows,c,r=fixture()
 assert extract(HTML.replace('Signs and Symptoms of Cholera','Wrong title'),r['sources'][0])[1]=='page_title_changed'
 assert extract(HTML.replace('Vomiting and','Cholera vomiting and'),r['sources'][0])[1]=='target_name_in_input'
def test_exact_and_near_duplicates_include_holdouts_and_other_labels():
 rows,c,r=fixture();text,_=extract(HTML,r['sources'][0]);rows[2]['text']=text
 final,_,report=enrich(rows,c,r,lambda u:HTML,search=lambda *a:[])
 assert final==rows and report['statistics']['duplicate_or_near_duplicate']==1
 dup=Duplicates([{'text':'alpha beta gamma delta epsilon zeta eta theta'}],.5)
 assert dup.contains('alpha beta gamma delta epsilon zeta eta iota')
def test_no_quota_no_download_and_no_manufactured_balancing():
 rows,c,r=fixture();c['target_train_per_label']=1
 final,_,report=enrich(rows,c,r,lambda u:pytest.fail('quota met'),search=lambda *a:[])
 assert final==rows and not report['added_by_label']
def test_ambiguous_labels_and_unreviewed_rights_not_ingested():
 rows,c,r=fixture();rows.append({**rows[0],'label':'Cholera','label_id':1})
 final,_,report=enrich(rows,c,r,lambda u:pytest.fail('ambiguous label'),search=lambda *a:[])
 assert final==rows and report['statistics']['ambiguous_or_unknown_source_label']==1
 rows,c,r=fixture();r['sources'][0]['reuse_status']='unknown'
 assert enrich(rows,c,r,lambda u:pytest.fail('unreviewed rights'),search=lambda *a:[])[0]==rows
def test_discovery_is_metadata_queue_never_training_data():
 rows,c,r=fixture();r['sources']=[]
 final,state,_=enrich(rows,c,r,lambda u:'',search=lambda l,c:[{'label':l,'url':'https://www.cdc.gov/example','title':'Search result','reason':'review'}])
 assert final==rows and len(state['review'])==1
def test_unsafe_urls_rejected():
 for url in ['http://www.cdc.gov/x','https://www.cdc.gov.evil.test/x','https://localhost/x','https://www.cdc.gov:444/x','https://user:pw@www.cdc.gov/x']:
  with pytest.raises(ValueError):canonical(url,['www.cdc.gov'])

def test_atomic_single_file_upload_preserves_provenance_and_repeated_run_skips(tmp_path,monkeypatch):
 import json,types,huggingface_hub,pyarrow as pa,pyarrow.parquet as pq,enrichment
 rows,c,r=fixture()
 for i,s in enumerate(['train','validation','test']):rows.append({**rows[i],'label':'Other label','label_id':1,'record_id':'other'+str(i),'text':'An entirely different clinical description '+str(i),'group_id':'other'+s})
 (tmp_path/'enrichment_config.json').write_text(json.dumps(c));(tmp_path/'crawl_sources.json').write_text(json.dumps(r));monkeypatch.setattr(enrichment,'ROOT',tmp_path)
 master=tmp_path/c['dataset_file'];pq.write_table(pa.Table.from_pylist(rows),master)
 paths={c['dataset_file']:master};calls=[];conflict=[True]
 class API:
  def repo_info(self,**kw):return types.SimpleNamespace(sha='pinned-head')
  def list_repo_files(self,*a,**kw):return list(paths)
  def create_commit(self,**kw):
   assert kw['parent_commit']=='pinned-head'
   if conflict[0]:raise RuntimeError('repo head changed')
   calls.append(kw)
   for operation in kw['operations']:paths[operation.path_in_repo]=Path(operation.path_or_fileobj)
   return types.SimpleNamespace(oid='new-commit')
 monkeypatch.setattr(huggingface_hub,'HfApi',API)
 monkeypatch.setattr(huggingface_hub,'hf_hub_download',lambda **kw:str(paths[kw['filename']]))
 monkeypatch.setattr(enrichment,'Fetcher',lambda c:lambda u:HTML)
 monkeypatch.delenv('FIRECRAWL_API_KEY',raising=False)
 with pytest.raises(RuntimeError,match='repo head changed'):enrichment.run(tmp_path/'work')
 assert len(calls)==0 and pq.read_table(master).num_rows==6
 conflict[0]=False
 result=enrichment.run(tmp_path/'work')
 assert result['rows_after']==7 and len(calls)==1
 uploaded=pq.read_table(paths[c['dataset_file']]).to_pylist()
 assert uploaded[-1]['source_kind']=='knowledge_symptom_excerpt'
 assert [x['text'] for x in uploaded if x['split']!='train']==[x['text'] for x in rows if x['split']!='train']
 assert enrichment.run(tmp_path/'work')['status']=='already_updated_this_month' and len(calls)==1
