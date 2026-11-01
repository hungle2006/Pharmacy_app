import sys,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from web_collectors import extract,collect,refresh,TOOLS

HTML='''<main><h1>Condition reference</h1><h2>Symptoms</h2><ul><li>Persistent discomfort in the abdomen over several days</li><li>Repeated episodes of sweating at night and reduced appetite</li><li>Difficulty maintaining normal daily activities due to fatigue</li></ul><h2>Treatment</h2><p>Do not include this treatment or © external material.</p></main>'''
def source():
 return {'id':'cdc','enabled':True,'allowed_domains':['example.org'],'policy_status':'reviewed_institute_authored_text_only','policy_url':'https://example.org/policy','notice':'Fixture source only','pages':[{'url':'https://example.org/condition','title':'Condition reference','headings':['Symptoms'],'mode':'list','train_eligible':True,'label_aliases':['Bệnh A'],'disease_aliases':['condition alpha']}]}
def rows():
 return [{'text':f'Original independent symptom history from person {i} with distinct onset {split}','label':label,'label_id':i,'split':split,'group_id':label+split} for i,label in enumerate(['Bệnh A','Bệnh B']) for split in ['train','validation','test']]
def test_ten_registered_named_tools_match_ten_reviewed_sources():
 registry=json.loads((Path(__file__).resolve().parents[1]/'web_collectors.json').read_text())
 assert len(registry['sources'])==10 and {s['id'] for s in registry['sources']}==set(TOOLS)
 assert len({s['allowed_domains'][0] for s in registry['sources']})==10
 assert all(s['policy_url'] and s['notice'] for s in registry['sources'])
def test_extract_only_selected_section_and_reject_changed_title_or_rights():
 p=source()['pages'][0];text=extract(HTML,p)
 assert 'fatigue' in text and 'treatment' not in text and 'external' not in text
 with pytest.raises(ValueError,match='page_title_changed'):extract(HTML.replace('Condition reference','Other topic'),p)
 with pytest.raises(ValueError,match='third_party'):extract(HTML.replace('Persistent discomfort','© Copyright protected discomfort'),p)
def test_short_symptom_items_preserved_and_h1_stops_at_next_section():
 p=source()['pages'][0];p.update(headings=['Condition reference'])
 text=extract(HTML.replace('<h2>Symptoms</h2>',''),p)
 assert 'treatment' not in text and 'fatigue' in text
 p.update(headings=['Symptoms'])
 html=HTML.replace('Persistent discomfort in the abdomen over several days','Fatigue')
 assert extract(html,p).startswith('Fatigue')
def test_holdouts_unchanged_one_url_one_group_even_when_page_changes():
 initial=rows();original=copy.deepcopy(initial);reg={'sources':[source()]}
 result,docs,report=refresh(initial,reg,fetch=lambda _:HTML)
 assert initial==original and len(result)==len(initial)+1 and report['accepted_train']==1
 assert [r for r in result if r['split']!='train']==[r for r in initial if r['split']!='train']
 updated=HTML.replace('Persistent discomfort','Newly observed discomfort')
 again,newdocs,report2=refresh(result,reg,docs,fetch=lambda _:updated)
 assert again==result and report2['accepted_train']==0 and len(newdocs)==1
 assert newdocs[0]['text']!=docs[0]['text'] and newdocs[0]['training_status']=='already_ingested_page'
def test_ambiguous_labels_and_quota_do_not_block_reference_collection():
 s=source();s['pages'][0]['label_aliases']=['Bệnh A','Bệnh B']
 result,docs,report=refresh(rows(),{'sources':[s]},fetch=lambda _:HTML)
 assert result==rows() and len(docs)==1 and docs[0]['training_status']=='ambiguous_or_unknown_label'
 result,docs,report=refresh(rows(),{'sources':[source()]},target=1,fetch=lambda _:HTML)
 assert report['accepted_train']==0 and docs[0]['training_status']=='quota_reached'
def test_source_failure_isolated_and_previous_reference_retained():
 s=source();reg={'sources':[s]};_,docs,_=refresh(rows(),reg,fetch=lambda _:HTML)
 def failed(_):raise OSError('Untrusted URL or sensitive server message')
 result,again,report=refresh(rows(),reg,docs,fetch=failed)
 assert result==rows() and again==docs and report['sources_ok']==0
 assert report['sources'][0]['errors'][0]['reason']=='source_unavailable'
def test_existing_holdout_text_never_appended_and_unreviewed_domain_not_fetched():
 initial=rows();initial[1]['text']=extract(HTML,source()['pages'][0])
 result,docs,report=refresh(initial,{'sources':[source()]},fetch=lambda _:HTML)
 assert result==initial and docs[0]['training_status']=='duplicate_or_near_existing'
 s=source();s['pages'][0]['url']='https://localhost/private'
 docs,report=collect(s,lambda _:pytest.fail('Unsafe URL was fetched'))
 assert not docs and report['errors'][0]['error_type']=='ValueError'

def test_robots_disallow_prevents_page_fetch(monkeypatch):
 import web_collectors
 from types import SimpleNamespace
 calls=[]
 class Response:
  headers={'Content-Type':'text/plain'}
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def read(self,*args):return b'User-agent: *\nDisallow: /\n'
 def open_request(request,**kwargs):
  calls.append(request.full_url)
  assert request.full_url.endswith('/robots.txt')
  return Response()
 monkeypatch.setattr(web_collectors,'build_opener',lambda *a:SimpleNamespace(open=open_request))
 with pytest.raises(ValueError,match='robots_disallowed'):web_collectors.Fetcher(['example.org'])('https://example.org/condition')
 assert calls==['https://example.org/robots.txt']

def test_atomic_publication_writes_one_master_and_one_reference_catalog(tmp_path,monkeypatch):
 import types,pyarrow as pa,pyarrow.parquet as pq,huggingface_hub,enrichment,web_collectors
 initial=rows();master=tmp_path/'disease_train_ready.parquet';pq.write_table(pa.Table.from_pylist(initial),master)
 cfg={'enabled':True,'dataset_repo':'fixture/data','dataset_file':master.name,'published_sources_enabled':False,'ddxplus_enabled':False,'web_collectors_enabled':True,'target_train_per_label':100,'near_jaccard':.8,'max_pages_per_run':0,'max_labels_per_run':0,'max_review_items':10,'max_additions_per_run':10,'allowed_domains':['example.org'],'delay_seconds':1}
 for name,data in [('enrichment_config.json',cfg),('crawl_sources.json',{'sources':[]}),('web_collectors.json',{'sources':[source()]})]:(tmp_path/name).write_text(json.dumps(data))
 (tmp_path/'web_collectors.py').write_text('fixture extractor revision')
 (tmp_path/'SOURCE_NOTICES.md').write_text('Fixture attribution')
 paths={master.name:master};commits=[]
 class API:
  def repo_info(self,**kwargs):return types.SimpleNamespace(sha='pinned')
  def list_repo_files(self,*args,**kwargs):return list(paths)
  def create_commit(self,**kwargs):
   assert kwargs['parent_commit']=='pinned';commits.append(kwargs)
   for operation in kwargs['operations']:paths[operation.path_in_repo]=Path(operation.path_or_fileobj)
   return types.SimpleNamespace(oid='published')
 monkeypatch.setattr(enrichment,'ROOT',tmp_path)
 monkeypatch.setattr(huggingface_hub,'HfApi',API)
 monkeypatch.setattr(huggingface_hub,'hf_hub_download',lambda **kw:str(paths[kw['filename']]))
 monkeypatch.setattr(web_collectors,'Fetcher',lambda *a:lambda _:HTML)
 monkeypatch.delenv('FIRECRAWL_API_KEY',raising=False)
 result=enrichment.run(tmp_path/'work')
 assert result['rows_after']==7 and result['web_collectors']['sources_ok']==1
 assert [p for p in paths if p.endswith('.parquet')]==[master.name]
 assert {'medical_source_knowledge.jsonl','source_crawl_report.json','SOURCE_NOTICES.md'}<=set(paths)
 final=pq.read_table(paths[master.name]).to_pylist()
 assert [r['text'] for r in final if r['split']!='train']==[r['text'] for r in initial if r['split']!='train']
 assert len(paths['medical_source_knowledge.jsonl'].read_text().splitlines())==1
 assert enrichment.run(tmp_path/'work')['status']=='already_updated_this_month' and len(commits)==1
