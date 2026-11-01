"""Import vetted, pinned published TRAIN data; never turn original test into train."""
import collections,json,re
from datetime import datetime,timezone
from enrichment import norm,digest,Duplicates

def import_rows(rows,source,train_rows,test_rows,target=100,threshold=.8):
 counts=collections.Counter(r['label'] for r in rows if r['split']=='train')
 groups=collections.defaultdict(set)
 for r in rows:groups[norm(r['label'])].add((r['label'],r['label_id']))
 labels={k:next(iter(v)) for k,v in groups.items() if len(v)==1}
 if len(train_rows)>5000:raise ValueError('Published source exceeds reviewed acquisition budget')
 existing=Duplicates(rows,threshold);original_test=Duplicates([{'text':x['input_text']} for x in test_rows],threshold)
 additions=[];stats=collections.Counter();perlabel=collections.Counter();seen={}
 # Conflicting labels for exactly the same source input are all rejected.
 for x in train_rows:seen.setdefault(digest(x['input_text']),set()).add(x['output_text'])
 for x in sorted(train_rows,key=lambda x:digest(x['input_text'])):
  text=x['input_text'].strip();original=x['output_text'];mapped=source['label_map'].get(original)
  if mapped is None or norm(mapped) not in labels:stats['unmapped_label']+=1;continue
  label,label_id=labels[norm(mapped)]
  if counts[label]+perlabel[label]>=target or perlabel[label]>=source['max_per_label']:stats['quota_reached']+=1;continue
  if len(seen[digest(text)])!=1:stats['conflicting_input_label']+=1;continue
  if not 40<=len(text)<=1500 or len(text.split())<8 or re.search(r'https?://|@|\ufffd',text):stats['input_quality']+=1;continue
  if any(re.search(r'(?<!\w)'+re.escape(norm(a))+r'(?!\w)',norm(text)) for a in [original,label]):stats['target_name_in_input']+=1;continue
  if original_test.contains(text):stats['near_original_source_test']+=1;continue
  if existing.contains(text):stats['duplicate_or_near_existing']+=1;continue
  url='https://huggingface.co/datasets/'+source['repo']+'/blob/'+source['revision']+'/'+source['train_file']
  additions.append({'record_id':digest(text),'text':text,'label':label,'label_id':label_id,'language':'en','source_files':[url],'group_id':'published:'+source['repo']+':'+digest(text),'split':'train','source_url':url,'source_kind':source['kind'],'source_sha256':digest(text),'retrieved_at':datetime.now(timezone.utc).isoformat(),'label_method':'published_label_reviewed_crosswalk','reuse_notice':source['notice'],'reuse_policy_url':'https://huggingface.co/datasets/'+source['repo']+'/blob/'+source['revision']+'/README.md'})
  perlabel[label]+=1;existing.add(text)
 return rows+additions,{'source':source['repo'],'revision':source['revision'],'statistics':dict(stats),'accepted':len(additions),'added_by_label':dict(perlabel),'label_quality':'source-provided synthetic labels; no clinical validation claim'}

def refresh(rows,registry,target=100,threshold=.8):
 from huggingface_hub import hf_hub_download,HfApi
 reports=[]
 for source in registry['sources']:
  info=HfApi().dataset_info(source['repo'],revision=source['revision'])
  card=info.card_data.to_dict() if info.card_data else {}
  if card.get('license')!=source['license']:raise ValueError('Published source license differs from reviewed manifest')
  def read(name):
   path=hf_hub_download(repo_id=source['repo'],repo_type='dataset',revision=source['revision'],filename=name)
   with open(path) as f:return [json.loads(line) for line in f if line.strip()]
  rows,report=import_rows(rows,source,read(source['train_file']),read(source['test_file']),target,threshold);reports.append(report)
 return rows,reports
