"""PostgreSQL integration tests (CI runs a disposable PostgreSQL service).

Covers reuse of existing eight tables, incremental append/update, price
semantic deduplication, protection of prior human-reviewed RxNorm mappings,
and zero new persistent staging tables.
"""
import csv,os,tempfile,unittest
from pathlib import Path

SCHEMA = """
CREATE TABLE public.dav_product (
 dav_row_id text, registration_number text,drug_name text,active_ingredient_raw text,
 strength_raw text,dosage_form_raw text,package text,unit text,manufacturer text,country text,source text
);
CREATE TABLE public.price_record (
 price_id text,dav_row_id text,declaration_date date,price_vnd bigint,currency text,
 price_type text,unit text,package text,source text
);
CREATE TABLE public.dav_rxnorm_mapping (
 mapping_id text,dav_row_id text,selected_scd_rxcui text,selected_scd_name text,
 suggested_scd_rxcui text,mapping_status text,confidence text,review_required integer,
 evidence_level text,accepted_for_serving integer,selected_scd_fk_valid integer
);
CREATE TABLE public.disease (
 icd_code text,icd_code_nodot text,icd_code3 text,icd_code_marker text,
 disease_name_vi text,disease_name_vi_norm text,disease_name_en text,disease_name_en_norm text,
 code_level text,chapter_code text,chapter_name_vi text,chapter_name_en text,
 section_id text,section_name_vi text,section_name_en text,type_code text,
 type_name_vi text,type_name_en text,normalization_status text,review_reason text,
 source text,source_url text,source_row_count integer
);
CREATE TABLE public.medi_relation (
 medi_relation_id text,source_row_id text,disease_icd_code text,rxcui text,
 drug_description text,code_system text,code_raw text,code_normalized text,
 code_nodot text,code3 text,code_type text,code_range_start text,
 code_range_end text,indication_description text,relation_key text,
 icd_match_status text,rxnorm_match_status text,normalization_status text,review_reason text
);
CREATE TABLE public.rxnorm_concept (
 rxcui text,canonical_name text,canonical_tty text,canonical_sab text,
 tty_set text,sab_set text,term_count integer,is_ingredient integer,is_scd integer,
 used_in_medi integer,concept_status text
);
CREATE TABLE public.rxnorm_scd (
 scd_rxcui text,scd_name text,scd_name_norm text,dose_form_rxcui text,
 dose_form_name text,dose_form_status text,component_count integer,
 matched_component_count integer,component_status text,sab text
);
CREATE TABLE public.rxnorm_scd_component (
 scd_component_id text,scd_rxcui text,component_order integer,scdc_rxcui text,
 scdc_name text,ingredient_rxcui text,ingredient_name text,ingredient_tty text,
 strength_text text,scdc_parse_status text,relation_status text,
 component_raw text,component_clean text,sab text
);
"""

def csv_file(folder,label,rows):
 from gold_auto.sync import HEADERS
 headers=sorted(HEADERS[label])
 path=Path(folder)/(label+".csv")
 with path.open("w",newline="",encoding="utf-8") as output:
  writer=csv.DictWriter(output,fieldnames=headers)
  writer.writeheader()
  writer.writerows(rows)
 return path

@unittest.skipUnless(os.getenv("GOLD_TEST_DSN"),"PostgreSQL service is only required in CI")
class GoldIntegrationTest(unittest.TestCase):
 def test_upsert_existing_tables_without_duplicates(self):
  import psycopg
  from gold_auto.sync import write_gold
  url=os.environ["GOLD_TEST_DSN"]
  with psycopg.connect(url) as db:
   with db.cursor() as cur:
    cur.execute(SCHEMA)
    cur.execute("""INSERT INTO dav_product
     (dav_row_id,drug_name) VALUES ('1','Old drug name')""")
    cur.execute("""INSERT INTO price_record
     (price_id,dav_row_id,declaration_date,price_vnd,currency,price_type,unit,package,source)
     VALUES ('legacy-price','1','2026-10-20',5000,'VND','KKL','viên','Hộp','DAV')""")
    cur.execute("""INSERT INTO dav_rxnorm_mapping
     (mapping_id,dav_row_id,selected_scd_rxcui,mapping_status,accepted_for_serving)
     VALUES ('legacy-mapping','1','103','VERIFIED_SCD',1)""")
   db.commit()
  with tempfile.TemporaryDirectory() as tmp:
   fixtures={
    "dav":[{
     "dav_row_id":"1","dav_drug_name":"Paracetamol 500",
     "dav_registration_number":"VD001","dav_active_ingredient_raw":"acetaminophen",
     "dav_strength":"500 MG","dav_dosage_form":"Viên nén","dav_price_vnd":"5000.0",
     "dav_declaration_date":"2026-10-20T09:00:00+07:00","dav_price_type":"KKL",
     "dav_package":"Hộp","dav_unit":"viên","dav_manufacturer":"Test Company",
     "dav_country":"Việt Nam","silver_qc_status":"ACCEPTED"
    },{
     "dav_row_id":"2","dav_drug_name":"Second drug","dav_registration_number":"VD002",
     "dav_active_ingredient_raw":"ibuprofen","dav_strength":"200 MG",
     "dav_dosage_form":"Viên nén","dav_price_vnd":"3200",
     "dav_declaration_date":"2026-10-20T10:00:00+07:00","dav_price_type":"KKL",
     "dav_package":"Hộp","dav_unit":"viên","dav_manufacturer":"Test Company",
     "dav_country":"Việt Nam","silver_qc_status":"REVIEW_REQUIRED"
    }],
    "rxnorm":[
     {"rxcui":"100","tty":"IN","sab":"RXNORM","display_name":"acetaminophen"},
     {"rxcui":"101","tty":"SCDC","sab":"RXNORM","display_name":"acetaminophen 500 MG"},
     {"rxcui":"103","tty":"SCD","sab":"RXNORM","display_name":"acetaminophen 500 MG Oral Tablet"}],
    "icd":[{"silver_code_canonical":"N30","name_vi":"Viêm bàng quang",
      "name_en":"Cystitis","model":"disease","silver_qc_status":"ACCEPTED",
      "silver_qc_flags":"","source":"ICD10_VIETNAM"}],
    "scd":[{"scd_rxcui":"103","scd_name":"acetaminophen 500 MG Oral Tablet",
      "dose_form_rxcui":"1000","dose_form_name":"Oral Tablet","component_order":"1",
      "scdc_rxcui":"101","scdc_name":"acetaminophen 500 MG",
      "ingredient_rxcui":"100","ingredient_name":"acetaminophen",
      "component_strength":"500 MG","component_raw":"acetaminophen 500 MG",
      "relation_status":"TEXT_INFERRED_REVIEW","evidence_method":"TERM_PARSE","clinical_verified":"false"}],
    "mapping":[
      {"dav_row_id":"1","candidate_scd_rxcui":"103",
       "candidate_scd_name":"acetaminophen 500 MG Oral Tablet",
       "mapping_status":"CANDIDATE_REVIEW","review_reason":"RXNREL_NOT_VALIDATED"},
      {"dav_row_id":"2","candidate_scd_rxcui":"",
       "mapping_status":"UNMATCHED_REVIEW","review_reason":"NO_MATCH"}],
    "evidence":[
      {"dav_row_id":"1","component_order":"1","component_raw":"acetaminophen",
       "ingredient_candidate_rxcui":"100","ingredient_candidate_name":"acetaminophen",
       "ingredient_search_name":"acetaminophen","candidate_count":"1",
       "evidence_status":"CANDIDATE_REVIEW","clinical_verified":"false"},
      {"dav_row_id":"2","component_order":"1","component_raw":"ibuprofen",
       "candidate_count":"0","evidence_status":"REVIEW_REQUIRED","clinical_verified":"false"}],
    "medi":[{"medi_rxcui":"100","medi_drug_description":"acetaminophen",
      "medi_vocabulary":"ICD10CM","medi_code":"N30",
      "medi_indication_description":"Cystitis","mapping_status":"CROSS_CODE_SYSTEM_REVIEW",
      "review_reason":"NO_OFFICIAL_CROSSWALK","rxcui_found_in_rxnorm":"true",
      "clinical_verified":"false"}],
   }
   paths={k:csv_file(tmp,k,values) for k,values in fixtures.items()}
   checks={k:{"sha256":"test-sha256-"+k} for k in fixtures}
   first=write_gold(paths,checks,url)
   second=write_gold(paths,checks,url)
   with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
     cur.execute("SELECT COUNT(*) FROM public.dav_product")
     self.assertEqual(cur.fetchone()[0],2)
     cur.execute("SELECT drug_name FROM public.dav_product WHERE dav_row_id='1'")
     self.assertEqual(cur.fetchone()[0],"Paracetamol 500")
     cur.execute("SELECT COUNT(*) FROM public.price_record")
     self.assertEqual(cur.fetchone()[0],2) # prior identical price remains one + one genuinely new
     cur.execute("SELECT COUNT(*) FROM public.dav_rxnorm_mapping")
     self.assertEqual(cur.fetchone()[0],2)
     cur.execute("""SELECT selected_scd_rxcui,mapping_status,accepted_for_serving
      FROM public.dav_rxnorm_mapping WHERE dav_row_id='1'""")
     self.assertEqual(cur.fetchone(),("103","VERIFIED_SCD",1))
     cur.execute("SELECT COUNT(*) FROM public.dav_rxnorm_evidence")
     self.assertEqual(cur.fetchone()[0],2)
     cur.execute("SELECT COUNT(*) FROM public.rxnorm_scd_component")
     self.assertEqual(cur.fetchone()[0],1)
     cur.execute("SELECT COUNT(*) FROM public.medi_relation")
     self.assertEqual(cur.fetchone()[0],1)
     cur.execute("SELECT disease_icd_code FROM medi_relation")
     self.assertIsNone(cur.fetchone()[0])
     cur.execute("""SELECT COUNT(*) FROM information_schema.tables
      WHERE table_schema='public'""")
     self.assertEqual(cur.fetchone()[0],9)
   self.assertEqual(sum(v for k,v in second.items() if k.startswith("changed_")),0)
if __name__=="__main__":unittest.main()
