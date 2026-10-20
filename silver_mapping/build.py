"""Generate conservative mapping tables from the current compact Silver CSVs.

Source terminology relationships inferred from exact RxNorm SCD/SCDC strings are
NOT RXNREL official relations. No row is assigned VERIFIED without curated evidence.
"""
from __future__ import annotations
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from silver_v3.legacy_tools.rxnorm_normalize import build_outputs, search_norm
from silver_v3.quality import strength_signature
from silver_v3.safe_tools.dav_rxnorm_mapper_v3 import expected_forms

OUTPUTS = (
    "dav_rxnorm_mapping",
    "dav_rxnorm_component_evidence",
    "rxnorm_scd_components",
    "medi_icd10_mapping",
)
FIELDS = {
    "dav_rxnorm_mapping": [
        "dav_row_id","dav_registration_number","dav_drug_name","dav_active_ingredient_raw",
        "dav_strength_raw","dav_dosage_form_raw","dav_qc_status",
        "ingredient_components","ingredient_candidates_found",
        "candidate_scd_rxcui","candidate_scd_name","candidate_strength",
        "candidate_dose_form","mapping_status","mapping_method",
        "review_reason","clinical_verified","source"
    ],
    "dav_rxnorm_component_evidence": [
        "dav_row_id","component_order","component_raw","ingredient_search_name",
        "ingredient_candidate_rxcui","ingredient_candidate_name","ingredient_candidate_tty",
        "candidate_count","match_method","evidence_status","review_reason","clinical_verified"
    ],
    "rxnorm_scd_components": [
        "scd_rxcui","scd_name","dose_form_rxcui","dose_form_name",
        "component_order","component_raw","scdc_rxcui","scdc_name",
        "ingredient_rxcui","ingredient_name","component_strength",
        "relation_status","evidence_method","clinical_verified","source"
    ],
    "medi_icd10_mapping": [
        "medi_row_id","medi_rxcui","medi_drug_description","medi_vocabulary",
        "medi_code","medi_indication_description",
        "candidate_icd10_vi_code","candidate_icd10_vi_name",
        "candidate_count","rxcui_found_in_rxnorm","mapping_status","evidence_method",
        "review_reason","clinical_verified","source_release"
    ],
}
# Translation aliases are used only to SUGGEST candidates, never for verification.
ALIASES = {
    "paracetamol": "acetaminophen",
    "vitamin c": "ascorbic acid",
    "acid ascorbic": "ascorbic acid",
}
def rows(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)):
            raise ValueError("Invalid CSV headers: "+str(path))
        yield from reader

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as inp:
        for chunk in iter(lambda: inp.read(2**20),b""):
            h.update(chunk)
    return h.hexdigest()

def strength(raw):
    """Canonical numeric signature with plain decimals, never scientific notation."""
    val,unit=strength_signature(raw)
    if val is None:
        return None
    return format(val.normalize(), "f"),unit

def display_strength(signature):
    """User-facing dosage strength (e.g. '500 MG', not "('5E+2', 'MG')")."""
    return f"{signature[0]} {signature[1]}" if signature else ""

def split_ingredients(raw):
    original=(raw or "").strip()
    if not original:
        return [""]
    # Do not treat slash as a safe ingredient separator (it can denote synonyms).
    pieces=[p.strip() for p in re.split(r"\s*[+;]\s*|\n+",original) if p.strip()]
    return pieces or [original]

def ingredient_search_value(raw):
    stripped=re.sub(r"\s+\d+(?:[.,]\d+)?\s*(?:mcg|ug|mg|g|iu|ml)\b.*$","",raw or "",flags=re.I).strip()
    return search_norm(stripped), stripped != (raw or "").strip()

def create_rx_tables(rxrows):
    canonical=[]
    for row in rxrows:
        if row.get("sab")!="RXNORM" or not row.get("rxcui","").isdigit():
            continue
        display=row.get("display_name","").strip()
        canonical.append({
            "rxcui":row["rxcui"],"tty":row.get("tty",""),"sab":"RXNORM",
            "display_name":display,
            "normalized_name_source":row.get("normalized_name",""),
            "display_name_norm":search_norm(display),
            "normalized_name_norm":search_norm(row.get("normalized_name") or display),
        })
    if not canonical:
        raise ValueError("No valid RXNORM source terms; abort mappings")
    built=build_outputs(canonical,Counter({"input_rows":len(canonical),"clean_rows":len(canonical)}))
    ings=built["01_Ingredient"]
    index=defaultdict(dict)
    for term in ings:
        if term["ingredient_tty"] not in ("IN","PIN"):
            continue
        key=search_norm(term["ingredient_name"])
        index[key][term["ingredient_rxcui"]]=term
    scdcs={r["scdc_rxcui"]:r for r in built["02_Component_SCDC"]}
    clinical={r["scd_rxcui"]:r for r in built["03_Clinical_Drug_SCD"]}
    relations=built["05_SCD_Component_Rel"]
    components=[]
    scd_by_ingredient_strength=defaultdict(list)
    for rel in relations:
        scd=clinical.get(rel["scd_rxcui"],{})
        scdc=scdcs.get(rel["scdc_rxcui"],{})
        resolved=(bool(rel["scdc_rxcui"]) and
            rel["relation_status"]=="EXACT_SCDC_NAME" and
            scdc.get("parse_status")=="EXACT_INGREDIENT_PREFIX")
        item={
            "scd_rxcui":rel["scd_rxcui"],"scd_name":rel["scd_name"],
            "dose_form_rxcui":scd.get("dose_form_rxcui",""),
            "dose_form_name":scd.get("dose_form_name",""),
            "component_order":rel["component_order"],"component_raw":rel["component_raw"],
            "scdc_rxcui":rel["scdc_rxcui"],"scdc_name":scdc.get("scdc_name",""),
            "ingredient_rxcui":scdc.get("ingredient_rxcui",""),
            "ingredient_name":scdc.get("ingredient_name",""),
            "component_strength":scdc.get("strength_text",""),
            "relation_status":"TEXT_INFERRED_REVIEW" if resolved else "UNRESOLVED_REVIEW",
            "evidence_method":"EXACT_RXNORM_TERM_PARSE_NOT_OFFICIAL_RXNREL",
            "clinical_verified":"false","source":"RXNORM_SCD_SCDC_TERMINOLOGY",
        }
        components.append(item)
        if (resolved and scd.get("component_count")==1 and
            scd.get("component_status")=="ALL_COMPONENTS_EXACT" and
            scd.get("dose_form_status")=="EXACT_DF_SUFFIX"):
            canonical_strength=strength(scdc.get("strength_text",""))
            if canonical_strength:
                scd_by_ingredient_strength[
                    (scdc["ingredient_rxcui"],canonical_strength)
                ].append(item)
    known_rxcuis={r["rxcui"] for r in canonical}
    return index,scd_by_ingredient_strength,components,known_rxcuis

def lookup_ingredient(part,index):
    key,stripped=ingredient_search_value(part)
    method="RXNORM_INGREDIENT_EXACT_NAME"
    matches=index.get(key,{})
    if not matches and key in ALIASES:
        matches=index.get(search_norm(ALIASES[key]),{})
        method="CURATED_LANGUAGE_ALIAS_REVIEW"
    if not matches:
        return [],"UNMATCHED_REVIEW","NO_RXNORM_INGREDIENT_EXACT_MATCH"
    sorted_matches=sorted(matches.values(),key=lambda x:(x["ingredient_rxcui"],x["ingredient_tty"]))
    if len(sorted_matches)>1:
        return sorted_matches,"AMBIGUOUS_REVIEW","MULTIPLE_INGREDIENT_RXCUI"
    if stripped:
        return sorted_matches,method+"_STRENGTH_STRIPPED","STRENGTH_EMBEDDED_IN_INGREDIENT"
    return sorted_matches,method,""

def build_all(dav,rxnorm,icd10,output_dir,medi=None):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    index,scd_index,relations,known_rxcuis=create_rx_tables(rows(rxnorm))
    counts=Counter()
    def write(name,records):
        with (out/(name+".csv")).open("w",encoding="utf-8",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=FIELDS[name],extrasaction="ignore",lineterminator="\n")
            writer.writeheader()
            for record in records:
                writer.writerow(record)
                counts[name]+=1
    write("rxnorm_scd_components",relations)
    evidence=[]
    mapping=[]
    for davrow in rows(dav):
        ident=davrow.get("dav_row_id","").strip()
        if not ident:raise ValueError("DAV record missing id")
        original=davrow.get("dav_active_ingredient_raw","")
        parts=split_ingredients(original)
        selected=[]
        problems=[]
        for order,part in enumerate(parts,1):
            matches,method,reason=lookup_ingredient(part,index)
            evidence.append({
                "dav_row_id":ident,"component_order":order,
                "component_raw":part,"ingredient_search_name":ingredient_search_value(part)[0],
                "ingredient_candidate_rxcui":matches[0]["ingredient_rxcui"] if len(matches)==1 else "",
                "ingredient_candidate_name":matches[0]["ingredient_name"] if len(matches)==1 else "",
                "ingredient_candidate_tty":matches[0]["ingredient_tty"] if len(matches)==1 else "",
                "candidate_count":len(matches),"match_method":method,
                "evidence_status":"CANDIDATE_REVIEW" if len(matches)==1 else "REVIEW_REQUIRED",
                "review_reason":reason,"clinical_verified":"false"})
            if len(matches)==1:selected.append(matches[0])
            if reason:problems.append(reason)
        if len(parts)>1:problems.append("MULTI_INGREDIENT_REQUIRES_COMPLETE_COMPONENT_SET")
        if "/" in original:problems.append("POSSIBLE_AMBIGUOUS_SEPARATOR")
        current_strength=strength(davrow.get("dav_strength",""))
        if not current_strength:problems.append("UNKNOWN_OR_AMBIGUOUS_DAV_STRENGTH")
        matched=[]
        if len(parts)==1 and len(selected)==1 and current_strength:
            form=davrow.get("dav_dosage_form","")
            choices=scd_index.get((selected[0]["ingredient_rxcui"],current_strength),[])
            all_forms={entry["dose_form_name"] for entry in choices}
            exact_forms,_,_=expected_forms(form,all_forms)
            matched=[item for item in choices if item["dose_form_name"] in exact_forms]
            # Different texts for same RxCUI must not imply duplicate candidates.
            matched={m["scd_rxcui"]:m for m in matched}
            matched=list(matched.values())
            if not matched and choices:problems.append("DOSE_FORM_NOT_EXACT_OR_UNAVAILABLE")
            if len(matched)>1:problems.append("MULTIPLE_SCD_CANDIDATES")
        if not matched:problems.append("NO_COMPLETE_SCD_STRUCTURAL_MATCH")
        final=matched[0] if len(matched)==1 else {}
        mapping.append({
            "dav_row_id":ident,
            "dav_registration_number":davrow.get("dav_registration_number",""),
            "dav_drug_name":davrow.get("dav_drug_name",""),
            "dav_active_ingredient_raw":original,
            "dav_strength_raw":davrow.get("dav_strength",""),
            "dav_dosage_form_raw":davrow.get("dav_dosage_form",""),
            "dav_qc_status":davrow.get("silver_qc_status",""),
            "ingredient_components":len(parts),"ingredient_candidates_found":len(selected),
            "candidate_scd_rxcui":final.get("scd_rxcui",""),
            "candidate_scd_name":final.get("scd_name",""),
            "candidate_strength":display_strength(current_strength),
            "candidate_dose_form":final.get("dose_form_name",""),
            "mapping_status":"CANDIDATE_REVIEW" if final else "UNMATCHED_REVIEW",
            "mapping_method":"EXACT_INGREDIENT_STRENGTH_FORM_TEXT_STRUCTURE" if final else "EVIDENCE_INCOMPLETE",
            "review_reason":"|".join(sorted(set(problems))) if problems else "OFFICIAL_RXNREL_NOT_AVAILABLE",
            "clinical_verified":"false","source":"DAV+RXNORM_TERMINOLOGY",
        })
    write("dav_rxnorm_mapping",mapping)
    write("dav_rxnorm_component_evidence",evidence)
    icd_index=defaultdict(list)
    for item in rows(icd10):
        code=item.get("silver_code_canonical",item.get("code","")).strip().upper()
        if code and item.get("name_vi","").strip():
            icd_index[code].append(item)
    medi_records=[]
    if medi and Path(medi).is_file():
        for i,item in enumerate(rows(medi),start=2):
            code=item.get("CODE","").strip().upper()
            voc=item.get("VOCABULARY","").strip().upper()
            candidates=icd_index.get(code,[]) if voc=="ICD10CM" else []
            unique={c["id"]:c for c in candidates if c.get("id")}
            matched=list(unique.values())
            is_candidate=len(matched)==1
            medi_records.append({
                "medi_row_id":str(i),"medi_rxcui":item.get("RXCUI",""),
                "medi_drug_description":item.get("DRUG_DESCRIPTION",""),
                "medi_vocabulary":voc,"medi_code":code,
                "medi_indication_description":item.get("INDICATION_DESCRIPTION",""),
                "candidate_icd10_vi_code":code if is_candidate else "",
                "candidate_icd10_vi_name":matched[0].get("name_vi","") if is_candidate else "",
                "candidate_count":len(matched),
                "rxcui_found_in_rxnorm":str(item.get("RXCUI","") in known_rxcuis).lower(),
                "mapping_status":"CROSS_CODE_SYSTEM_REVIEW" if is_candidate else "UNMATCHED_REVIEW",
                "evidence_method":"IDENTICAL_CODE_STRING_ONLY_NOT_EQUIVALENCE" if is_candidate else "NO_VALIDATED_CROSSWALK",
                "review_reason":"MEDI_LEGACY_SOURCE;ICD10CM_NOT_EQUIVALENT_TO_ICD10_VI" if is_candidate else "MEDI_LEGACY_SOURCE;NO_SAFE_CROSSWALK",
                "clinical_verified":"false","source_release":"MEDI-2_HPS_LEGACY_VERSION_UNVERIFIED",
            })
    write("medi_icd10_mapping",medi_records)
    # Refuse publication if an output is missing or includes clinically auto-verified values.
    for dataset in OUTPUTS:
        output_path=out/(dataset+".csv")
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise ValueError("Empty mapping output: "+dataset)
        expected=counts[dataset]
        actual=0
        with output_path.open("r",encoding="utf-8",newline="") as stream:
            for record in csv.DictReader(stream):
                actual+=1
                if record.get("clinical_verified")!="false":
                    raise ValueError("Unsafe clinical_verified value: "+dataset)
        if expected!=actual:
            raise ValueError(f"Mapping row count mismatch: {dataset} {expected}!={actual}")
    if counts["dav_rxnorm_mapping"]==0 or counts["rxnorm_scd_components"]==0:
        raise ValueError("Required source or structural relations absent; refuse publication")
    if counts["dav_rxnorm_component_evidence"]<counts["dav_rxnorm_mapping"]:
        raise ValueError("Some DAV products lack component evidence")
    return {
        "rows":dict(counts),
        "csv_sha256":{name:digest(out/(name+".csv")) for name in OUTPUTS},
        "mapping_verified":False,
        "relation_evidence":"TEXT_STRUCTURE_ONLY_NOT_OFFICIAL_RXNREL",
        "medi_release":"LEGACY_NOT_CURATED",
    }
