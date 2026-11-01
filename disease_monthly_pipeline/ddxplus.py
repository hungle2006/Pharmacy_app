"""Checksum-pinned DDXPlus TRAIN importer. No differential-label leakage.
Synthetic positive evidence is rendered as faithful English question/answer pairs.
No translations, invented patient prose, or variants of the same evidence set.
"""
import ast,collections,csv,hashlib,io,json,re,zipfile
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen
from enrichment import norm,digest,Duplicates

def sha256(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def download(spec,cache):
 path=Path(cache)/spec['name'];path.parent.mkdir(parents=True,exist_ok=True)
 if path.is_file() and sha256(path)==spec['sha256']:return path
 temp=path.with_suffix(path.suffix+'.partial');size=0
 try:
  with urlopen('https://ndownloader.figshare.com/files/'+str(spec['id']),timeout=60) as response,temp.open('wb') as output:
   while True:
    block=response.read(1024*1024)
    if not block:break
    size+=len(block)
    if size>spec['max_bytes']:raise ValueError('DDXPlus download exceeds reviewed limit')
    output.write(block)
  if sha256(temp)!=spec['sha256']:raise ValueError('DDXPlus checksum changed')
  temp.replace(path)
 finally:temp.unlink(missing_ok=True)
 return path

def render(evidence_value,evidences):
 codes=ast.literal_eval(evidence_value)
 if not isinstance(codes,list) or not all(isinstance(c,str) for c in codes) or len(codes)>300:raise ValueError('Invalid evidence list')
 pairs=[]
 for code in sorted(set(codes)):
  key,sep,value=code.partition('_@_');spec=evidences.get(key)
  if spec is None:raise ValueError('Unknown evidence code')
  if spec['is_antecedent']:continue
  if spec['data_type']=='B':
   if sep:raise ValueError('Unexpected binary value')
   answer='Yes'
  else:
   if not sep:raise ValueError('Missing categorical value')
   if str(spec['default_value'])==value:continue
   meaning=spec.get('value_meaning',{}).get(value,{}).get('en')
   # Numeric scales without documented anchors are omitted, never interpreted.
   if not meaning or meaning in {'NA','N','nowhere'}:continue
   answer='Yes' if meaning=='Y' else meaning
  question=spec['question_en'].strip()
  if not question:raise ValueError('Missing evidence question')
  pairs.append(question+' '+answer+'.')
 return '\n'.join(pairs),digest('\n'.join(pairs)),len(pairs)

def import_cases(rows,source,cases,evidences,target=100,threshold=.8):
 counts=collections.Counter(r['label'] for r in rows if r['split']=='train');labels=collections.defaultdict(set)
 for r in rows:labels[norm(r['label'])].add((r['label'],r['label_id']))
 mapping={k:next(iter(labels[norm(v)])) for k,v in source['label_map'].items() if len(labels[norm(v)])==1}
 fraction=source.get('max_source_fraction',.5)
 if not 0<fraction<1:raise ValueError('Invalid source fraction')
 source_counts=collections.Counter(r['label'] for r in rows if r['split']=='train' and r.get('source_kind')=='synthetic_structured_evidence')
 quota={}
 for k,(label,_) in mapping.items():
  current=source_counts[label];other=counts[label]-current
  remaining_fraction=max(0,int(other*fraction/(1-fraction))-current)
  quota[k]=min(max(0,target-counts[label]),source['max_per_label'],remaining_fraction)
 stats=collections.Counter();added=collections.Counter();out=list(rows)
 if not any(quota.values()):return out,{'source':'DDXPlus','accepted':0,'added_by_label':{},'statistics':{'all_mapped_labels_at_target':1}}
 existing=Duplicates(rows,threshold);seen={r['group_id'] for r in rows}
 url='https://ndownloader.figshare.com/files/'+str(source['files']['train']['id'])
 for index,case in enumerate(cases):
  if index>=source['max_rows_scanned']:break
  stats['scanned_train_rows']+=1;original=case['PATHOLOGY']
  if not quota.get(original):continue
  label,label_id=mapping[original]
  text,fingerprint,n=render(case['EVIDENCES'],evidences);group='ddxplus:evidence:'+fingerprint
  if n<3 or not 80<=len(text)<=2000:stats['insufficient_or_long_evidence']+=1;continue
  if any(re.search(r'(?<!\w)'+re.escape(norm(a))+r'(?!\w)',norm(text)) for a in [original,label]):stats['target_in_input']+=1;continue
  if group in seen or existing.contains(text):stats['duplicate_or_near_existing']+=1;continue
  out.append({'record_id':digest(text),'text':text,'label':label,'label_id':label_id,'language':'en','source_files':[url],'group_id':group,'split':'train','source_url':url,'source_kind':'synthetic_structured_evidence','source_sha256':source['files']['train']['sha256'],'retrieved_at':datetime.now(timezone.utc).isoformat(),'label_method':'published_PATHOLOGY_reviewed_crosswalk','reuse_notice':source['notice'],'reuse_policy_url':source['license_url']})
  quota[original]-=1;added[label]+=1;seen.add(group);existing.add(text)
  if not any(quota.values()):break
 return out,{'source':'DDXPlus','accepted':sum(added.values()),'added_by_label':dict(added),'statistics':dict(stats),'files':source['files'],'label_quality':'Expert-knowledge-base simulated patients; structured evidence, not real clinical notes. Only source TRAIN used; no source test accuracy claim.'}

def refresh(rows,source,cache,target=100,threshold=.8):
 files={k:download(v,cache) for k,v in source['files'].items()}
 evidences=json.loads(files['evidences'].read_text());conditions=json.loads(files['conditions'].read_text())
 if not set(source['label_map'])<=set(conditions):raise ValueError('DDXPlus condition mapping changed')
 with zipfile.ZipFile(files['train']) as archive:
  members=archive.infolist()
  if len(members)!=1 or members[0].filename!='release_train_patients' or members[0].file_size>800_000_000:raise ValueError('Unexpected source TRAIN archive')
  with archive.open(members[0]) as raw:return import_cases(rows,source,csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8')),evidences,target,threshold)
