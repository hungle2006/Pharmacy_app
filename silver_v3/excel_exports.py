"""Compatibility XLSX exporter for rebuilt DAV and RxNorm mappings."""
import csv
from pathlib import Path
from .legacy_tools.normalize_icd10_vietnam import write_simple_xlsx
def rows_of(path):
 with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def to_rows(records,fields):
 return [[r.get(k,'') for k in fields] for r in records]
def build_compat(out):
 out=Path(out)
 dav=rows_of(out/'dav'/'dav_component_normalized_v2.csv')
 davfields=['dav_row_id','component_order','dav_registration_number','dav_drug_name',
  'ingredient_normalized_candidate','precise_ingredient_raw','strength_normalized',
  'dav_dosage_form_raw','dav_form_group','dav_route_hint','mapping_readiness_v2','review_reason']
 review=[r for r in dav if r.get('mapping_readiness_v2','').startswith('REVIEW')]
 forms=rows_of(out/'dav'/'dav_form_route_v2.csv')
 formfields=['dav_dosage_form_raw','dav_dosage_form_norm_vi','row_count','dav_form_group',
  'dav_route_hint','route_hint_confidence','rxnorm_df_verification_status']
 write_simple_xlsx(out/'DAV_Normalized_v2_for_RxNorm_Mapping.xlsx',[
  ('DAV_COMPONENT',davfields,to_rows(dav,davfields),{}),
  ('REVIEW_QUEUE',davfields,to_rows(review,davfields),{}),
  ('FORM_ROUTE',formfields,to_rows(forms,formfields),{}),
  ('QC',['metric','value'],[['component_rows_total',len(dav)],['review_rows',len(review)]],{})])
 mapped=rows_of(out/'dav_rxnorm'/'dav_rxnorm_product_mapping_full.csv')
 mapfields=['dav_row_id','dav_registration_number','dav_drug_name','dav_active_ingredient_raw',
  'dav_strength_raw','dav_dosage_form_raw','selected_scd_rxcui','selected_scd_name',
  'suggested_scd_rxcui','mapping_status','confidence','review_required']
 with (out/'dav_rxnorm'/'dav_rxnorm_mapping_qc.csv').open(encoding='utf-8-sig',newline='') as f:
  qc=list(csv.reader(f))
 write_simple_xlsx(out/'DAV_RxNorm_Mapping_Products.xlsx',[
  ('DAV_RXNORM_MAPPING',mapfields,to_rows(mapped,mapfields),{}),
  ('QC_SUMMARY',['Metric','Value'],qc[1:],{})])
 evidence=rows_of(out/'dav_rxnorm'/'dav_rxnorm_component_mapping_full.csv')
 fields=['dav_row_id','component_order','dav_registration_number','dav_drug_name',
  'dav_ingredient_component','dav_strength_canonical','ingredient_rxcui',
  'ingredient_rxnorm_name','ingredient_match_method','ingredient_confidence',
  'selected_scd_rxcui','scdc_rxcui','rx_strength','component_match_status']
 write_simple_xlsx(out/'DAV_RxNorm_Component_Evidence.xlsx',[
  ('COMPONENT_EVIDENCE',fields,to_rows(evidence,fields),{})])
 return {'dav_component_count':len(dav),'dav_product_count':len(mapped),'evidence_count':len(evidence)}
