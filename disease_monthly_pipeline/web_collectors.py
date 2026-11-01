"""Ten bounded source collectors. Clinical reference excerpts are not patient cases.

Each source has independently reviewed URLs, title/section selectors and reuse terms.
Only explicit unambiguous mappings can append to TRAIN. A URL is one group forever.
"""
import collections,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.robotparser import RobotFileParser
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from enrichment import canonical,norm,digest,Duplicates,resolve_label

ROOT=Path(__file__).parent
BOT='PharmacyResearchCollector/1.0'

class Fetcher:
 def __init__(self,domains):self.domains=domains;self.robots={};self.last={}
 def __call__(self,url):
  canonical(url,self.domains);host=urlsplit(url).hostname;domains=self.domains
  class Redirect(HTTPRedirectHandler):
   def redirect_request(self,req,fp,code,msg,headers,newurl):
    canonical(newurl,domains)
    return super().redirect_request(req,fp,code,msg,headers,newurl)
  opener=build_opener(Redirect())
  def read(u):
   with opener.open(Request(u,headers={'User-Agent':BOT}),timeout=25) as response:
    if 'text/' not in response.headers.get('Content-Type',''):raise ValueError('non_text_response')
    data=response.read(3_000_001)
    if len(data)>3_000_000:raise ValueError('page_too_large')
    return data.decode('utf-8','replace')
  if host not in self.robots:
   robot=RobotFileParser()
   try:rules=read('https://'+host+'/robots.txt').splitlines()
   except HTTPError as error:
    if error.code not in {404,410}:raise
    rules=[]
   robot.parse(rules);self.robots[host]=robot
  robot=self.robots[host]
  if not robot.can_fetch(BOT,url):raise ValueError('robots_disallowed')
  delay=max(1,robot.crawl_delay(BOT) or robot.crawl_delay('*') or 0)
  if delay>60:raise ValueError('crawl_delay_exceeds_budget')
  time.sleep(max(0,delay-(time.monotonic()-self.last.get(host,0))))
  self.last[host]=time.monotonic();return read(url)

def extract(html,page):
 soup=BeautifulSoup(html,'html.parser')
 for node in soup.select('script,style,nav,footer,header,aside,figure,figcaption,sup,img,svg,video,form'):node.decompose()
 main=soup.find('main') or soup
 titles=[norm(h.get_text(' ',strip=True)) for h in main.find_all('h1')]
 if norm(page['title']) not in titles:raise ValueError('page_title_changed')
 headings=main.find_all(re.compile('^h[1-6]$'));blocks=[]
 for h in headings:
  if norm(h.get_text(' ',strip=True)) not in {norm(x) for x in page['headings']}:continue
  level=int(h.name[1]);stop_level=max(level,2)
  for node in h.next_elements:
   if getattr(node,'name',None) and re.match('h[1-6]$',node.name) and int(node.name[1])<=stop_level:break
   kind=getattr(node,'name',None)
   if (page['mode']=='list' and kind=='li' and not node.find_parent('li')) or (page['mode']=='paragraph' and kind=='p') or (page['mode']=='table' and kind=='td'):
    # Preserve the exact selected block, excluding markup/citation numbers only.
    text=node.get_text(' ',strip=True)
    if not text or len(text)<3:continue
    if re.search(r'copyright|all rights reserved|©|https?://|@',text,re.I):raise ValueError('third_party_or_contact_in_excerpt')
    blocks.append(text)
   if len('\n'.join(blocks))>8000:raise ValueError('section_too_large')
  break
 text='\n'.join(blocks)
 if not 60<=len(text)<=8000 or len(text.split())<10:raise ValueError('insufficient_selected_text')
 return text

def document(source,page,text,page_hash,retrieved_at,mode):
 doc={'source_id':source['id'],'url':page['url'],'title':page['title'],'content_date':page.get('known_content_date'),'text':text,'text_sha256':digest(text),'page_sha256':page_hash,'retrieved_at':retrieved_at,'last_checked_at':datetime.now(timezone.utc).isoformat(),'retrieval_mode':mode,'source_kind':'knowledge_symptom_excerpt' if page['train_eligible'] else 'knowledge_condition_reference','policy_url':source['policy_url'],'reuse_notice':source['notice'],'label_aliases':page['label_aliases'],'disease_aliases':page['disease_aliases'],'train_eligible':page['train_eligible'],'training_status':'not_reviewed_against_master'}
 if mode!='live' and (datetime.now(timezone.utc)-datetime.fromisoformat(retrieved_at)).days>31:doc['train_eligible']=False
 return doc

def collect(source,fetch=None):
 """Live fetch first; an explicitly reviewed snapshot is a dated fallback, not a new crawl."""
 fetch=fetch or Fetcher(source['allowed_domains']);docs=[];errors=[]
 for page in source['pages'][:3]:
  try:
   canonical(page['url'],source['allowed_domains'])
   if source['policy_status']!='reviewed_institute_authored_text_only':raise ValueError('reuse_not_reviewed')
   html=fetch(page['url']);text=extract(html,page)
   docs.append(document(source,page,text,__import__('hashlib').sha256(html.encode()).hexdigest(),datetime.now(timezone.utc).isoformat(),'live'))
  except Exception as error:
   errors.append({'url':page['url'],'error_type':type(error).__name__,'reason':str(error)[:100] if isinstance(error,ValueError) else 'http_'+str(error.code) if isinstance(error,HTTPError) else 'source_unavailable'})
   # Do not hide title changes, robots disallow or detected rights conflicts behind a cache.
   if not isinstance(error,(HTTPError,URLError,TimeoutError)):continue
   prior=source.get('_previous',{}).get(page['url'])
   snapshot=page.get('reviewed_snapshot')
   if prior and prior.get('policy_url')==source['policy_url']:
    docs.append(document(source,page,prior['text'],prior['page_sha256'],prior['retrieved_at'],'last_successful_snapshot'))
   elif snapshot and __import__('hashlib').sha256(snapshot['text'].encode()).hexdigest()==snapshot['sha256']:
    docs.append(document(source,page,snapshot['text'],snapshot['page_sha256'],snapshot['retrieved_at'],'reviewed_snapshot'))
 return docs,{'source_id':source['id'],'pages_attempted':min(3,len(source['pages'])),'pages_collected':len(docs),'pages_live':sum(d['retrieval_mode']=='live' for d in docs),'pages_snapshot':sum(d['retrieval_mode']!='live' for d in docs),'errors':errors}

# Ten named tools, each independently callable and configurable.
def crawl_cdc(source,fetch=None):return collect(source,fetch)
def crawl_niddk(source,fetch=None):return collect(source,fetch)
def crawl_nhlbi(source,fetch=None):return collect(source,fetch)
def crawl_nimh(source,fetch=None):return collect(source,fetch)
def crawl_nei(source,fetch=None):return collect(source,fetch)
def crawl_nidcd(source,fetch=None):return collect(source,fetch)
def crawl_nidcr(source,fetch=None):return collect(source,fetch)
def crawl_nichd(source,fetch=None):return collect(source,fetch)
def crawl_medlineplus(source,fetch=None):return collect(source,fetch)
def crawl_nccih(source,fetch=None):return collect(source,fetch)
TOOLS={f.__name__.removeprefix('crawl_'):f for f in [crawl_cdc,crawl_niddk,crawl_nhlbi,crawl_nimh,crawl_nei,crawl_nidcd,crawl_nidcr,crawl_nichd,crawl_medlineplus,crawl_nccih]}

def refresh(rows,registry,previous=None,target=100,threshold=.8,only=None,fetch=None):
 catalog={d['url']:dict(d) for d in previous or []};out=list(rows);groups={r['group_id'] for r in rows}
 counts=collections.Counter(r['label'] for r in rows if r['split']=='train');added=collections.Counter();reports=[];dupes=None;deadline=time.monotonic()+registry.get('max_seconds',600)
 for source in registry['sources']:
  if not source.get('enabled') or (only and source['id']!=only):continue
  if time.monotonic()>deadline:reports.append({'source_id':source['id'],'status':'time_budget_exhausted'});continue
  docs,report=TOOLS[source['id']]({**source,'_previous':catalog},fetch);reports.append(report)
  for doc in docs:
   label=resolve_label(doc,rows);group='web:'+digest(doc['url']);status='eligible'
   if not doc['train_eligible']:status='reference_only'
   elif label is None:status='ambiguous_or_unknown_label'
   elif counts[label]>=target:status='quota_reached'
   elif group in groups:status='already_ingested_page'
   elif len(doc['text'])>1800:status='train_excerpt_too_long'
   elif any(re.search(r'(?<!\w)'+re.escape(norm(a))+r'(?!\w)',norm(doc['text'])) for a in doc['disease_aliases']+[label]):status='target_name_in_input'
   else:
    if dupes is None:dupes=Duplicates(out,threshold)
    if dupes.contains(doc['text']):status='duplicate_or_near_existing'
   if status=='eligible':
    label_id=next(r['label_id'] for r in rows if r['label']==label)
    out.append({'record_id':digest(doc['text']),'text':doc['text'],'label':label,'label_id':label_id,'language':'en','source_files':[doc['url']],'group_id':group,'split':'train','source_url':doc['url'],'source_kind':'knowledge_symptom_excerpt','source_sha256':doc['page_sha256'],'retrieved_at':doc['retrieved_at'],'label_method':'reviewed_exact_page_mapping','reuse_notice':doc['reuse_notice'],'reuse_policy_url':doc['policy_url']})
    added[label]+=1;counts[label]+=1;groups.add(group);dupes.add(doc['text']);status='accepted_train'
   doc['training_status']=status;doc['matched_label']=label;catalog[doc['url']]=doc
 assert [r for r in out if r['split']!='train']==[r for r in rows if r['split']!='train'],'Frozen holdouts changed'
 report={'sources':reports,'sources_attempted':len(reports),'sources_ok':sum(x.get('pages_live',0)>0 for x in reports),'sources_with_content':sum(x.get('pages_collected',0)>0 for x in reports),'snapshot_sources':sum(x.get('pages_snapshot',0)>0 for x in reports),'knowledge_documents':len(catalog),'accepted_train':sum(added.values()),'added_by_label':dict(added),'note':'Reference pages are knowledge, not independent patient cases. One canonical URL is one training group; no synthetic paraphrase expansion.'}
 return out,sorted(catalog.values(),key=lambda d:d['url']),report

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--source',choices=['all',*TOOLS],default='all');p.add_argument('--output',type=Path,default=Path('web-crawl-preview'));a=p.parse_args()
 registry=json.loads((ROOT/'web_collectors.json').read_text());_,docs,report=refresh([],registry,only=None if a.source=='all' else a.source)
 a.output.mkdir(parents=True,exist_ok=True)
 (a.output/'medical_source_knowledge.jsonl').write_text(''.join(json.dumps(d,ensure_ascii=False)+'\n' for d in docs))
 (a.output/'source_crawl_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
