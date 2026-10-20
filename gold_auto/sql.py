"""Gold PostgreSQL SQL. Extend existing tables, never persist staging snapshots."""
from __future__ import annotations

# All public table names and columns are grounded in PharmaBiz /api/insights.
# New columns are additive. No DROP TABLE, TRUNCATE, or DELETE operations.
ALTERATIONS = {
    "dav_product": [
        ("silver_qc_status","TEXT"),
        ("silver_source_sha","TEXT"),
    ],
    "price_record": [("silver_source_sha","TEXT")],
    "dav_rxnorm_mapping": [
        ("silver_mapping_status","TEXT"),
        ("candidate_scd_name","TEXT"),
        ("review_reason","TEXT"),
        ("silver_source_sha","TEXT"),
    ],
    "disease": [
        ("silver_qc_status","TEXT"),
        ("silver_source_sha","TEXT"),
    ],
    "rxnorm_concept": [("silver_source_sha","TEXT")],
    "rxnorm_scd": [
        ("evidence_method","TEXT"),
        ("silver_source_sha","TEXT"),
    ],
    "rxnorm_scd_component": [
        ("evidence_method","TEXT"),
        ("silver_source_sha","TEXT"),
    ],
    "medi_relation": [
        ("silver_source_sha","TEXT"),
        ("crosswalk_review_status","TEXT"),
    ],
}
UNIQUES = (
    ("dav_product", ("dav_row_id",)),
    ("price_record", ("price_id",)),
    ("dav_rxnorm_mapping", ("dav_row_id",)),
    ("disease", ("icd_code",)),
    ("rxnorm_concept", ("rxcui",)),
    ("rxnorm_scd", ("scd_rxcui",)),
    ("rxnorm_scd_component", ("scd_rxcui","component_order")),
    ("medi_relation", ("medi_relation_id",)),
)
# Only ONE genuinely new table; no persistent ETL staging, no accumulating snapshots.
EVIDENCE_DDL = """
CREATE TABLE IF NOT EXISTS public.dav_rxnorm_evidence (
    dav_row_id TEXT NOT NULL,
    component_order INTEGER NOT NULL,
    component_raw TEXT,
    ingredient_search_name TEXT,
    ingredient_candidate_rxcui TEXT,
    ingredient_candidate_name TEXT,
    ingredient_candidate_tty TEXT,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    match_method TEXT,
    evidence_status TEXT,
    review_reason TEXT,
    clinical_verified BOOLEAN NOT NULL DEFAULT FALSE,
    silver_source_sha TEXT,
    PRIMARY KEY (dav_row_id, component_order)
)
"""

# Every statement updates existing rows only when mapped values actually changed.
# Mapping selected_scd_* and accepted_for_serving remain untouched for old rows.
STATEMENTS = [
("dav_product", """
WITH src AS (
 SELECT NULLIF(TRIM(dav_row_id),'') AS dav_row_id,
        NULLIF(TRIM(dav_drug_name),'') AS drug_name,
        NULLIF(TRIM(dav_registration_number),'') AS registration_number,
        NULLIF(TRIM(dav_active_ingredient_raw),'') AS active_ingredient_raw,
        NULLIF(TRIM(dav_strength),'') AS strength_raw,
        NULLIF(TRIM(dav_dosage_form),'') AS dosage_form_raw,
        NULLIF(TRIM(dav_package),'') AS package,
        NULLIF(TRIM(dav_unit),'') AS unit,
        NULLIF(TRIM(dav_manufacturer),'') AS manufacturer,
        NULLIF(TRIM(dav_country),'') AS country,
        NULLIF(TRIM(silver_qc_status),'') AS silver_qc_status
 FROM gold_stg_dav
)
INSERT INTO public.dav_product
(dav_row_id, drug_name, registration_number, active_ingredient_raw,
 strength_raw, dosage_form_raw, package, unit, manufacturer, country, source,
 silver_qc_status, silver_source_sha)
SELECT dav_row_id, drug_name, registration_number, active_ingredient_raw,
       strength_raw, dosage_form_raw, package, unit, manufacturer, country, 'SILVER_R2',
       silver_qc_status, %(source_sha)s
FROM src WHERE dav_row_id IS NOT NULL
ON CONFLICT (dav_row_id) DO UPDATE SET
 drug_name=EXCLUDED.drug_name, registration_number=EXCLUDED.registration_number,
 active_ingredient_raw=EXCLUDED.active_ingredient_raw, strength_raw=EXCLUDED.strength_raw,
 dosage_form_raw=EXCLUDED.dosage_form_raw, package=EXCLUDED.package, unit=EXCLUDED.unit,
 manufacturer=EXCLUDED.manufacturer, country=EXCLUDED.country,
 silver_qc_status=EXCLUDED.silver_qc_status, silver_source_sha=EXCLUDED.silver_source_sha
WHERE (dav_product.drug_name, dav_product.registration_number, dav_product.active_ingredient_raw,
       dav_product.strength_raw, dav_product.dosage_form_raw, dav_product.package, dav_product.unit,
       dav_product.manufacturer, dav_product.country, dav_product.silver_qc_status)
 IS DISTINCT FROM
      (EXCLUDED.drug_name, EXCLUDED.registration_number, EXCLUDED.active_ingredient_raw,
       EXCLUDED.strength_raw, EXCLUDED.dosage_form_raw, EXCLUDED.package, EXCLUDED.unit,
       EXCLUDED.manufacturer, EXCLUDED.country, EXCLUDED.silver_qc_status)
"""),
("price_record", """
WITH src AS (
 SELECT NULLIF(TRIM(dav_row_id),'') AS dav_row_id,
        CASE WHEN TRIM(dav_price_vnd) ~ '^[0-9]{1,15}(\\.0+)?$'
             THEN TRIM(dav_price_vnd)::numeric::bigint ELSE NULL END AS price_vnd,
        CASE WHEN TRIM(dav_declaration_date) ~ '^\\d{4}-\\d{2}-\\d{2}'
             THEN SUBSTRING(TRIM(dav_declaration_date) FROM 1 FOR 10)::date ELSE NULL END AS declaration_date,
        NULLIF(TRIM(dav_price_type),'') AS price_type,
        NULLIF(TRIM(dav_unit),'') AS unit,
        NULLIF(TRIM(dav_package),'') AS package
 FROM gold_stg_dav
), clean AS (
 SELECT DISTINCT dav_row_id,price_vnd,declaration_date,price_type,unit,package
 FROM src WHERE dav_row_id IS NOT NULL AND price_vnd IS NOT NULL
)
INSERT INTO public.price_record
(price_id,dav_row_id,declaration_date,price_vnd,currency,price_type,unit,package,source,silver_source_sha)
SELECT 'slv:'||md5(concat_ws('|',s.dav_row_id,COALESCE(s.declaration_date::text,''),
                          s.price_vnd::text,COALESCE(s.price_type,''),
                          COALESCE(s.unit,''),COALESCE(s.package,''))),
       s.dav_row_id,s.declaration_date,s.price_vnd,'VND',s.price_type,s.unit,s.package,
       'SILVER_DAV_PRICE', %(source_sha)s
FROM clean s
WHERE EXISTS (SELECT 1 FROM public.dav_product d WHERE d.dav_row_id=s.dav_row_id)
  AND NOT EXISTS (
   SELECT 1 FROM public.price_record p
   WHERE p.dav_row_id=s.dav_row_id AND p.price_vnd=s.price_vnd
     AND p.declaration_date IS NOT DISTINCT FROM s.declaration_date
     AND p.price_type IS NOT DISTINCT FROM s.price_type
     AND p.unit IS NOT DISTINCT FROM s.unit
     AND p.package IS NOT DISTINCT FROM s.package)
ON CONFLICT (price_id) DO NOTHING
"""),
("disease", """
WITH candidates AS (
 SELECT NULLIF(UPPER(TRIM(silver_code_canonical)),'') AS icd_code,
        NULLIF(TRIM(name_vi),'') AS disease_name_vi,
        NULLIF(TRIM(name_en),'') AS disease_name_en,
        NULLIF(TRIM(model),'') AS code_level,
        NULLIF(TRIM(silver_qc_status),'') AS normalization_status,
        NULLIF(TRIM(silver_qc_flags),'') AS review_reason,
        NULLIF(TRIM(source),'') AS source
 FROM gold_stg_icd
), unique_codes AS (
 SELECT DISTINCT ON (icd_code) *
 FROM candidates
 WHERE icd_code ~ '^[A-Z][0-9]{2}(\\.[0-9A-Z]{1,4})?$'
 ORDER BY icd_code, (disease_name_vi IS NOT NULL) DESC, (disease_name_en IS NOT NULL) DESC
)
INSERT INTO public.disease
(icd_code,icd_code_nodot,icd_code3,disease_name_vi,disease_name_en,
 code_level,normalization_status,review_reason,source,silver_qc_status,silver_source_sha)
SELECT icd_code,REPLACE(icd_code,'.',''),LEFT(icd_code,3),disease_name_vi,disease_name_en,
       code_level,normalization_status,review_reason,COALESCE(source,'ICD10_VIETNAM'),
       normalization_status,%(source_sha)s
FROM unique_codes
ON CONFLICT (icd_code) DO UPDATE SET
 disease_name_vi=COALESCE(EXCLUDED.disease_name_vi,disease.disease_name_vi),
 disease_name_en=COALESCE(EXCLUDED.disease_name_en,disease.disease_name_en),
 code_level=COALESCE(EXCLUDED.code_level,disease.code_level),
 normalization_status=EXCLUDED.normalization_status,
 silver_qc_status=EXCLUDED.silver_qc_status,
 silver_source_sha=EXCLUDED.silver_source_sha
WHERE (disease.disease_name_vi,disease.disease_name_en,disease.code_level,disease.silver_qc_status)
 IS DISTINCT FROM
      (COALESCE(EXCLUDED.disease_name_vi,disease.disease_name_vi),
       COALESCE(EXCLUDED.disease_name_en,disease.disease_name_en),
       COALESCE(EXCLUDED.code_level,disease.code_level),EXCLUDED.silver_qc_status)
"""),
("rxnorm_concept", """
WITH canonical AS (
 SELECT NULLIF(TRIM(rxcui),'') AS rxcui, NULLIF(TRIM(display_name),'') AS display_name,
        NULLIF(TRIM(tty),'') AS tty, NULLIF(TRIM(sab),'') AS sab
 FROM gold_stg_rxnorm
 WHERE TRIM(rxcui) ~ '^[0-9]+$'
), agg AS (
 SELECT rxcui, string_agg(DISTINCT tty, ',' ORDER BY tty) AS tty_set,
        string_agg(DISTINCT sab, ',' ORDER BY sab) AS sab_set,
        COUNT(*)::integer AS term_count,
        MAX(CASE WHEN tty IN ('IN','PIN') THEN 1 ELSE 0 END)::integer AS is_ingredient,
        MAX(CASE WHEN tty='SCD' THEN 1 ELSE 0 END)::integer AS is_scd
 FROM canonical GROUP BY rxcui
), preferred AS (
 SELECT DISTINCT ON (rxcui) rxcui, display_name,tty,sab
 FROM canonical
 ORDER BY rxcui,
 CASE tty WHEN 'IN' THEN 0 WHEN 'PIN' THEN 1 WHEN 'SCD' THEN 2
 WHEN 'SCDC' THEN 3 WHEN 'DF' THEN 4 ELSE 9 END,display_name
)
INSERT INTO public.rxnorm_concept
(rxcui, canonical_name, canonical_tty, canonical_sab, tty_set, sab_set,term_count,
 is_ingredient,is_scd,concept_status,silver_source_sha)
SELECT p.rxcui,p.display_name,p.tty,p.sab,a.tty_set,a.sab_set,a.term_count,
       a.is_ingredient,a.is_scd,'SOURCE_TERMINOLOGY',%(source_sha)s
FROM preferred p JOIN agg a USING (rxcui)
ON CONFLICT (rxcui) DO UPDATE SET
 canonical_name=EXCLUDED.canonical_name,canonical_tty=EXCLUDED.canonical_tty,
 canonical_sab=EXCLUDED.canonical_sab,tty_set=EXCLUDED.tty_set,sab_set=EXCLUDED.sab_set,
 term_count=EXCLUDED.term_count,is_ingredient=EXCLUDED.is_ingredient,is_scd=EXCLUDED.is_scd,
 silver_source_sha=EXCLUDED.silver_source_sha
WHERE (rxnorm_concept.canonical_name,rxnorm_concept.canonical_tty,rxnorm_concept.canonical_sab,
       rxnorm_concept.tty_set,rxnorm_concept.sab_set,rxnorm_concept.term_count,
       rxnorm_concept.is_ingredient,rxnorm_concept.is_scd)
 IS DISTINCT FROM
      (EXCLUDED.canonical_name,EXCLUDED.canonical_tty,EXCLUDED.canonical_sab,
       EXCLUDED.tty_set,EXCLUDED.sab_set,EXCLUDED.term_count,
       EXCLUDED.is_ingredient,EXCLUDED.is_scd)
"""),
("rxnorm_scd", """
WITH grouped AS (
 SELECT scd_rxcui,MIN(scd_name) AS scd_name,
        MIN(NULLIF(dose_form_rxcui,'')) AS dose_form_rxcui,
        MIN(NULLIF(dose_form_name,'')) AS dose_form_name,
        COUNT(DISTINCT component_order)::integer AS component_count,
        COUNT(DISTINCT component_order)
          FILTER (WHERE relation_status='TEXT_INFERRED_REVIEW')::integer AS matched_component_count
 FROM gold_stg_scd WHERE scd_rxcui~'^[0-9]+$'
 GROUP BY scd_rxcui
)
INSERT INTO public.rxnorm_scd
(scd_rxcui,scd_name,scd_name_norm,dose_form_rxcui,dose_form_name,dose_form_status,
 component_count,matched_component_count,component_status,sab,evidence_method,silver_source_sha)
SELECT scd_rxcui,scd_name,LOWER(scd_name),dose_form_rxcui,dose_form_name,
       'TEXT_INFERRED_REVIEW',component_count,matched_component_count,
       'TEXT_INFERRED_REVIEW','RXNORM','EXACT_NAME_PARSE_NOT_OFFICIAL_RXNREL',%(source_sha)s
FROM grouped
ON CONFLICT (scd_rxcui) DO UPDATE SET
 scd_name=EXCLUDED.scd_name,scd_name_norm=EXCLUDED.scd_name_norm,
 dose_form_rxcui=EXCLUDED.dose_form_rxcui,dose_form_name=EXCLUDED.dose_form_name,
 component_count=EXCLUDED.component_count,matched_component_count=EXCLUDED.matched_component_count,
 evidence_method=EXCLUDED.evidence_method,silver_source_sha=EXCLUDED.silver_source_sha
WHERE COALESCE(rxnorm_scd.component_status,'') IN ('','REVIEW','TEXT_INFERRED_REVIEW')
  AND (rxnorm_scd.scd_name,rxnorm_scd.dose_form_name,
       rxnorm_scd.component_count,rxnorm_scd.matched_component_count)
 IS DISTINCT FROM
      (EXCLUDED.scd_name,EXCLUDED.dose_form_name,
       EXCLUDED.component_count,EXCLUDED.matched_component_count)
"""),
("rxnorm_scd_component", """
WITH raw AS (
 SELECT scd_rxcui,component_order::integer AS component_order,
        NULLIF(scdc_rxcui,'') AS scdc_rxcui,NULLIF(scdc_name,'') AS scdc_name,
        NULLIF(ingredient_rxcui,'') AS ingredient_rxcui,
        NULLIF(ingredient_name,'') AS ingredient_name,
        NULLIF(component_strength,'') AS strength_text,
        NULLIF(component_raw,'') AS component_raw,
        NULLIF(relation_status,'') AS relation_status,
        NULLIF(evidence_method,'') AS evidence_method
 FROM gold_stg_scd
 WHERE scd_rxcui~'^[0-9]+$' AND component_order~'^[0-9]+$'
), unique_lines AS (
 SELECT DISTINCT ON (scd_rxcui,component_order) *
 FROM raw ORDER BY scd_rxcui,component_order,(scdc_rxcui IS NOT NULL) DESC,scdc_name
)
INSERT INTO public.rxnorm_scd_component
(scd_component_id,scd_rxcui,component_order,scdc_rxcui,scdc_name,ingredient_rxcui,
 ingredient_name,ingredient_tty,strength_text,scdc_parse_status,relation_status,
 component_raw,component_clean,sab,evidence_method,silver_source_sha)
SELECT 'slv:'||md5(scd_rxcui||':'||component_order::text),
       scd_rxcui,component_order,scdc_rxcui,scdc_name,ingredient_rxcui,ingredient_name,
       NULL,strength_text,'TEXT_INFERRED_REVIEW',relation_status,
       component_raw,component_raw,'RXNORM',evidence_method,%(source_sha)s
FROM unique_lines
WHERE EXISTS(SELECT 1 FROM public.rxnorm_scd s WHERE s.scd_rxcui=unique_lines.scd_rxcui)
ON CONFLICT (scd_rxcui,component_order) DO UPDATE SET
 scdc_rxcui=EXCLUDED.scdc_rxcui,scdc_name=EXCLUDED.scdc_name,
 ingredient_rxcui=EXCLUDED.ingredient_rxcui,ingredient_name=EXCLUDED.ingredient_name,
 strength_text=EXCLUDED.strength_text,component_raw=EXCLUDED.component_raw,
 evidence_method=EXCLUDED.evidence_method,silver_source_sha=EXCLUDED.silver_source_sha
WHERE COALESCE(rxnorm_scd_component.relation_status,'') IN ('','REVIEW','TEXT_INFERRED_REVIEW','UNRESOLVED_REVIEW')
  AND (rxnorm_scd_component.scdc_rxcui,rxnorm_scd_component.ingredient_rxcui,
       rxnorm_scd_component.strength_text,rxnorm_scd_component.component_raw)
 IS DISTINCT FROM
      (EXCLUDED.scdc_rxcui,EXCLUDED.ingredient_rxcui,
       EXCLUDED.strength_text,EXCLUDED.component_raw)
"""),
("dav_rxnorm_mapping", """
WITH source AS (
 SELECT NULLIF(TRIM(dav_row_id),'') AS dav_row_id,
        NULLIF(TRIM(candidate_scd_rxcui),'') AS suggested_scd_rxcui,
        NULLIF(TRIM(candidate_scd_name),'') AS candidate_scd_name,
        NULLIF(TRIM(mapping_status),'') AS mapping_status,
        NULLIF(TRIM(review_reason),'') AS review_reason
 FROM gold_stg_mapping
)
INSERT INTO public.dav_rxnorm_mapping
(mapping_id,dav_row_id,selected_scd_rxcui,selected_scd_name,suggested_scd_rxcui,
 mapping_status,confidence,review_required,evidence_level,accepted_for_serving,
 selected_scd_fk_valid,silver_mapping_status,candidate_scd_name,review_reason,silver_source_sha)
SELECT 'slv:'||md5(s.dav_row_id),s.dav_row_id,NULL,NULL,s.suggested_scd_rxcui,
       COALESCE(s.mapping_status,'UNMATCHED_REVIEW'),'CANDIDATE_ONLY',1,
       'UNVERIFIED_SILVER',0,0,s.mapping_status,s.candidate_scd_name,s.review_reason,%(source_sha)s
FROM source s
WHERE s.dav_row_id IS NOT NULL
 AND EXISTS(SELECT 1 FROM public.dav_product d WHERE d.dav_row_id=s.dav_row_id)
ON CONFLICT (dav_row_id) DO UPDATE SET
 suggested_scd_rxcui=EXCLUDED.suggested_scd_rxcui,
 silver_mapping_status=EXCLUDED.silver_mapping_status,
 candidate_scd_name=EXCLUDED.candidate_scd_name,
 review_reason=EXCLUDED.review_reason,
 silver_source_sha=EXCLUDED.silver_source_sha
WHERE COALESCE(dav_rxnorm_mapping.accepted_for_serving,0)<>1
  AND (dav_rxnorm_mapping.suggested_scd_rxcui,dav_rxnorm_mapping.silver_mapping_status,
       dav_rxnorm_mapping.candidate_scd_name,dav_rxnorm_mapping.review_reason)
 IS DISTINCT FROM
      (EXCLUDED.suggested_scd_rxcui,EXCLUDED.silver_mapping_status,
       EXCLUDED.candidate_scd_name,EXCLUDED.review_reason)
"""),
("dav_rxnorm_evidence", """
WITH clean AS (
 SELECT NULLIF(TRIM(dav_row_id),'') AS dav_row_id,
        component_order::integer AS component_order,
        NULLIF(TRIM(component_raw),'') AS component_raw,
        NULLIF(TRIM(ingredient_search_name),'') AS ingredient_search_name,
        NULLIF(TRIM(ingredient_candidate_rxcui),'') AS ingredient_candidate_rxcui,
        NULLIF(TRIM(ingredient_candidate_name),'') AS ingredient_candidate_name,
        NULLIF(TRIM(ingredient_candidate_tty),'') AS ingredient_candidate_tty,
        COALESCE(NULLIF(TRIM(candidate_count),'')::integer,0) AS candidate_count,
        NULLIF(TRIM(match_method),'') AS match_method,
        NULLIF(TRIM(evidence_status),'') AS evidence_status,
        NULLIF(TRIM(review_reason),'') AS review_reason
 FROM gold_stg_evidence
 WHERE dav_row_id IS NOT NULL AND component_order~'^[0-9]+$'
)
INSERT INTO public.dav_rxnorm_evidence
(dav_row_id,component_order,component_raw,ingredient_search_name,
 ingredient_candidate_rxcui,ingredient_candidate_name,ingredient_candidate_tty,
 candidate_count,match_method,evidence_status,review_reason,clinical_verified,silver_source_sha)
SELECT dav_row_id,component_order,component_raw,ingredient_search_name,
       ingredient_candidate_rxcui,ingredient_candidate_name,ingredient_candidate_tty,
       candidate_count,match_method,evidence_status,review_reason,FALSE,%(source_sha)s
FROM clean s
WHERE EXISTS(SELECT 1 FROM public.dav_product d WHERE d.dav_row_id=s.dav_row_id)
ON CONFLICT (dav_row_id,component_order) DO UPDATE SET
 component_raw=EXCLUDED.component_raw,ingredient_search_name=EXCLUDED.ingredient_search_name,
 ingredient_candidate_rxcui=EXCLUDED.ingredient_candidate_rxcui,
 ingredient_candidate_name=EXCLUDED.ingredient_candidate_name,
 ingredient_candidate_tty=EXCLUDED.ingredient_candidate_tty,
 candidate_count=EXCLUDED.candidate_count,match_method=EXCLUDED.match_method,
 evidence_status=EXCLUDED.evidence_status,review_reason=EXCLUDED.review_reason,
 silver_source_sha=EXCLUDED.silver_source_sha
WHERE NOT dav_rxnorm_evidence.clinical_verified
  AND (dav_rxnorm_evidence.component_raw,dav_rxnorm_evidence.ingredient_candidate_rxcui,
       dav_rxnorm_evidence.candidate_count,dav_rxnorm_evidence.evidence_status,
       dav_rxnorm_evidence.review_reason)
 IS DISTINCT FROM
      (EXCLUDED.component_raw,EXCLUDED.ingredient_candidate_rxcui,
       EXCLUDED.candidate_count,EXCLUDED.evidence_status,EXCLUDED.review_reason)
"""),
("medi_relation", """
WITH src AS (
 SELECT NULLIF(TRIM(medi_rxcui),'') AS rxcui,
        NULLIF(TRIM(medi_drug_description),'') AS drug_description,
        NULLIF(TRIM(medi_vocabulary),'') AS code_system,
        NULLIF(TRIM(medi_code),'') AS code_raw,
        NULLIF(TRIM(medi_indication_description),'') AS indication_description,
        NULLIF(TRIM(review_reason),'') AS review_reason,
        NULLIF(TRIM(mapping_status),'') AS crosswalk_review_status,
        NULLIF(TRIM(rxcui_found_in_rxnorm),'') AS rxnorm_match_status
 FROM gold_stg_medi
), uniq AS (
 SELECT DISTINCT ON (rxcui,code_system,code_raw,indication_description) *
 FROM src WHERE rxcui IS NOT NULL AND code_system IS NOT NULL AND code_raw IS NOT NULL
 ORDER BY rxcui,code_system,code_raw,indication_description,
          (drug_description IS NOT NULL) DESC
)
INSERT INTO public.medi_relation
(medi_relation_id,source_row_id,disease_icd_code,rxcui,drug_description,code_system,
 code_raw,code_normalized,code_nodot,code3,code_type,indication_description,
 relation_key,icd_match_status,rxnorm_match_status,normalization_status,
 review_reason,silver_source_sha,crosswalk_review_status)
SELECT 'slv:'||md5(concat_ws('|',u.rxcui,u.code_system,u.code_raw,
        COALESCE(u.indication_description,''))), NULL,NULL,u.rxcui,u.drug_description,u.code_system,
       u.code_raw,u.code_raw,REPLACE(u.code_raw,'.',''),LEFT(u.code_raw,3),
       'single',u.indication_description,
       md5(concat_ws('|',u.rxcui,u.code_system,u.code_raw,COALESCE(u.indication_description,''))),
       'CROSS_CODE_SYSTEM_REVIEW',u.rxnorm_match_status,'REVIEW_REQUIRED',
       u.review_reason,%(source_sha)s,u.crosswalk_review_status
FROM uniq u
WHERE NOT EXISTS (
 SELECT 1 FROM public.medi_relation r WHERE r.rxcui=u.rxcui
 AND r.code_system=u.code_system AND r.code_raw=u.code_raw
 AND r.indication_description IS NOT DISTINCT FROM u.indication_description
)
ON CONFLICT (medi_relation_id) DO NOTHING
"""),
]
