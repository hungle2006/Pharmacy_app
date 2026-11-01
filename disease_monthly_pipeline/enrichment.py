"""Bounded source-backed enrichment. One master Parquet, frozen holdouts, atomic HF commit.

Discovery never equals approval. Only reviewed page/label/rights mappings can add
verbatim symptom lists; other results enter a bounded metadata-only review queue.
"""
from pathlib import Path
import collections, hashlib, json, os, re, time, unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).parent
BOT='PharmacyResearchBot/1.0'
def norm(text):
 return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(text)).casefold()).strip()
def digest(text):return hashlib.sha256(norm(text).encode()).hexdigest()
def canonical(url,domains):
 p=urlsplit(url)
 if p.scheme!='https' or p.hostname not in domains or p.username or p.password or p.port or p.query:raise ValueError('URL outside configured public source allowlist')
 return urlunsplit(('https',p.hostname,p.path or '/','',''))
def tokens(text):
 words=re.findall(r'\w+',norm(text));return {' '.join(words[i:i+3]) for i in range(max(0,len(words)-2))}
class Duplicates:
 """Exact hashes plus an exhaustive-overlap candidate index for trigram Jaccard.
 No SimHash collision assumption: every qualifying Jaccard pair shares a trigram.
 """
 def __init__(self,rows,threshold=.8):
  self.exact=set();self.index=collections.defaultdict(set);self.features=[];self.threshold=threshold
  for r in rows:self.add(r['text'])
 def add(self,text):
  self.exact.add(digest(text));s=tokens(text);i=len(self.features);self.features.append(s)
  for t in s:self.index[t].add(i)
 def contains(self,text):
  if digest(text) in self.exact:return True
  s=tokens(text)
  if not s:return True
  overlap=collections.Counter(i for t in s for i in self.index.get(t,()))
  return any(n/(len(s)+len(self.features[i])-n)>=self.threshold for i,n in overlap.items())
def deficits(rows,target):
 labels={r['label'] for r in rows};counts=collections.Counter(r['label'] for r in rows if r['split']=='train')
 return sorted([{'label':l,'train':counts[l],'missing':max(0,target-counts[l])} for l in labels],key=lambda r:(-r['missing'],r['label']))
def resolve_label(source,rows):
 labels={r['label'] for r in rows};matches=[l for l in labels if norm(l) in {norm(a) for a in source['label_aliases']}]
 # Multiple aliases present as separate classes require taxonomy review, never merge silently.
 return matches[0] if len(matches)==1 else None
def extract(html,source):
 from bs4 import BeautifulSoup
 soup=BeautifulSoup(html,'html.parser');h1=soup.find('h1')
 if not h1 or norm(h1.get_text(' ',strip=True))!=norm(source['page_title']):return None,'page_title_changed'
 main=soup.find('main') or soup
 blocks=[]
 for h in main.find_all(re.compile('^h[2-4]$')):
  if norm(h.get_text(' ',strip=True)) not in {norm(x) for x in source['section_headings']}:continue
  for node in h.next_elements:
   if node is h:continue
   if getattr(node,'name',None) and re.match('h[1-4]$',node.name):break
   if getattr(node,'name',None)=='ul':
    for li in node.find_all('li',recursive=False):
     t=li.get_text(' ',strip=True)
     if re.search(r'©|copyright|all rights reserved|https?://|@',t,re.I):return None,'rights_or_contact_in_excerpt'
     blocks.append(t)
    break
 text='\n'.join(blocks)
 if len(text)<80 or len(text)>1800 or len(text.split())<15:return None,'insufficient_symptom_text'
 for alias in source['disease_aliases']:
  if re.search(r'(?<!\w)'+re.escape(norm(alias))+r'(?!\w)',norm(text)):return None,'target_name_in_input'
 return text,None
class Fetcher:
 def __init__(self,config):self.config=config;self.robots={};self.last=0
 def __call__(self,url):
  url=canonical(url,self.config['allowed_domains']);host=urlsplit(url).netloc
  domains=self.config['allowed_domains']
  class Redirect(HTTPRedirectHandler):
   def redirect_request(self,req,fp,code,msg,headers,newurl):
    canonical(newurl,domains)
    return super().redirect_request(req,fp,code,msg,headers,newurl)
  opener=build_opener(Redirect())
  def read(u):
   with opener.open(Request(u,headers={'User-Agent':BOT}),timeout=25) as r:
    if 'text/' not in r.headers.get('Content-Type',''):raise ValueError('Not a text document')
    b=r.read(3_000_001)
    if len(b)>3_000_000:raise ValueError('Source too large')
    return b.decode('utf-8','replace')
  if host not in self.robots:
   robot=RobotFileParser();robot.parse(read('https://'+host+'/robots.txt').splitlines());self.robots[host]=robot
  robot=self.robots[host]
  if not robot.can_fetch(BOT,url):raise ValueError('robots_disallowed')
  delay=max(self.config['delay_seconds'],robot.crawl_delay(BOT) or robot.crawl_delay('*') or 0)
  time.sleep(min(60,max(0,delay-(time.monotonic()-self.last))))
  if delay>60:raise ValueError('Source crawl delay exceeds run budget')
  self.last=time.monotonic();return read(url)
def discover(label,config):
 key=os.getenv('FIRECRAWL_API_KEY')
 if not key:return []
 # Titles/excerpts are discovery evidence only; neither is training text.
 payload={'query':label+' triệu chứng symptoms '+' OR '.join('site:'+d for d in config['allowed_domains']),'limit':config['search_results_per_label']}
 req=Request('https://api.firecrawl.dev/v2/search',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urlopen(req,timeout=30) as r:d=json.load(r)
 data=d.get('data',{});items=data.get('web',[]) if isinstance(data,dict) else data
 return [{'label':label,'url':canonical(x['url'],config['allowed_domains']),'title':str(x.get('title',''))[:250],'reason':'needs_page_label_and_reuse_review'} for x in items if urlsplit(x.get('url','')).hostname in config['allowed_domains']]
def enrich(rows,config,registry,fetch,state=None,search=discover):
 deadline=time.monotonic()+config.get('max_duration_seconds',1200)
 state=state or {};pages=dict(state.get('pages',{}));review=list(state.get('review',[]));stats=collections.Counter();before=deficits(rows,config['target_train_per_label']);quota={x['label']:x['missing'] for x in before}
 labels={r['label']:r['label_id'] for r in rows};groups={r['group_id'] for r in rows};out=list(rows);dupes=None;added=collections.Counter()
 requested={r['label'] for r in before if r['missing']>0}
 for source in registry['sources'][:config['max_pages_per_run']]:
  if time.monotonic()>deadline:stats['time_budget_exhausted']+=1;break
  label=resolve_label(source,rows)
  if label is None:stats['ambiguous_or_unknown_source_label']+=1;continue
  if label not in requested or added[label]>=quota[label]:continue
  if source.get('reuse_status')!='reviewed_cdc_authored_text_only' or source.get('label_status')!='source_disease_page':stats['unreviewed_sources_skipped']+=1;continue
  url=canonical(source['url'],config['allowed_domains']);group='web:'+digest(url)
  # A source page is one independent group, even after content edits or new months.
  if group in groups:stats['already_ingested_page']+=1;continue
  try:html=fetch(url);text,reason=extract(html,source)
  except Exception as e:stats['fetch_failed']+=1;review.append({'label':label,'url':url,'reason':'fetch_failed:'+type(e).__name__});continue
  if reason:
   stats[reason]+=1;review.append({'label':label,'url':url,'reason':reason});continue
  if dupes is None:dupes=Duplicates(rows,config['near_jaccard'])
  if dupes.contains(text):stats['duplicate_or_near_duplicate']+=1;continue
  # Existing cleaner also rejects disease-name leakage; check before writing the master.
  if re.search(r'(?<!\w)'+re.escape(norm(label))+r'(?!\w)',norm(text)):stats['target_name_in_input']+=1;continue
  r={'record_id':digest(text),'text':text,'label':label,'label_id':labels[label],'language':source['language'],'source_files':[url],'group_id':group,'split':'train','source_url':url,'source_kind':source['kind'],'source_sha256':hashlib.sha256(html.encode()).hexdigest(),'retrieved_at':datetime.now(timezone.utc).isoformat(),'label_method':'reviewed_exact_page_mapping','reuse_notice':registry['reuse_notice'],'reuse_policy_url':registry['policy_url']}
  out.append(r);dupes.add(text);groups.add(group);added[label]+=1;stats['accepted']+=1;pages[url]={'sha256':r['source_sha256'],'record_id':r['record_id']}
  if stats['accepted']>=config['max_additions_per_run']:break
 for item in before[:config['max_labels_per_run']]:
  if time.monotonic()>deadline:stats['time_budget_exhausted']+=1;break
  if not item['missing']:continue
  try:review.extend(search(item['label'],config))
  except Exception:stats['discovery_failed']+=1
 unique={(r['label'],r['url']):r for r in review};review=list(unique.values())[-config['max_review_items']:]
 assert [r for r in out if r['split']!='train']==[r for r in rows if r['split']!='train'],'Holdout modified'
 report={'status':'completed','period':datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y-%m'),'statistics':dict(stats),'before':before,'after':deficits(out,config['target_train_per_label']),'added_by_label':dict(added),'discovery_enabled':bool(os.getenv('FIRECRAWL_API_KEY')),'note':'Quotas are goals, not fabricated observations. Knowledge excerpts are not patient cases; semantic and cross-language duplicate checks remain incomplete.'}
 return out,{'pages':pages,'review':review},report
def run(storage,publish=True):
 from huggingface_hub import HfApi,hf_hub_download,CommitOperationAdd
 config=json.loads((ROOT/'enrichment_config.json').read_text());registry=json.loads((ROOT/'crawl_sources.json').read_text())
 if not config['enabled']:return {'status':'disabled'}
 api=HfApi();repo=config['dataset_repo'];info=api.repo_info(repo_id=repo,repo_type='dataset');revision=info.sha
 # One canonical file only. Never delete other users' shards or silently mix copies.
 files=api.list_repo_files(repo,repo_type='dataset',revision=revision)
 if [p for p in files if p.endswith('.parquet')]!=[config['dataset_file']]:raise ValueError('Expected exactly one master Parquet; review shard consolidation first')
 def read(name):return Path(hf_hub_download(repo_id=repo,repo_type='dataset',revision=revision,filename=name))
 state=json.loads(read('enrichment_state.json').read_text()) if 'enrichment_state.json' in files else {}
 published=json.loads((ROOT/'published_sources.json').read_text()) if config.get('published_sources_enabled') else {'sources':[]}
 ddx=json.loads((ROOT/'ddxplus_sources.json').read_text()) if config.get('ddxplus_enabled') else {'enabled':False}
 signature=hashlib.sha256(json.dumps([config,registry,published,ddx],sort_keys=True).encode()).hexdigest();period=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%Y-%m')
 if state.get('period')==period and state.get('config_signature')==signature and state.get('last_master_sha256')==hashlib.sha256(read(config['dataset_file']).read_bytes()).hexdigest():return {'status':'already_updated_this_month'}
 table=pq.read_table(read(config['dataset_file']));rows=table.to_pylist()
 final,newstate,report=enrich(rows,config,registry,Fetcher(config),state)
 if published['sources']:
  from published_sources import refresh
  final,source_reports=refresh(final,published,config['target_train_per_label'],config['near_jaccard'])
  report['published_sources']=source_reports
  for item in source_reports:
   for label,count in item['added_by_label'].items():report['added_by_label'][label]=report['added_by_label'].get(label,0)+count
  report['after']=deficits(final,config['target_train_per_label'])
 if ddx.get('enabled'):
  from ddxplus import refresh as refresh_ddx
  final,ddx_report=refresh_ddx(final,ddx,Path(storage)/'source_cache',config['target_train_per_label'],config['near_jaccard'])
  report['ddxplus']=ddx_report
  for label,count in ddx_report['added_by_label'].items():report['added_by_label'][label]=report['added_by_label'].get(label,0)+count
  report['after']=deficits(final,config['target_train_per_label'])
 from balancing import coverage
 report['balance_before']=coverage(rows,config['target_train_per_label'])
 report['balance_after']=coverage(final,config['target_train_per_label'])
 work=Path(storage)/'enrichment';work.mkdir(parents=True,exist_ok=True);path=work/config['dataset_file']
 # Explicit schema union keeps provenance fields on newly added rows and original Arrow types.
 schema=table.schema
 for name in ['source_url','source_kind','source_sha256','retrieved_at','label_method','reuse_notice','reuse_policy_url']:
  if name not in schema.names:schema=schema.append(pa.field(name,pa.string()))
 pq.write_table(pa.Table.from_pylist(final,schema=schema),path,compression='zstd')
 from data_pipeline import validate
 validate(final)
 if len(final)==len(rows):
  import shutil
  shutil.copyfile(read(config['dataset_file']),path)
 newstate.update(period=period if not report['statistics'].get('fetch_failed') else None,config_signature=signature,last_master_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 report.update(dataset_revision_before=revision,rows_before=len(rows),rows_after=len(final))
 for name,value in [('enrichment_state.json',newstate),('enrichment_report.json',report)]:
  (work/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
 # Repeated names replace the HEAD file atomically; HF retains history, not extra train shards.
 if publish:
  ops=[CommitOperationAdd(path_in_repo=name,path_or_fileobj=str(work/name)) for name in [config['dataset_file'],'enrichment_state.json','enrichment_report.json']]
  if published['sources']:ops.append(CommitOperationAdd(path_in_repo='SOURCE_NOTICES.md',path_or_fileobj=str(ROOT/'SOURCE_NOTICES.md')))
  commit=api.create_commit(repo_id=repo,repo_type='dataset',parent_commit=revision,operations=ops,commit_message='Update reviewed disease train data '+period)
  report['commit']=commit.oid
 return report
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--output',default='./enrichment-work');p.add_argument('--publish',action='store_true');a=p.parse_args();r=run(a.output,publish=a.publish)
 print(json.dumps({k:r[k] for k in ['status','statistics','rows_before','rows_after','commit'] if k in r}))
