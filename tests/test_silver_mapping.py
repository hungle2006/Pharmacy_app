import csv
import tempfile
import unittest
from pathlib import Path

from silver_mapping.build import build_all,OUTPUTS,strength,split_ingredients

def write(path, fields, items):
 with path.open('w',encoding='utf-8',newline='') as output:
  w=csv.DictWriter(output,fieldnames=fields)
  w.writeheader()
  w.writerows(items)

class MappingTests(unittest.TestCase):
 def test_safe_strength(self):
  self.assertEqual(strength('500 MG'),('5E+2','MG'))
  self.assertEqual(strength('5 MG/5ML'),('1','MG/ML'))
  self.assertIsNone(strength('1.000 MG'))
  self.assertEqual(split_ingredients('A + B; C'),['A','B','C'])
 def test_candidate_mapping_and_legacy_code_system_warning(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   write(p/'rx.csv',['rxcui','tty','sab','display_name','normalized_name'],[
    {'rxcui':'100','tty':'IN','sab':'RXNORM','display_name':'acetaminophen'},
    {'rxcui':'101','tty':'SCDC','sab':'RXNORM','display_name':'acetaminophen 500 MG'},
    {'rxcui':'102','tty':'DF','sab':'RXNORM','display_name':'Oral Tablet'},
    {'rxcui':'103','tty':'SCD','sab':'RXNORM','display_name':'acetaminophen 500 MG Oral Tablet'}])
   write(p/'dav.csv',['dav_row_id','dav_drug_name','dav_active_ingredient_raw','dav_strength','dav_dosage_form'],[
    {'dav_row_id':'1','dav_drug_name':'Thuốc mẫu','dav_active_ingredient_raw':'paracetamol','dav_strength':'500 MG','dav_dosage_form':'Viên nén'},
    {'dav_row_id':'2','dav_drug_name':'Thuốc phối hợp','dav_active_ingredient_raw':'paracetamol + ibuprofen','dav_strength':'','dav_dosage_form':'Viên nén'}])
   write(p/'icd.csv',['id','code','name_vi','silver_code_canonical'],[
    {'id':'N30','code':'N30','name_vi':'Viêm bàng quang','silver_code_canonical':'N30'}])
   write(p/'medi.csv',['RXCUI','DRUG_DESCRIPTION','VOCABULARY','CODE','INDICATION_DESCRIPTION'],[
    {'RXCUI':'100','DRUG_DESCRIPTION':'acetaminophen','VOCABULARY':'ICD10CM','CODE':'N30','INDICATION_DESCRIPTION':'Cystitis'},
    {'RXCUI':'100','DRUG_DESCRIPTION':'acetaminophen','VOCABULARY':'ICD9CM','CODE':'595','INDICATION_DESCRIPTION':'Cystitis'}])
   stats=build_all(p/'dav.csv',p/'rx.csv',p/'icd.csv',p/'outputs',medi=p/'medi.csv')
   self.assertEqual(set(stats['rows']),set(OUTPUTS))
   self.assertEqual(stats['rows']['dav_rxnorm_mapping'],2)
   self.assertEqual(stats['rows']['medi_icd10_mapping'],2)
   with (p/'outputs'/'dav_rxnorm_mapping.csv').open() as f:m=list(csv.DictReader(f))
   self.assertEqual(m[0]['candidate_scd_rxcui'],'103')
   self.assertEqual(m[0]['clinical_verified'],'false')
   self.assertEqual(m[0]['mapping_status'],'CANDIDATE_REVIEW')
   self.assertEqual(m[1]['candidate_scd_rxcui'],'')
   with (p/'outputs'/'medi_icd10_mapping.csv').open() as f:med=list(csv.DictReader(f))
   self.assertEqual(med[0]['mapping_status'],'CROSS_CODE_SYSTEM_REVIEW')
   self.assertEqual(med[0]['clinical_verified'],'false')
   self.assertEqual(med[1]['candidate_icd10_vi_code'],'')
   for name in OUTPUTS:
    self.assertTrue((p/'outputs'/(name+'.csv')).exists())
 def test_unmatched_is_not_fabricated(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   write(p/'rx.csv',['rxcui','tty','sab','display_name','normalized_name'],[
    {'rxcui':'1','tty':'IN','sab':'RXNORM','display_name':'acetaminophen'},
    {'rxcui':'2','tty':'SCDC','sab':'RXNORM','display_name':'acetaminophen 5 MG'},
    {'rxcui':'3','tty':'DF','sab':'RXNORM','display_name':'Oral Tablet'},
    {'rxcui':'4','tty':'SCD','sab':'RXNORM','display_name':'acetaminophen 5 MG Oral Tablet'}])
   write(p/'dav.csv',['dav_row_id','dav_active_ingredient_raw','dav_strength','dav_dosage_form'],[
    {'dav_row_id':'x','dav_active_ingredient_raw':'UNKNOWN SALT','dav_strength':'5 MG','dav_dosage_form':'Viên nén'}])
   write(p/'icd.csv',['id','code','name_vi'],[{'id':'A00','code':'A00','name_vi':'Tả'}])
   build_all(p/'dav.csv',p/'rx.csv',p/'icd.csv',p/'out')
   with (p/'out'/'dav_rxnorm_mapping.csv').open() as f:
    row=next(csv.DictReader(f))
   self.assertEqual(row['candidate_scd_rxcui'],'')
   self.assertEqual(row['mapping_status'],'UNMATCHED_REVIEW')
if __name__=='__main__':unittest.main()
