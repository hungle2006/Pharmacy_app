"""Rebuild input normalizations from original, source-complete raw files.
These raw files were not all uploaded in the chat and are required at runtime.
"""
import argparse,csv,json,subprocess,sys
from collections import defaultdict
from pathlib import Path
from .xlsx_source import stream_rows
ROOT=Path(__file__).parent
def run(script,*args):
 subprocess.run([sys.executable,str(ROOT/'safe_tools'/script),*map(str,args)],check=True)
def write_csv(path,headers,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore');w.writeheader();w.writerows(rows)
def rxnorm_mapper_inputs(rxnorm_xlsx,output_dir):
 output_dir.mkdir(parents=True,exist_ok=True)
 scds={r['scd_rxcui']:r for r in stream_rows(rxnorm_xlsx,'03_Clinical_Drug_SCD')}
 scdcs={r['scdc_rxcui']:r for r in stream_rows(rxnorm_xlsx,'02_Component_SCDC')}
 forms={r['scd_rxcui']:r for r in stream_rows(rxnorm_xlsx,'06_SCD_Dose_Form_Rel')}
 rels=defaultdict(list)
 for r in stream_rows(rxnorm_xlsx,'05_SCD_Component_Rel'):rels[r['scd_rxcui']].append(r)
 out=[];review=[]
 headers=['scd_rxcui','scd_name','dose_form_rxcui','dose_form_rxnorm','scdc_rxcui','ingredient_rxcui','strength_rxnorm']
 for rid,scd in scds.items():
  links=rels.get(rid,[])
  try:expected=int(float(scd.get('component_count') or '0'))
  except ValueError:expected=0
  if not links or len(links)!=expected or scd.get('component_status')!='ALL_COMPONENTS_EXACT':
   review.append({'scd_rxcui':rid,'review_reason':'INCOMPLETE_COMPONENT_SET'});continue
  form=forms.get(rid,{})
  if not form.get('dose_form_name'):
   review.append({'scd_rxcui':rid,'review_reason':'MISSING_DOSE_FORM'});continue
  rows=[]
  for link in links:
   scdc=scdcs.get(link.get('scdc_rxcui',''),{})
   if not scdc.get('ingredient_rxcui') or not scdc.get('strength_text'):
    rows=[];break
   rows.append({'scd_rxcui':rid,'scd_name':scd.get('scd_name',''),
     'dose_form_rxcui':form.get('dose_form_rxcui',''),
     'dose_form_rxnorm':form.get('dose_form_name',''),
     'scdc_rxcui':link['scdc_rxcui'],
     'ingredient_rxcui':scdc['ingredient_rxcui'],'strength_rxnorm':scdc['strength_text']})
  if rows:out.extend(rows)
  else:review.append({'scd_rxcui':rid,'review_reason':'UNRESOLVED_SCDC_COMPONENT'})
 scd_path=output_dir/'rxnorm_scd_mapping_ready.csv';write_csv(scd_path,headers,out)
 def clean():
  for row in stream_rows(rxnorm_xlsx,'00_Clean_Normalized'):
   yield {'rxcui':row.get('rxcui',''),'tty':row.get('tty',''),
    'sab':row.get('sab',''),'display_name':row.get('display_name',''),
    'normalized_name':row.get('normalized_name_source') or row.get('display_name','')}
 cleaned=output_dir/'rxnorm_clean.csv'
 write_csv(cleaned,['rxcui','tty','sab','display_name','normalized_name'],clean())
 write_csv(output_dir/'rxnorm_scd_excluded_review.csv',['scd_rxcui','review_reason'],review)
 (output_dir/'rxnorm_extract_qc.json').write_text(json.dumps({
    'candidate_component_rows':len(out),'excluded_scd_count':len(review)},indent=2))
 return scd_path,cleaned
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--dav-csv',type=Path,required=True)
 p.add_argument('--rxnorm-raw-xlsx',type=Path,required=True)
 p.add_argument('--icd10-vietnam-raw-xlsx',type=Path,required=True)
 p.add_argument('--medi2-raw-xlsx',type=Path,required=True)
 p.add_argument('--dav-component-csv',type=Path)
 p.add_argument('--output-dir',type=Path,default=Path('rebuilt'))
 a=p.parse_args();out=a.output_dir;out.mkdir(parents=True,exist_ok=True)
 sources=[a.dav_csv,a.rxnorm_raw_xlsx,a.icd10_vietnam_raw_xlsx,a.medi2_raw_xlsx]
 if a.dav_component_csv:sources.append(a.dav_component_csv)
 missing=[str(f) for f in sources if not f.is_file()]
 if missing:raise FileNotFoundError('Missing raw input(s): '+', '.join(missing))
 from .legacy_tools.rxnorm_normalize import run_pipeline
 rx=out/'rxnorm_output.xlsx';run_pipeline(str(a.rxnorm_raw_xlsx),str(rx))
 davdir=out/'dav';params=['--dav',str(a.dav_csv),'--output-dir',str(davdir)]
 if a.dav_component_csv:params+=['--components',str(a.dav_component_csv)]
 run('dav_normalizer_v3.py',*params)
 run('normalize_icd10_vietnam.py','--input',a.icd10_vietnam_raw_xlsx,'--output-dir',out/'icd10_vi')
 run('normalize_medi2_hps_v3.py','--input',a.medi2_raw_xlsx,'--output-dir',out/'medi2')
 scd,cleaned=rxnorm_mapper_inputs(rx,out/'rxnorm_mapping_inputs')
 run('dav_rxnorm_mapper_v3.py',
  '--dav-product',davdir/'dav_product_normalized_v2.csv',
  '--dav-component',davdir/'dav_component_normalized_v2.csv',
  '--rxnorm-scd',scd,'--rxnorm-clean',cleaned,'--output-dir',out/'dav_rxnorm')
 print('Done. Review outputs before any clinical mapping approval.')
if __name__=='__main__':main()
