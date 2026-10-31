"""Download one immutable HF snapshot, normalize compatible Parquet schemas, freeze holdouts."""
from pathlib import Path
import collections,fnmatch,hashlib,json,re,shutil
import pyarrow as pa
import pyarrow.parquet as pq
from prepare_train_ready import tidy,key,named,build,shingles,simhash

def sha_file(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def text_hash(text):return hashlib.sha256(key(text).encode()).hexdigest()
def snapshot_dataset(config,cache,api=None,download=None):
 from huggingface_hub import HfApi,snapshot_download
 api=api or HfApi();download=download or snapshot_download
 info=api.repo_info(config['dataset_repo'],repo_type='dataset',files_metadata=True)
 files=sorted(s.rfilename for s in info.siblings if any(fnmatch.fnmatch(s.rfilename,p) for p in config['parquet_patterns']))
 if not files:raise ValueError('Dataset repo has no matching Parquet files')
 root=Path(download(repo_id=config['dataset_repo'],repo_type='dataset',revision=info.sha,allow_patterns=files,cache_dir=str(cache)))
 manifest=[{'path':f,'sha256':sha_file(root/f),'bytes':(root/f).stat().st_size} for f in files]
 fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
 return root,files,{'dataset_revision':info.sha,'data_fingerprint':fingerprint,'files':manifest}
def read_rows(root,files):
 rows=[];stats=collections.Counter();aliases={}
 for name in files:
  p=pq.ParquetFile(root/name);columns=set(p.schema_arrow.names)
  if not ({'text','label'}<=columns or {'input_text','disease_label'}<=columns or {'messages','target_disease'}<=columns or {'Question','Disease'}<=columns):
   if {'question','answer'}<=columns or {'question','category'}<=columns:stats['non_classification_rows_skipped']+=p.metadata.num_rows;continue
   raise ValueError(f'Unsupported schema in {name}; do not infer disease labels from QA answers')
  for batch in p.iter_batches(batch_size=256):
   for index,r in enumerate(batch.to_pylist()):
    stats['rows_scanned']+=1
    if 'task' in r and r['task']!='disease_classification':stats['non_classification_rows_skipped']+=1;continue
    original_split=r.get('split');split=original_split if original_split in ['train','validation','test'] else None
    if 'text' in r:raw=r['text'];label=r['label'];lang=r.get('language','und')
    elif 'input_text' in r:raw=r['input_text'];label=r['disease_label'];lang=r.get('language_hint','und')
    elif 'messages' in r:
     users=[m.get('content') or '' for m in r['messages'] if m.get('role')=='user'];raw=users[0] if users else '';label=r['target_disease'];lang={'english':'en','vietnamese':'vi'}.get(r.get('subset'),'und')
    else:raw=r['Question'];label=r['Disease'];lang='vi'
    if not isinstance(label,str):raise ValueError(f'{name}: label must be a disease name string, not numeric class IDs')
    label=label.strip();text=tidy(raw or '')
    if key(label)=='nhiễm khuẩn h':label='Nhiễm Khuẩn H.Pylori';stats['h_pylori_name_repaired']+=1
    if not text or len(key(text).split())<5 or not label or '\ufffd' in text or named(text,label):
     if split in ['validation','test']:raise ValueError('A supplied holdout fails input quality checks; repair or version the benchmark explicitly')
     stats['invalid_or_target_named_rows_skipped']+=1;continue
    k=key(label);aliases.setdefault(k,label)
    q=text_hash(text);rows.append({'text':text,'label_key':k,'language':lang,'split':split,'group_id':r.get('group_id') or r.get('input_group_id') or q,'record_id':q,'source_files':[name]})
 # Exact same input across files is one observation. Preserve split annotations and reject conflicting holdouts.
 grouped=collections.defaultdict(list)
 for r in rows:grouped[r['record_id']].append(r)
 out=[]
 for q,items in grouped.items():
  labels={r['label_key'] for r in items};splits={r['split'] for r in items if r['split']}
  if len(labels)>1:
   if splits&{'validation','test'}:raise ValueError('Conflicting labels affect supplied holdout; benchmark review required')
   stats['conflicting_rows_quarantined']+=len(items);continue
  if len(splits)>1:raise ValueError('Identical text appears in different provided splits')
  r=items[0];r['split']=next(iter(splits),None);r['source_files']=sorted({f for i in items for f in i['source_files']});out.append(r);stats['duplicate_occurrences_merged']+=len(items)-1
 return out,aliases,dict(stats)
def _write_ready(rows,path):
 schema=pa.schema([('record_id',pa.string()),('text',pa.string()),('label',pa.string()),('label_id',pa.int32()),('language',pa.string()),('source_files',pa.list_(pa.string())),('group_id',pa.string()),('split',pa.string())])
 pq.write_table(pa.Table.from_pylist(rows,schema=schema),path,compression='zstd')
def prepare(root,files,state_dir,out):
 state_dir=Path(state_dir);out=Path(out);state_dir.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
 rows,aliases,stats=read_rows(Path(root),files);state_path=state_dir/'registry.json';hold_path=state_dir/'holdouts.parquet'
 if not rows:raise ValueError('No usable disease-labelled records')
 if state_path.exists():
  state=json.loads(state_path.read_text());holdouts=pq.read_table(hold_path).to_pylist();known=state['seen'];labels=state['labels'];display=state['display'];groles=state['group_roles'];train=[]
  held={r['record_id']:r for r in holdouts}
  # Index fixed holdouts only. Compare genuinely new examples to a conservative lexical near-duplicate index.
  index=collections.defaultdict(list);features={};signatures={}
  def ensure_index():
   if features:return
   for r in holdouts:
    q=r['record_id'];tokens=shingles(r['text']);sig=simhash(tokens);features[q]=tokens;signatures[q]=sig
    for b in range(4):index[(b,(sig>>(16*b))&65535)].append(q)
  for r in rows:
   q=r['record_id'];lk=r['label_key'];requested=r['split'];g=r['group_id']
   if q in known and known[q]['label_key']!=lk:raise ValueError('A previously seen example changed label; use a reviewed new benchmark version')
   if q in held:continue # Preserve the exact frozen holdout, independent of source file deletions/reordering.
   if q in known and requested in ['validation','test']:raise ValueError('Historical training example cannot move into a holdout')
   if lk not in labels:stats['new_class_rows_quarantined']=stats.get('new_class_rows_quarantined',0)+1;continue
   if requested in ['validation','test'] or groles.get(g) in ['validation','test']:
    stats['new_or_heldout_related_rows_quarantined']=stats.get('new_or_heldout_related_rows_quarantined',0)+1;continue
   if q not in known:
    ensure_index();tokens=shingles(r['text']);sig=simhash(tokens);near=False;candidates=set()
    for b in range(4):candidates.update(index[(b,(sig>>(16*b))&65535)])
    for other in candidates:
     if (sig^signatures[other]).bit_count()<=3 and len(tokens&features[other])/max(1,len(tokens|features[other]))>=.85:near=True;break
    if near:stats['new_near_holdout_rows_quarantined']=stats.get('new_near_holdout_rows_quarantined',0)+1;continue
   r={**r,'label':display[lk],'label_id':labels.index(lk),'split':'train'};r.pop('label_key');train.append(r);known[q]={'label_key':lk,'split':'train'};groles[g]='train'
  final=train+holdouts
 else:
  splits={r['split'] for r in rows}
  if {'train','validation','test'}<=splits:
   # Use prepared splits; new unsplit records are train only if their labels already have holdout coverage.
   covered={r['label_key'] for r in rows if r['split']=='validation'}&{r['label_key'] for r in rows if r['split']=='test'}&{r['label_key'] for r in rows if r['split']=='train'}
   labels=sorted(covered);display={k:aliases[k] for k in labels};final=[]
   for r in rows:
    if r['label_key'] not in covered:stats['classes_without_full_split_coverage_skipped']=stats.get('classes_without_full_split_coverage_skipped',0)+1;continue
    k=r.pop('label_key');r.update(label=display[k],label_id=labels.index(k),split=r['split'] or 'train');final.append(r)
  else:
   # Raw compatible shards are passed through the previously verified technical cleaner and group splitter.
   master=[]
   for r in rows:master.append({'record_id':r['record_id'],'task':'disease_classification','language_hint':r['language'],'input_text':r['text'],'disease_label':aliases[r['label_key']],'sources':[{'file':r['source_files'][0]}],'quality_flags':[]})
   temp=out/'raw_labelled.parquet';pq.write_table(pa.Table.from_pylist(master),temp)
   build(temp,out/'first_preparation',min_groups=10);final=pq.read_table(out/'first_preparation/disease_train_ready.parquet').to_pylist();temp.unlink()
   labels=sorted({key(r['label']) for r in final});display={key(r['label']):r['label'] for r in final}
   for r in final:r['record_id']=text_hash(r['text']);r['label_id']=labels.index(key(r['label']))
  holdouts=[r for r in final if r['split']!='train'];_write_ready(holdouts,hold_path)
  state={'labels':labels,'display':display,'seen':{r['record_id']:{'label_key':key(r['label']),'split':r['split']} for r in final},'group_roles':{r['group_id']:r['split'] for r in final}}
 if len(state['labels'])<2:raise ValueError('Need at least two disease classes')
 validate(final)
 # Benchmark identity includes labels and exact frozen holdout texts/targets, never current training rows.
 bhash=hashlib.sha256(json.dumps(sorted((r['record_id'],r['label_id'],r['split']) for r in final if r['split']!='train'),ensure_ascii=False).encode()).hexdigest()
 dest=out/'disease_train_ready.parquet';_write_ready(final,dest)
 report={'output_sha256':sha_file(dest),'benchmark_sha256':bhash,'rows':len(final),'classes':len(state['labels']),'splits':dict(collections.Counter(r['split'] for r in final)),'statistics':stats,'note':'Frozen same-source benchmark; no claim of exhaustive semantic or translation deduplication or clinical label validation.'}
 (out/'preparation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 # Atomic registry update. Historical train hashes never become new holdout examples.
 tmp=state_path.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False));tmp.replace(state_path)
 return report
def validate(rows):
 seen={};groups=collections.defaultdict(set);classes=collections.defaultdict(set)
 for r in rows:
  q=text_hash(r['text']);assert q not in seen,'Duplicate normalized text';seen[q]=r['split'];groups[r['group_id']].add(r['split']);classes[r['split']].add(r['label_id']);assert not re.search(r'</?think\b',r['text'],re.I)
 assert all(len(s)==1 for s in groups.values()),'Group leakage'
 assert set(classes)=={'train','validation','test'}
 assert classes['train']==classes['validation']==classes['test'],'Class coverage differs'
