#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DAV ↔ RxNorm Mapper v1
======================

Evidence-based mapping from normalized DAV data to RxNorm SCD.

Required inputs
---------------
1) dav_product_normalized_v2.csv
2) dav_component_normalized_v2.csv
3) rxnorm_scd_mapping_ready.csv
4) rxnorm_clean.csv

Optional
--------
5) rxnorm_dav_mapping_clean.csv
   Reuses prior DAV ingredient identity evidence only.
   Prior product-level SCD mapping is NOT reused.

Main output
-----------
- dav_rxnorm_product_mapping_full.csv
- dav_rxnorm_component_mapping_full.csv
- dav_rxnorm_candidate_review_full.csv
- dav_rxnorm_mapping_qc.csv
- DAV_RxNorm_Full_Mapping_Package.zip

Acceptance logic
----------------
VERIFIED_SCD requires:
- complete ingredient-set equality
- exact component-strength equality after unit normalization
- exact semantic dosage-form correspondence
- no ingredient/DAV normalization review flag
- quantitative factor verified when applicable

Ambiguous candidates are never forced to one RxCUI.
"""

from __future__ import annotations
import argparse, csv, re, unicodedata, zipfile
from collections import defaultdict, Counter
from pathlib import Path

def load_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def nt(s):
    s = str(s or "").replace("đ","d").replace("Đ","D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("–","-").replace("—","-")
    s = re.sub(r"[^a-z0-9%+./ -]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_num(s):
    try:
        return float(str(s).replace(",", ".")) if str(s).strip() else None
    except Exception:
        return None

def canonical_strength(value, unit):
    """Strict mass/volume strength handling; unsupported dimensions remain unmapped."""
    if value is None or not str(unit).strip():
        return None
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None
    u = re.sub(r"\s+", "", str(unit).upper()).replace("µG", "MCG").replace("UG", "MCG")
    m = re.fullmatch(r"(KG|MCG|MG|G|ML|L|UNT|IU|MEQ|MMOL|MCI|%)(?:/([0-9]+(?:[.,][0-9]+)?)(ML|L|MG|G|MCG|EACH))?", u)
    if m:
        numerator, denvalue, denunit = m.group(1), float(m.group(2) or "1"), m.group(3)
    else:
        m = re.fullmatch(r"(KG|MCG|MG|G|ML|L|UNT|IU|MEQ|MMOL|MCI|%)(?:/(ML|L|MG|G|MCG|EACH))?", u)
        if not m: return None
        numerator, denvalue, denunit = m.group(1), 1.0, m.group(2)
    if numerator=="G":v*=1000;numerator="MG"
    elif numerator=="MCG":v/=1000;numerator="MG"
    elif numerator=="KG":v*=1000000;numerator="MG"
    if denunit:
        if not denvalue:return None
        if denunit=="L":denvalue*=1000;denunit="ML"
        elif denunit=="G":denvalue*=1000;denunit="MG"
        elif denunit=="MCG":denvalue/=1000;denunit="MG"
        v/=denvalue
        if denunit=="EACH":denunit=""
    return (round(v,12), f"{numerator}/{denunit}" if denunit else numerator)

def dav_strength_canon(d):
    v = parse_num(d.get("strength_compare_value"))
    u = d.get("strength_compare_unit","")
    return canonical_strength(v,u) if v is not None and u else None

def rx_strength_canon(r):
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(.*)$", str(r.get("strength_rxnorm") or "").strip())
    return canonical_strength(float(m.group(1)), m.group(2).strip()) if m else None

def canon_text(c):
    return "" if not c else f"{c[0]:g} {c[1]}"

def expected_forms(form_text, rx_forms):
    z = nt(form_text)
    exact, fams, route = set(), set(), ""

    if "uong" in z and "am dao" in z:
        if "nang" in z:
            exact, fams = {"Oral Capsule","Vaginal Insert"}, {"oral_capsule","vaginal"}
        elif "vien" in z:
            exact, fams = {"Oral Tablet","Vaginal Insert"}, {"oral_tablet","vaginal"}
        return exact & rx_forms, fams, "oral_or_vaginal"

    if "am dao" in z:
        fams, route = {"vaginal"}, "vaginal"
        exact = {"Vaginal Cream"} if "kem" in z else {"Vaginal Gel"} if "gel" in z else {"Vaginal Ointment"} if "mo" in z else {"Vaginal Insert"}
    elif "truc trang" in z or "hau mon" in z:
        fams, route = {"rectal"}, "rectal"
        exact = {"Rectal Cream"} if "kem" in z else {"Rectal Gel"} if "gel" in z else {"Rectal Ointment"} if "mo" in z else {"Rectal Solution","Enema"} if ("thut" in z or "dung dich" in z) else {"Rectal Suppository"}
    elif "duoi luoi" in z:
        exact, fams, route = {"Sublingual Tablet"}, {"sublingual"}, "sublingual"
    elif "tan trong ruot" in z or "tan o ruot" in z or "gastro" in z:
        exact, fams, route = ({"Delayed Release Oral Capsule"},{"oral_capsule"},"oral") if "nang" in z else ({"Delayed Release Oral Tablet"},{"oral_tablet"},"oral")
    elif any(k in z for k in ["phong thich keo dai","giai phong keo dai","tac dung keo dai","extended release","phong thich cham","giai phong cham"]):
        exact, fams, route = ({"Extended Release Oral Capsule"},{"oral_capsule"},"oral") if "nang" in z else ({"Extended Release Oral Tablet"},{"oral_tablet"},"oral")
    elif "phan tan trong mieng" in z:
        exact, fams, route = {"Disintegrating Oral Tablet"},{"oral_tablet"},"oral"
    elif "nhai" in z:
        exact, fams, route = {"Chewable Tablet"},{"oral_tablet"},"oral"
    elif "sui" in z:
        exact, fams, route = {"Effervescent Oral Tablet"},{"oral_tablet"},"oral"
    elif "ngam" in z:
        exact, fams, route = {"Oral Lozenge"},{"oral_tablet"},"oral"
    elif "vien nang" in z or z == "vien nang":
        exact, fams, route = {"Oral Capsule"},{"oral_capsule"},"oral"
    elif "vien nen" in z or z.startswith("vien "):
        exact, fams, route = {"Oral Tablet"},{"oral_tablet"},"oral"
    elif "bot" in z and "hon dich uong" in z:
        exact, fams, route = {"Powder for Oral Suspension"},{"oral_powder"},"oral"
    elif "com" in z and "hon dich uong" in z:
        exact, fams, route = {"Granules for Oral Suspension"},{"oral_granule"},"oral"
    elif "hon dich uong" in z or "nhu tuong uong" in z:
        exact, fams, route = {"Oral Suspension"},{"oral_liquid"},"oral"
    elif "dung dich uong" in z or "siro" in z:
        exact, fams, route = {"Oral Solution"},{"oral_liquid"},"oral"
    elif "mat" in z and "hon dich" in z:
        exact, fams, route = {"Ophthalmic Suspension"},{"ophthalmic"},"ophthalmic"
    elif "mat" in z and ("mo" in z or "tra" in z):
        exact, fams, route = {"Ophthalmic Ointment"},{"ophthalmic"},"ophthalmic"
    elif "mat" in z and "gel" in z:
        exact, fams, route = {"Ophthalmic Gel"},{"ophthalmic"},"ophthalmic"
    elif "mat" in z and ("dung dich" in z or "nho" in z):
        exact, fams, route = {"Ophthalmic Solution"},{"ophthalmic"},"ophthalmic"
    elif "tai" in z and ("dung dich" in z or "nho" in z):
        exact, fams, route = {"Otic Solution"},{"otic"},"otic"
    elif "mui" in z and ("xit" in z or "spray" in z):
        exact, fams, route = {"Nasal Spray","Metered Dose Nasal Spray"},{"nasal"},"nasal"
    elif "mui" in z and ("dung dich" in z or "nho" in z):
        exact, fams, route = {"Nasal Solution"},{"nasal"},"nasal"
    elif "khi dung" in z and "dung dich" in z:
        exact, fams, route = {"Inhalation Solution"},{"inhalation"},"respiratory"
    elif "bot hit" in z or "bot de hit" in z:
        exact, fams, route = {"Inhalation Powder","Dry Powder Inhaler"},{"inhalation"},"respiratory"
    elif "hon dich" in z and "tiem" in z:
        exact, fams, route = {"Injectable Suspension"},{"injection"},"parenteral"
    elif any(k in z for k in ["bot","dong kho","ong kho"]) and "tiem" in z:
        exact, fams, route = {"Injection"},{"injection"},"parenteral"
    elif ("dung dich" in z or "nhu tuong" in z) and ("tiem" in z or "truyen" in z):
        exact, fams, route = {"Injectable Solution"},{"injection"},"parenteral"
    elif "tiem" in z or "truyen" in z:
        exact, fams, route = {"Injection","Injectable Solution"},{"injection"},"parenteral"
    elif "kem" in z:
        exact, fams, route = {"Topical Cream"},{"topical"},"topical"
    elif "gel" in z:
        exact, fams, route = {"Topical Gel"},{"topical"},"topical"
    elif "thuoc mo" in z or "mo boi" in z:
        exact, fams, route = {"Topical Ointment"},{"topical"},"topical"
    elif "dan" in z or "mieng dan" in z:
        exact, fams, route = {"Medicated Patch","Transdermal System"},{"transdermal"},"transdermal"

    return exact & rx_forms, fams, route

def form_family(f):
    x = f.lower()
    if "ophthalmic" in x: return "ophthalmic"
    if "otic" in x: return "otic"
    if "nasal" in x: return "nasal"
    if "vaginal" in x: return "vaginal"
    if "rectal" in x or f == "Enema": return "rectal"
    if "sublingual" in x: return "sublingual"
    if "inhal" in x: return "inhalation"
    if "inject" in x or f in ("Injection","Prefilled Syringe","Auto-Injector","Cartridge","Pen Injector"): return "injection"
    if "topical" in x: return "topical"
    if "transdermal" in x or "patch" in x: return "transdermal"
    if "oral capsule" in x: return "oral_capsule"
    if "oral tablet" in x or f in ("Chewable Tablet","Disintegrating Oral Tablet","Effervescent Oral Tablet","Oral Lozenge"): return "oral_tablet"
    if any(k in x for k in ["oral solution","oral suspension"]): return "oral_liquid"
    if "oral powder" in x or "powder for oral" in x: return "oral_powder"
    if "oral granule" in x or "granules for oral" in x: return "oral_granule"
    return "other"

def rx_qf(g):
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s+(ML|HR|ACTUAT|MG|DAY|UNT)\s+", g["scd_name"], re.I)
    return (float(m.group(1)),m.group(2).upper()) if m else None

def dav_quantities(p):
    text = " ".join([p.get("dav_package",""),p.get("dav_drug_name_raw",""),p.get("dav_dosage_form_raw",""),p.get("dav_strength_raw","")])
    z = nt(text); out = defaultdict(set)
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*ml\b", z):
        out["ML"].add(float(m.group(1).replace(",",".")))
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:gio|hr|h)\b", z):
        out["HR"].add(float(m.group(1).replace(",",".")))
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:lieu|nhat|actuat)\b", z):
        out["ACTUAT"].add(float(m.group(1).replace(",",".")))
    return out

def qf_match(p,g):
    q = rx_qf(g)
    if not q: return "NOT_APPLICABLE",1.0
    qs = dav_quantities(p)
    if q[0] in qs.get(q[1],set()): return "MATCH",1.0
    if qs.get(q[1]): return "MISMATCH",0.0
    return "UNKNOWN",0.5

def form_match(p,g,rx_forms):
    exact,fams,_ = expected_forms(p["dav_dosage_form_raw"],rx_forms)
    if g["dose_form_rxnorm"] in exact: return "EXACT_SEMANTIC",1.0
    if fams and form_family(g["dose_form_rxnorm"]) in fams: return "FAMILY_COMPATIBLE",0.8
    return "MISMATCH_OR_UNKNOWN",0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dav-product", required=True)
    ap.add_argument("--dav-component", required=True)
    ap.add_argument("--rxnorm-scd", required=True)
    ap.add_argument("--rxnorm-clean", required=True)
    ap.add_argument("--prior-ingredient-map", default=None)
    ap.add_argument("--output-dir", default="dav_rxnorm_mapping_output")
    args = ap.parse_args()

    out = Path(args.output_dir).resolve(); out.mkdir(parents=True,exist_ok=True)
    dav_prod = load_csv(Path(args.dav_product))
    dav_comp = load_csv(Path(args.dav_component))
    rx_rows = load_csv(Path(args.rxnorm_scd))
    rxclean = load_csv(Path(args.rxnorm_clean))
    old_rows = load_csv(Path(args.prior_ingredient_map)) if args.prior_ingredient_map else []

    rx_scd = {}
    for r in rx_rows:
        g = rx_scd.setdefault(r["scd_rxcui"],{
            "scd_rxcui":r["scd_rxcui"],"scd_name":r["scd_name"],
            "dose_form_rxcui":r["dose_form_rxcui"],"dose_form_rxnorm":r["dose_form_rxnorm"],
            "components":[]
        })
        g["components"].append(r)
    ingredient_ids = {r["ingredient_rxcui"] for r in rx_rows if r["ingredient_rxcui"]}
    rx_forms = {r["dose_form_rxnorm"] for r in rx_rows}

    tty_priority={"IN":0,"PIN":1,"MIN":2,"SY":3,"SU":4,"BN":5}
    ing_name_to_rows=defaultdict(list)
    all_name_to_rows=defaultdict(list)
    for r in rxclean:
        k=nt(r["normalized_name"]); all_name_to_rows[k].append(r)
        if r["rxcui"] in ingredient_ids: ing_name_to_rows[k].append(r)

    old_key={(r["dav_row_id"],r["component_order"]):r for r in old_rows}

    def resolve_ing(d):
        name=nt(d["ingredient_normalized_candidate"])
        rows=ing_name_to_rows.get(name,[])
        ids=sorted({r["rxcui"] for r in rows})
        if len(ids)==1:
            rr=sorted(rows,key=lambda r:(tty_priority.get(r["tty"],9),0 if r["sab"]=="RXNORM" else 1))[0]
            return rr["rxcui"],rr["display_name"],rr["tty"],rr["sab"],"RXNORM_TERM_EXACT","HIGH",False,1.0
        old=old_key.get((d["dav_row_id"],d["component_order"]))
        if old and old.get("matched")=="1" and old.get("rxcui") in ingredient_ids:
            mm=old.get("match_method","")
            conf="HIGH" if mm=="exact_normalized" else "MEDIUM" if mm in ("international_synonym","base_ingredient") else "LOW"
            score=float(old.get("match_score") or (0.99 if mm=="exact_normalized" else 0.9))
            return old["rxcui"],old["rxnorm_display_name"],old["rxnorm_tty"],old["rxnorm_sab"],"PRIOR_"+mm.upper(),conf,mm!="exact_normalized",score
        rows2=all_name_to_rows.get(name,[])
        ids2=sorted({r["rxcui"] for r in rows2})
        if len(ids2)==1:
            rr=rows2[0]
            return rr["rxcui"],rr["display_name"],rr["tty"],rr["sab"],"RXNORM_TERM_EXACT_NOT_IN_SCD_COMPONENT","MEDIUM",True,0.9
        return "","","","","UNMATCHED_INGREDIENT","NONE",True,0.0

    comps_by_prod=defaultdict(list)
    for d in dav_comp:
        rid,rn,tty,sab,method,conf,review,score = resolve_ing(d)
        x=dict(d)
        x["_rid"]=rid;x["_rname"]=rn;x["_tty"]=tty;x["_sab"]=sab;x["_method"]=method
        x["_conf"]=conf;x["_review"]=review;x["_score"]=score;x["_strength"]=dav_strength_canon(d)
        comps_by_prod[d["dav_row_id"]].append(x)

    rx_ing_index=defaultdict(list); rx_sig_index=defaultdict(list)
    for g in rx_scd.values():
        ingtuple=tuple(sorted(r["ingredient_rxcui"] for r in g["components"]))
        rx_ing_index[ingtuple].append(g)
        rs=[rx_strength_canon(r) for r in g["components"]]
        if all(rs):
            sig=tuple(sorted((r["ingredient_rxcui"],rx_strength_canon(r)) for r in g["components"]))
            rx_sig_index[sig].append(g)

    prod_headers=[
        "dav_row_id","dav_registration_number","dav_drug_name","dav_active_ingredient_raw",
        "dav_strength_raw","dav_dosage_form_raw","dav_package",
        "ingredient_rxcuies","ingredient_rxnorm_names","ingredient_identity_methods",
        "selected_scd_rxcui","selected_scd_name","selected_scd_dose_form",
        "suggested_scd_rxcui","suggested_scd_name",
        "mapping_score","evidence_level","mapping_status","confidence","review_required","review_reason"
    ]
    product_rows=[]; selected_by_prod={}

    for p in dav_prod:
        pid=p["dav_row_id"]; comps=comps_by_prod.get(pid,[])
        all_ing=bool(comps) and all(c["_rid"] in ingredient_ids for c in comps)
        all_strength=bool(comps) and all(c["_strength"] is not None for c in comps)

        ing_candidates=[]; exact_candidates=[]
        if all_ing:
            ingtuple=tuple(sorted(c["_rid"] for c in comps))
            ing_candidates=rx_ing_index.get(ingtuple,[])
            if all_strength:
                sig=tuple(sorted((c["_rid"],c["_strength"]) for c in comps))
                exact_candidates=rx_sig_index.get(sig,[])

        selected=None; status=""; confidence="NONE"; review=True; reasons=[]; form_type=""; qftype=""

        if exact_candidates:
            exact_forms,fams,_=expected_forms(p["dav_dosage_form_raw"],rx_forms)
            exact_form=[g for g in exact_candidates if g["dose_form_rxnorm"] in exact_forms]
            family=[g for g in exact_candidates if fams and form_family(g["dose_form_rxnorm"]) in fams]

            if len(exact_form)==1:
                selected=exact_form[0];form_type="EXACT_SEMANTIC"
            elif len(exact_form)>1:
                q=[g for g in exact_form if qf_match(p,g)[0]=="MATCH"]
                if len(q)==1: selected=q[0];form_type="EXACT_SEMANTIC";qftype="MATCH"
                else: status="AMBIGUOUS_SCD";reasons.append("MULTIPLE_EXACT_FORM_SCD")
            elif len(family)==1:
                selected=family[0];form_type="FAMILY_COMPATIBLE";reasons.append("DOSE_FORM_FAMILY_ONLY")
            elif len(family)>1:
                q=[g for g in family if qf_match(p,g)[0]=="MATCH"]
                if len(q)==1: selected=q[0];form_type="FAMILY_COMPATIBLE";qftype="MATCH";reasons.append("DOSE_FORM_FAMILY_ONLY")
                else: status="AMBIGUOUS_SCD";reasons.append("MULTIPLE_FAMILY_SCD")
            elif len(exact_candidates)==1:
                status="INGREDIENT_STRENGTH_FORM_CONFLICT";reasons.append("DOSE_FORM_MISMATCH_OR_UNMAPPED")
            else:
                status="AMBIGUOUS_SCD";reasons.append("MULTIPLE_INGREDIENT_STRENGTH_SCD")

            if selected:
                if not qftype: qftype=qf_match(p,selected)[0]
                ing_review=any(c["_review"] for c in comps)
                dav_review=any(c.get("mapping_readiness_v2")!="READY_FOR_RXNORM_CANDIDATE" for c in comps)
                qok=qftype in ("NOT_APPLICABLE","MATCH")
                if form_type=="EXACT_SEMANTIC" and not ing_review and not dav_review and qok:
                    status,confidence,review="VERIFIED_SCD","HIGH",False
                else:
                    status,confidence,review="SCD_MATCH_REVIEW_REQUIRED","MEDIUM",True
                    if ing_review: reasons.append("INGREDIENT_IDENTITY_REVIEW")
                    if dav_review: reasons.append("DAV_NORMALIZATION_REVIEW")
                    if qftype=="MISMATCH": reasons.append("QUANTITY_FACTOR_MISMATCH");confidence="LOW"
                    elif qftype=="UNKNOWN": reasons.append("QUANTITY_FACTOR_NOT_VERIFIED")
        elif all_ing and ing_candidates:
            status,confidence="INGREDIENT_SET_ONLY","LOW";reasons.append("NO_EXACT_STRENGTH_SCD")
        elif all_ing:
            status,confidence="NO_SCD_FOR_INGREDIENT_SET","NONE";reasons.append("INGREDIENT_SET_NOT_FOUND_IN_SCD")
        elif comps and any(c["_rid"] in ingredient_ids for c in comps):
            status,confidence="PARTIAL_INGREDIENT_MAPPING","LOW";reasons.append("ONE_OR_MORE_INGREDIENTS_UNMAPPED")
        else:
            status,confidence="UNMAPPED","NONE";reasons.append("NO_RXNORM_INGREDIENT_IDENTITY")

        suggested=None
        if not selected and ing_candidates:
            ranked=[]
            for g in ing_candidates:
                sf=sum(
                    1 for c in comps
                    if any(r["ingredient_rxcui"]==c["_rid"] and rx_strength_canon(r)==c["_strength"] for r in g["components"])
                )/max(len(comps),len(g["components"]))
                fm,fs=form_match(p,g,rx_forms); qm,qs=qf_match(p,g)
                ranked.append((0.70*sf+0.25*fs+0.05*qs,g))
            ranked.sort(key=lambda x:x[0],reverse=True)
            if ranked and (len(ranked)==1 or ranked[0][0] > ranked[1][0]):
                suggested=ranked[0][1]

        score=""
        if selected:
            min_ing=min((c["_score"] for c in comps),default=0)
            fs=1.0 if form_type=="EXACT_SEMANTIC" else 0.8
            qs={"MATCH":1.0,"NOT_APPLICABLE":1.0,"UNKNOWN":0.5,"MISMATCH":0.0}.get(qftype,0.5)
            score=round(0.45*min_ing+0.35+0.15*fs+0.05*qs,4)

        evidence = "A_VERIFIED" if status=="VERIFIED_SCD" else "B_STRUCTURED_REVIEW" if status=="SCD_MATCH_REVIEW_REQUIRED" else "C_CANDIDATE_ONLY" if status in ("AMBIGUOUS_SCD","INGREDIENT_STRENGTH_FORM_CONFLICT","INGREDIENT_SET_ONLY") else "D_PARTIAL" if status in ("PARTIAL_INGREDIENT_MAPPING","NO_SCD_FOR_INGREDIENT_SET") else "U_UNMAPPED"

        product_rows.append({
            "dav_row_id":pid,
            "dav_registration_number":p["dav_registration_number"],
            "dav_drug_name":p["dav_drug_name_raw"],
            "dav_active_ingredient_raw":p["dav_active_ingredient_raw"],
            "dav_strength_raw":p["dav_strength_raw"],
            "dav_dosage_form_raw":p["dav_dosage_form_raw"],
            "dav_package":p["dav_package"],
            "ingredient_rxcuies":";".join(f"{c['component_order']}:{c['_rid']}" for c in comps if c["_rid"]),
            "ingredient_rxnorm_names":";".join(f"{c['component_order']}:{c['_rname']}" for c in comps if c["_rname"]),
            "ingredient_identity_methods":";".join(f"{c['component_order']}:{c['_method']}" for c in comps),
            "selected_scd_rxcui":selected["scd_rxcui"] if selected else "",
            "selected_scd_name":selected["scd_name"] if selected else "",
            "selected_scd_dose_form":selected["dose_form_rxnorm"] if selected else "",
            "suggested_scd_rxcui":suggested["scd_rxcui"] if suggested else "",
            "suggested_scd_name":suggested["scd_name"] if suggested else "",
            "mapping_score":score,
            "evidence_level":evidence,
            "mapping_status":status,
            "confidence":confidence,
            "review_required":1 if review else 0,
            "review_reason":"|".join(dict.fromkeys(reasons)),
        })
        if selected: selected_by_prod[pid]=selected

    product_path=out/"dav_rxnorm_product_mapping_full.csv"
    write_csv(product_path,prod_headers,product_rows)

    comp_headers=[
        "dav_row_id","component_order","dav_registration_number","dav_drug_name",
        "dav_ingredient_component","dav_strength_canonical",
        "ingredient_rxcui","ingredient_rxnorm_name","ingredient_match_method","ingredient_confidence",
        "selected_scd_rxcui","selected_scd_name","scdc_rxcui","rx_strength","component_match_status"
    ]
    comp_rows=[]
    for pid,comps in comps_by_prod.items():
        selected=selected_by_prod.get(pid)
        for c in comps:
            rxcomp=None
            if selected and c["_rid"] in ingredient_ids and c["_strength"]:
                mm=[r for r in selected["components"] if r["ingredient_rxcui"]==c["_rid"] and rx_strength_canon(r)==c["_strength"]]
                if len(mm)==1: rxcomp=mm[0]
            comp_rows.append({
                "dav_row_id":pid,"component_order":c["component_order"],
                "dav_registration_number":c["dav_registration_number"],"dav_drug_name":c["dav_drug_name"],
                "dav_ingredient_component":c["ingredient_component_clean"],"dav_strength_canonical":canon_text(c["_strength"]),
                "ingredient_rxcui":c["_rid"],"ingredient_rxnorm_name":c["_rname"],
                "ingredient_match_method":c["_method"],"ingredient_confidence":c["_conf"],
                "selected_scd_rxcui":selected["scd_rxcui"] if selected else "",
                "selected_scd_name":selected["scd_name"] if selected else "",
                "scdc_rxcui":rxcomp["scdc_rxcui"] if rxcomp else "",
                "rx_strength":rxcomp["strength_rxnorm"] if rxcomp else "",
                "component_match_status":"LINKED_TO_SELECTED_SCD" if rxcomp else "INGREDIENT_LINKED_SCD_NOT_SELECTED" if c["_rid"] in ingredient_ids else "UNMAPPED_INGREDIENT"
            })
    comp_path=out/"dav_rxnorm_component_mapping_full.csv"
    write_csv(comp_path,comp_headers,comp_rows)

    counts=Counter(r["mapping_status"] for r in product_rows)
    qc_path=out/"dav_rxnorm_mapping_qc.csv"
    with qc_path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f);w.writerow(["metric","value"])
        w.writerow(["dav_products_total",len(product_rows)])
        w.writerow(["dav_components_total",len(comp_rows)])
        w.writerow(["selected_scd_products",sum(1 for r in product_rows if r["selected_scd_rxcui"])])
        for k,v in counts.most_common(): w.writerow([f"status__{k}",v])

    zip_path=out/"DAV_RxNorm_Full_Mapping_Package.zip"
    with zipfile.ZipFile(zip_path,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for p in [product_path,comp_path,qc_path]:
            z.write(p,arcname=p.name)

    print("DONE")
    print("Products:",len(product_rows))
    print("Selected SCD:",sum(1 for r in product_rows if r["selected_scd_rxcui"]))
    print("Output:",out)

if __name__ == "__main__":
    main()