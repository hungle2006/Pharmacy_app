"""Deterministic technical preparation for research classification, not clinical adjudication."""
import argparse,collections,hashlib,html,json,re,unicodedata
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


def nfc(s):return unicodedata.normalize('NFC',s or '')
def key(s):return ' '.join(re.sub(r'[^\w\s]',' ',nfc(s).casefold()).split())
def h(s):return hashlib.sha256(s.encode()).hexdigest()
def tidy(s):
 s=nfc(html.unescape(s));s=re.sub(r'<think\b[^>]*>.*?</think\s*>',' ',s,flags=re.I|re.S)
 if re.search(r'</think\s*>',s,re.I):s=re.split(r'</think\s*>',s,flags=re.I)[-1]
 s=re.sub(r'<think\b[^>]*>.*$',' ',s,flags=re.I|re.S)
 s=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[EMAIL]',s)
 # Vietnam-style phone patterns only; no broad numeric removal of age/lab measurements.
 s=re.sub(r'(?<!\w)(?:\+84|0)(?:[ .-]?\d){9}(?!\w)','[PHONE]',s)
 s=re.sub(r'^(?:(?:Hello|Hi|Dear doctor|Chào bác sĩ|Xin chào bác sĩ)[,!.:\s]+)+','',s,flags=re.I)
 s=re.sub(r'^(?:My name is|Tôi tên là|Tên tôi là)\s+[^,.;:\d\n]{2,70}[,.;:]\s*','',s,flags=re.I)
 return ' '.join(s.split()).strip(' ,;:')
def named(text,label):
 k=key(label);k=re.sub(r'^bệnh\s+','',k)
 return bool(k and re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)',key(text)))
def shingles(s):
 words=key(s).split();return {' '.join(words[i:i+3]) for i in range(max(0,len(words)-2))} or set(words)
def simhash(tokens):
 weights=[0]*64
 for token in tokens:
  bits=int.from_bytes(hashlib.blake2b(token.encode(),digest_size=8).digest(),'little')
  for i in range(64):weights[i]+=1 if bits>>i&1 else -1
 return sum(1<<i for i,v in enumerate(weights) if v>=0)

def build(source,out,min_groups=10):
 out.mkdir(parents=True,exist_ok=True);rows=[];exclusions=[];alias={};stats=collections.Counter()
 cols=['record_id','task','language_hint','input_text','disease_label','sources','quality_flags']
 allrows=[]
 for b in pq.ParquetFile(source).iter_batches(batch_size=512,columns=cols):
  for r in b.to_pylist():
   if r['task']!='disease_classification':stats['non_classification_rows_not_used']+=1;continue
   allrows.append(r)
 keys={key(r['disease_label']) for r in allrows}
 symptom_names=['Chóng mặt','Cứng khớp ngón tay','Khàn tiếng','Khó thở','Mất ngủ','Nghẹt mũi','Sổ mũi','Tiêu chảy','Táo bón','Đau bụng','Đau lưng','Đau ngực','Đau vai','Đau đầu','Sốt','Ho','Buồn nôn','Nôn','Mệt mỏi']
 symptoms={key(s) for s in symptom_names}
 display=collections.defaultdict(collections.Counter)
 def lk(label):
  k=key(label)
  if k.startswith('bệnh ') and k[5:] in keys:k=k[5:]
  return k
 for r in allrows:display[lk(r['disease_label'])][nfc(r['disease_label'])]+=1
 # Prefer display forms from the main consultation source, then frequency; identity never drops accents.
 for r in allrows:
  k=lk(r['disease_label']);raw=r['disease_label'];alias[raw]=k
 for r in allrows:
  text=tidy(r['input_text']);label=lk(r['disease_label']);reasons=[]
  if not text or len(key(text).split())<5:reasons.append('empty_or_less_than_5_words')
  if not label:reasons.append('missing_label')
  if label in symptoms:reasons.append('symptom_only_label_outside_disease_scope')
  if named(text,label):reasons.append('target_name_in_input')
  if '\ufffd' in text:reasons.append('replacement_character')
  if re.search(r'(?i)diagnos(?:is|ed)\s*[:=]|chẩn đoán\s*[:=]',text):reasons.append('explicit_diagnosis_marker')
  if r['language_hint'] not in ['vi','en']:reasons.append('unverified_language')
  if reasons:exclusions.append({'record_id':r['record_id'],'reasons':reasons});continue
  rows.append({'record_id':r['record_id'],'text':text,'label_key':label,'language':r['language_hint'],'source_files':sorted({s['file'] for s in r['sources']}),'original_group':h(key(text))})
 print('FILTERED',len(rows),flush=True)
 # Recompute ambiguity after final text/label normalization; quarantine all labels for the same input.
 qlabels=collections.defaultdict(set)
 for r in rows:qlabels[r['original_group']].add(r['label_key'])
 conflicts={q for q,labels in qlabels.items() if len(labels)>1};filtered=[];seen={}
 for r in rows:
  if r['original_group'] in conflicts:exclusions.append({'record_id':r['record_id'],'reasons':['same_clean_input_conflicting_labels']});continue
  pair=(r['original_group'],r['label_key'])
  if pair in seen:
   dest=filtered[seen[pair]];dest['source_files']=sorted(set(dest['source_files'])|set(r['source_files']));exclusions.append({'record_id':r['record_id'],'reasons':['duplicate_clean_pair_merged']});continue
  seen[pair]=len(filtered);filtered.append(r)
 rows=filtered;print('EXACT_GROUPED',len(rows),'conflict_groups',len(conflicts),flush=True)
 # Conservative lexical near-duplicate clustering. Not a claim of complete semantic deduplication.
 parent=list(range(len(rows)));size=[1]*len(rows)
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def union(a,b):
  a,b=find(a),find(b)
  if a==b:return
  if size[a]<size[b]:a,b=b,a
  parent[b]=a;size[a]+=size[b]
 buckets=collections.defaultdict(list);sigs=[];sets=[];near_edges=0;skipped=0
 for i,r in enumerate(rows):
  tokens=shingles(r['text']);sig=simhash(tokens);sigs.append(sig);sets.append(tokens);candidates=set()
  for band in range(4):
   b=(band,(sig>>(16*band))&65535)
   if len(buckets[b])<=1000:candidates.update(buckets[b])
   else:skipped+=1
  for j in candidates:
   if (sig^sigs[j]).bit_count()>3:continue
   if min(len(tokens),len(sets[j]))/max(len(tokens),len(sets[j]),1)<.85:continue
   jac=len(tokens&sets[j])/max(1,len(tokens|sets[j]))
   if jac>=.85:union(i,j);near_edges+=1
  for band in range(4):buckets[(band,(sig>>(16*band))&65535)].append(i)
  if (i+1)%30000==0:print('NEAR_GROUPING',i+1,flush=True)
 groupmembers=collections.defaultdict(list)
 for i in range(len(rows)):groupmembers[find(i)].append(i)
 for group,indices in groupmembers.items():
  gid=min(rows[i]['record_id'] for i in indices)
  for i in indices:rows[i]['group_id']=gid
 # Quarantine lexical near-clusters with conflicting labels: their inputs differ minimally.
 badnear={group for group,indices in groupmembers.items() if len({rows[i]['label_key'] for i in indices})>1};badids={rows[i]['record_id'] for g in badnear for i in groupmembers[g]}
 final=[]
 for r in rows:
  if r['record_id'] in badids:exclusions.append({'record_id':r['record_id'],'reasons':['near_duplicate_cluster_conflicting_labels']})
  else:final.append(r)
 rows=final
 input_classification_count=len(allrows)
 del sets,buckets,sigs,allrows
 classgroups=collections.defaultdict(set)
 for r in rows:classgroups[r['label_key']].add(r['group_id'])
 rare={label for label,g in classgroups.items() if len(g)<min_groups};final=[]
 for r in rows:
  if r['label_key'] in rare:exclusions.append({'record_id':r['record_id'],'reasons':[f'fewer_than_{min_groups}_distinct_groups_in_class']})
  else:final.append(r)
 rows=final;labels=sorted({r['label_key'] for r in rows});l2id={v:i for i,v in enumerate(labels)}
 # Choose a representative original label from the canonical group, preserve all alias mappings in JSON.
 displays={k:display[k].most_common(1)[0][0] for k in labels}
 y=np.array([l2id[r['label_key']] for r in rows]);g=np.array([r['group_id'] for r in rows]);fold=np.full(len(rows),-1,dtype=int)
 # Near-conflict clusters were removed, so each remaining group has one label.
 # Balance indivisible groups within each label, without allocating a giant group-by-class matrix.
 rng=np.random.default_rng(42);global_load=[0]*10
 for label_id in sorted(set(y)):
  members=collections.defaultdict(list)
  for index in np.flatnonzero(y==label_id):members[g[index]].append(int(index))
  entries=list(members.values());rng.shuffle(entries);entries.sort(key=len,reverse=True)
  class_load=[0]*10
  for indices in entries:
   candidates=[f for f in range(10) if class_load[f]==min(class_load)]
   f=min(candidates,key=lambda k:(global_load[k],k))
   fold[indices]=f;class_load[f]+=len(indices);global_load[f]+=len(indices)
 assert (fold>=0).all()
 for i,r in enumerate(rows):r['label_id']=int(y[i]);r['label']=displays[r.pop('label_key')];r['split']='test' if fold[i]==0 else 'validation' if fold[i]==1 else 'train';r.pop('original_group',None)
 # Rarely a greedy group split may miss a class in a holdout: explicitly fail instead of concealing it.
 expected=set(l2id.values())
 for split in ['train','validation','test']:
  actual={r['label_id'] for r in rows if r['split']==split}
  assert actual==expected,(split,'missing',len(expected-actual))
 splitgroups={s:{r['group_id'] for r in rows if r['split']==s} for s in ['train','validation','test']}
 assert not(splitgroups['train']&splitgroups['validation'] or splitgroups['train']&splitgroups['test'] or splitgroups['validation']&splitgroups['test'])
 schema=pa.schema([('record_id',pa.string()),('text',pa.string()),('label',pa.string()),('label_id',pa.int32()),('language',pa.string()),('source_files',pa.list_(pa.string())),('group_id',pa.string()),('split',pa.string())])
 pq.write_table(pa.Table.from_pylist(rows,schema=schema),out/'disease_train_ready.parquet',compression='zstd')
 bysplit=collections.Counter(r['split'] for r in rows);bylang=collections.Counter(r['language'] for r in rows);reason=collections.Counter(reason for r in exclusions for reason in r['reasons']);perlabel=[]
 for i,k in enumerate(labels):
  subset=[r for r in rows if r['label_id']==i];perlabel.append({'label_id':i,'label':displays[k],'canonical_key':k,'counts':dict(collections.Counter(r['split'] for r in subset)),'languages':dict(collections.Counter(r['language'] for r in subset))})
 source_hasher=hashlib.sha256()
 with source.open('rb') as stream:
  for block in iter(lambda:stream.read(8*1024*1024),b''):source_hasher.update(block)
 sourcehash=source_hasher.hexdigest();outputhash=hashlib.sha256((out/'disease_train_ready.parquet').read_bytes()).hexdigest()
 report={'created':'2026-10-31','purpose':'Technically prepared bilingual disease-label classification research set. Not expert-adjudicated clinical diagnoses.','input_archive_sha256':sourcehash,'output_sha256':outputhash,'input_classification_rows':input_classification_count,'output_rows':len(rows),'classes':len(labels),'split_counts':dict(bysplit),'language_counts':dict(bylang),'exclusion_reason_counts':dict(reason),'excluded_or_merged_rows':len(exclusions),'non_classification_rows_not_used':stats['non_classification_rows_not_used'],'exact_conflict_groups_after_cleanup':len(conflicts),'near_duplicate_edges':near_edges,'near_conflict_clusters':len(badnear),'lsh_bucket_checks_skipped_over_1000':skipped,'minimum_groups_per_class':min_groups,'near_duplicate_method':'64-bit SimHash on normalized word trigrams; 4 bands, Hamming<=3, trigram Jaccard>=0.85; candidates in overfull buckets skipped. Incomplete lexical heuristic, not exhaustive semantic grouping.','split_method':'Per-label allocation of indivisible groups into 10 folds, largest first, least-loaded class fold then global fold (seed=42 tie shuffle). Fold0 test, fold1 validation, remaining8 train. No exact/identified near group crosses split. Same-source templates can still correlate.','alias_policy':'NFC/case/punctuation/whitespace and leading Bệnh only if a matching unprefixed label exists. Accents preserved. No fuzzy synonym/ICD merge.','removed_symptom_labels':symptom_names,'labels':perlabel,'limitations':['No human clinical label validation or complete de-identification.','First-user text can lack differentiating symptoms.','English subset retained; use multilingual encoder.','No full semantic or cross-language translation deduplication.','No independent clinical/source holdout. Test measures same-source label classification.','QA/question/doc rows retained in original archive, not given fabricated disease labels.']}
 (out/'preparation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 (out/'label_map.json').write_text(json.dumps({'label2id':{displays[k]:v for k,v in l2id.items()},'id2label':{str(v):displays[k] for k,v in l2id.items()},'aliases_to_canonical_key':alias},ensure_ascii=False,indent=2))
 # Audit IDs and reasons only. No patient input text is exported in the exclusion log.
 with (out/'excluded_record_ids.jsonl').open('w') as f:
  for r in exclusions:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 print('READY',json.dumps({k:report[k] for k in ['output_rows','classes','split_counts','language_counts','exclusion_reason_counts','near_duplicate_edges']},ensure_ascii=False),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--min-groups',type=int,default=10);a=p.parse_args();build(a.input,a.output,a.min_groups)
