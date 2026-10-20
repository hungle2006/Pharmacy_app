"""Audit six exact uploaded workbook types and export dataset-preserving Silver CSV."""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from .xlsx_source import stream_rows
from .quality import base_flags,decision
INPUTS={
 'dav_component':('DAV_Normalized_v2_for_RxNorm_Mapping.xlsx','DAV_COMPONENT'),
 'dav_mapping':('DAV_RxNorm_Mapping_11834_Products.xlsx','DAV_RXNORM_MAPPING'),
 'dav_evidence':('DAV_RxNorm_Component_Evidence_14844.xlsx','COMPONENT_EVIDENCE'),
 'rxnorm_clean':('rxnorm_output.xlsx','00_Clean_Normalized'),
 'icd10_vi':('ICD10_Vietnam_Normalized.xlsx',None),
 'medi2':('MEDI-2_HPS_Normalized.xlsx',None)
}
def checksum(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(2097152),b''):h.update(chunk)
 return h.hexdigest()
def produce(indir,outdir,allow_partial=False):
 indir=Path(indir);outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
 missing=[name for name,_ in INPUTS.values() if not (indir/name).is_file()]
 if missing and not allow_partial:raise FileNotFoundError('Missing expected workbook(s): '+', '.join(missing))
 summary={};total=Counter()
 for dataset,(filename,sheet) in INPUTS.items():
  source=indir/filename
  if not source.exists():continue
  dst=outdir/dataset;dst.mkdir(exist_ok=True)
  counts=Counter();flags_count=Counter();handles={};writers={}
  try:
   for i,row in enumerate(stream_rows(source,sheet),start=2):
    flags=base_flags(dataset,row);status=decision(dataset,row,flags)
    r=dict(row);r.update({'silver_qc_status':status,'silver_qc_flags':'|'.join(flags),'silver_source_file':filename,'silver_source_excel_row':str(i)})
    if not writers:
     for partition in ('all','accepted','review','rejected'):
      handle=(dst/(partition+'.csv')).open('w',newline='',encoding='utf-8-sig')
      handles[partition]=handle;writers[partition]=csv.DictWriter(handle,fieldnames=list(r));writers[partition].writeheader()
    partition={'ACCEPTED':'accepted','REVIEW_REQUIRED':'review','REJECTED':'rejected'}[status]
    writers['all'].writerow(r);writers[partition].writerow(r)
    counts['total']+=1;counts[status]+=1
    for flag in flags:flags_count[flag]+=1
  finally:
   for h in handles.values():h.close()
  if counts['total']==0:raise ValueError('Empty workbook '+filename)
  summary[dataset]={'file':filename,'sha256':checksum(source),'rows':dict(counts),'flags':dict(flags_count)}
  total.update(counts)
 manifest={'pipeline':'pharmacy-silver-v3','policy':'CONSERVATIVE_NO_AUTO_CLINICAL_VERIFICATION',
   'created_at':datetime.now(timezone.utc).isoformat(),'input_count':len(summary),
   'missing_inputs':missing,'counts':dict(total),'datasets':summary}
 (outdir/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
 with (outdir/'quality_summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['dataset','metric','value'])
  for ds,data in summary.items():
   for key,value in data['rows'].items():w.writerow([ds,key,value])
   for key,value in data['flags'].items():w.writerow([ds,'flag:'+key,value])
 return manifest
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--input-dir',default='input')
 p.add_argument('--output-dir',default='output')
 p.add_argument('--allow-partial',action='store_true')
 a=p.parse_args()
 print(json.dumps(produce(Path(a.input_dir),Path(a.output_dir),a.allow_partial),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
