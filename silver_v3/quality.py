"""Fail-closed quality gates. Never silently claim clinical mapping verification."""
import re
from decimal import Decimal,InvalidOperation
ICD=re.compile(r'^[A-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?$')
STRENGTH=re.compile(r'^\s*(\d+(?:[.,]\d+)?)\s*(MCG|UG|MG|G|KG|ML|L|IU|UNT|MEQ|MMOL|MCI|%)\s*(?:/\s*(\d+(?:[.,]\d+)?)?\s*(MCG|UG|MG|G|ML|L|EACH|DOSE))?\s*$',re.I)
def numeric_evidence(raw,locale='unknown'):
 s=re.sub(r'\s+','',str(raw or ''))
 if not s:return None,'MISSING_NUMBER'
 if not re.fullmatch(r'\d[\d.,]*',s):return None,'INVALID_NUMBER'
 if ',' in s and '.' in s:
  if locale=='vi' and re.fullmatch(r'\d{1,3}(?:\.\d{3})+,\d+',s):s=s.replace('.','').replace(',','.')
  elif locale=='en' and re.fullmatch(r'\d{1,3}(?:,\d{3})+\.\d+',s):s=s.replace(',','')
  else:return None,'AMBIGUOUS_NUMBER_LOCALE'
 elif s.count('.')+s.count(',')==1:
  sep=',' if ',' in s else '.'
  a,b=s.split(sep)
  if len(b)==3 and a!='0' and len(a)<=3 and locale=='unknown':return None,'AMBIGUOUS_THOUSANDS_DECIMAL'
  if len(b)==3 and a!='0' and len(a)<=3 and ((locale=='vi' and sep=='.') or (locale=='en' and sep==',')):s=a+b
  else:s=a+'.'+b
 elif s.count('.')+s.count(',')>1:
  if locale=='vi' and re.fullmatch(r'\d{1,3}(?:\.\d{3})+',s):s=s.replace('.','')
  elif locale=='en' and re.fullmatch(r'\d{1,3}(?:,\d{3})+',s):s=s.replace(',','')
  else:return None,'AMBIGUOUS_NUMBER_LOCALE'
 try:return Decimal(s),''
 except InvalidOperation:return None,'INVALID_NUMBER'
def strength_signature(raw,locale='unknown'):
 m=STRENGTH.fullmatch(str(raw or ''))
 if not m:return None,'COMPLEX_OR_UNKNOWN_STRENGTH'
 num,flag=numeric_evidence(m.group(1),locale)
 if flag:return None,flag
 u=m.group(2).upper().replace('UG','MCG')
 den=m.group(3);denu=(m.group(4) or '').upper().replace('UG','MCG')
 mass={'MCG':Decimal('.001'),'MG':Decimal(1),'G':Decimal(1000),'KG':Decimal(1000000)}
 vol={'ML':Decimal(1),'L':Decimal(1000)}
 if u in mass:num*=mass[u];u='MG'
 if denu:
  d,flag=numeric_evidence(den or '1',locale)
  if flag or not d:return None,flag or 'ZERO_DENOMINATOR'
  if denu in vol:d*=vol[denu];denu='ML'
  elif denu in mass:d*=mass[denu];denu='MG'
  return num/d,'DIMENSIONLESS' if u==denu else u+'/'+denu
 return num,u
def base_flags(dataset,row):
 f=[]; val=lambda k:str(row.get(k,'') or '').strip()
 if dataset=='dav_component':
  if val('mapping_readiness_v2').startswith('REVIEW') or val('review_reason'):f.append('DAV_EXISTING_REVIEW')
  if not val('ingredient_normalized_candidate'):f.append('MISSING_INGREDIENT')
  if val('strength_normalized'):
   v,reason=strength_signature(val('strength_normalized'))
   if v is None:f.append('STRENGTH_'+reason)
 elif dataset=='dav_mapping':
  status=val('mapping_status').upper()
  if status not in ('VERIFIED_SCD',''):f.append('NOT_VERIFIED_SCD')
  if val('review_required').lower() in ('1','true','yes'):f.append('EXISTING_MAPPING_REVIEW')
  if status=='VERIFIED_SCD' and not val('selected_scd_rxcui'):f.append('VERIFIED_MISSING_RXCUI')
  if val('selected_scd_rxcui') and not val('selected_scd_rxcui').isdigit():f.append('INVALID_SELECTED_RXCUI')
  if re.search(r'\d[,.]\d{3}\b',val('dav_strength_raw')):f.append('AMBIGUOUS_NUMERIC_SEPARATOR')
  if re.search(r'\d\s*[-~]\s*\d',val('dav_strength_raw')):f.append('STRENGTH_RANGE')
 elif dataset=='dav_evidence':
  if val('ingredient_match_method')=='UNMATCHED_INGREDIENT':f.append('UNMATCHED_INGREDIENT')
  if val('component_match_status') not in ('','LINKED_TO_SELECTED_SCD'):f.append('COMPONENT_NEEDS_REVIEW')
 elif dataset=='rxnorm_clean':
  if not val('rxcui').isdigit():f.append('INVALID_RXCUI')
  for k in ('tty','sab','display_name'):
   if not val(k):f.append('MISSING_'+k.upper())
 elif dataset=='icd10_vi':
  if not ICD.fullmatch(val('icd_code_canonical')):f.append('INVALID_ICD10_SYNTAX')
  if val('normalization_status')=='REVIEW':f.append('EXISTING_ICD_REVIEW')
  if val('icd_code_marker'):f.append('ICD_SPECIAL_MARKER')
 elif dataset=='medi2':
  if val('normalization_status')=='REVIEW':f.append('EXISTING_MEDI_REVIEW')
  if not val('rxcui').isdigit():f.append('INVALID_RXCUI')
  if val('code_system')=='ICD10CM':
   f.append('ICD10CM_TO_WHO_VI_EQUIVALENCE_NOT_VERIFIED')
   if val('code_type')!='range' and not ICD.fullmatch(val('code_normalized')):f.append('INVALID_ICD10CM_SYNTAX')
  if val('code_type')=='range':f.append('ICD_RANGE_NOT_EXACT')
 return sorted(set(f))
def decision(ds,row,flags):
 if any(f.startswith('INVALID_') for f in flags):return 'REJECTED'
 if ds in ('dav_mapping','dav_evidence','medi2'):return 'REVIEW_REQUIRED'
 return 'REVIEW_REQUIRED' if flags else 'ACCEPTED'
