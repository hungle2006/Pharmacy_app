"""Report 3 (EDA/QC) + Report 4 (visualization) for RxNorm before mapping.

Reads current Silver CSV; does not mutate Bronze/Silver, does not invent links.
Outputs an analysis JSON, a standalone HTML report, and a temporary mapping-ready
CSV with the five raw terminology fields.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from silver_mapping.rxnorm_report4 import compute_report4
from silver_mapping.rxnorm_report3 import profile

FIELDS = ["normalized_name", "rxcui", "display_name", "tty", "sab"]
BUCKETS = ["0-19", "20-39", "40-79", "80-159", "160+"]
PLACEHOLDERS = {"", "null", "none", "nan", "n/a"}
EXCLUDE_QC = {"REJECTED"}

def missing(value):
    return str(value or "").strip().lower() in PLACEHOLDERS

def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())

def pct(n, d):
    return round(100.0*n/d, 2) if d else 0.0

def hash_file(path):
    d=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            d.update(chunk)
    return d.hexdigest()

def ordered(counter):
    return [{"label":k, "count":v} for k,v in sorted(counter.items(),key=lambda p:(-p[1],p[0]))]

def analyze(source_path, mapping_path, report_path, html_path=None, provenance=None):
    source_path=Path(source_path);mapping_path=Path(mapping_path);report_path=Path(report_path)
    missing_by=Counter();tty=Counter();sab=Counter();qc=Counter();lengths=Counter()
    excluded=Counter();seen=set();concept_ids=set()
    stats=Counter();names_changed=0
    preview=[]
    report_path.parent.mkdir(parents=True,exist_ok=True)
    mapping_path.parent.mkdir(parents=True,exist_ok=True)
    with source_path.open("r",encoding="utf-8-sig",newline="") as src, mapping_path.open("w",encoding="utf-8",newline="") as dst:
        reader=csv.DictReader(src)
        headers=reader.fieldnames or []
        if len(headers)!=len(set(headers)) or any(f not in headers for f in FIELDS):
            raise ValueError("RxNorm Silver missing/duplicate columns; required "+",".join(FIELDS))
        w=csv.DictWriter(dst,fieldnames=FIELDS,lineterminator="\n")
        w.writeheader()
        for lineno,row in enumerate(reader,2):
            if None in row or any(row.get(h) is None for h in headers):
                raise ValueError("Malformed RxNorm CSV row "+str(lineno))
            stats["input_rows"]+=1
            qcstatus=(row.get("silver_qc_status") or "UNASSESSED").strip().upper()
            qc[qcstatus]+=1
            for f in FIELDS:
                if missing(row.get(f)):
                    missing_by[f]+=1
            tty_label=row["tty"].strip().upper() or "(missing)"
            sab_label=row["sab"].strip().upper() or "(missing)"
            tty[tty_label]+=1
            sab[sab_label]+=1
            text=row["display_name"].strip()
            n=len(text)
            group="0-19" if n<20 else "20-39" if n<40 else "40-79" if n<80 else "80-159" if n<160 else "160+"
            lengths[group]+=1
            if normalized(text)!=(row["normalized_name"] or "").strip():
                names_changed+=1
            if not re.fullmatch(r"[0-9]{1,15}",row["rxcui"].strip()):
                excluded["INVALID_RXCUI"]+=1
                continue
            if any(missing(row.get(f)) for f in ("display_name","tty","sab")):
                excluded["MISSING_REQUIRED_TERMINOLOGY"]+=1
                continue
            if qcstatus in EXCLUDE_QC:
                excluded["SILVER_REJECTED"]+=1
                continue
            if sab_label!="RXNORM":
                excluded["OTHER_SOURCE_ABBREVIATION"]+=1
                continue
            identity=tuple(row[x].strip() for x in ("rxcui","tty","sab","display_name"))
            if identity in seen:
                excluded["DUPLICATE_CONCEPT_TERM"]+=1
                continue
            seen.add(identity)
            concept_ids.add(row["rxcui"].strip())
            clean={f:row[f].strip() for f in FIELDS}
            clean["normalized_name"]=(row["normalized_name"] or normalized(text)).strip()
            if not clean["normalized_name"]:
                excluded["UNNORMALIZABLE_NAME"]+=1
                seen.remove(identity)
                continue
            w.writerow(clean)
            stats["mapping_ready_rows"]+=1
            if clean["tty"].upper() in ("IN","PIN"):stats["ingredient_terms"]+=1
            if clean["tty"].upper()=="SCD":stats["clinical_drug_terms"]+=1
            if len(preview)<8:
                preview.append({"rxcui":clean["rxcui"],"tty":clean["tty"],"display_name":clean["display_name"],"normalized_name":clean["normalized_name"]})
    if not stats["input_rows"]:
        raise ValueError("Empty RxNorm Silver data")
    if not stats["mapping_ready_rows"] or not stats["ingredient_terms"] or not stats["clinical_drug_terms"]:
        raise ValueError("RxNorm not suitable for mapping: missing IN/PIN or SCD")
    excluded_count=stats["input_rows"]-stats["mapping_ready_rows"]
    # Benign identical-term duplicates are deduplicated but must not trip
    # the quality gate. Invalid/unusable source rows above 5% do.
    invalid_count=sum(count for reason,count in excluded.items()
                      if reason!="DUPLICATE_CONCEPT_TERM")
    if invalid_count/stats["input_rows"]>0.05:
        raise ValueError(f"RxNorm unusable {invalid_count}/{stats['input_rows']} rows (>5%)")
    report={
        "source":"silver/rxnorm.csv",
        "source_sha256":hash_file(source_path),
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "provenance":provenance or {},
        "report_3_eda":{
            "scope":"Term-level current Silver RxNorm; not unique products or clinical relationships",
            "total_rows":stats["input_rows"],
            "distinct_rxcui_mapping_ready":len(concept_ids),
            "mapping_ready_rows":stats["mapping_ready_rows"],
            "excluded_rows":excluded_count,
            "mapping_ready_rate_pct":pct(stats["mapping_ready_rows"],stats["input_rows"]),
            "ingredient_terms":stats["ingredient_terms"],
            "scd_terms":stats["clinical_drug_terms"],
            "normalization_difference_rows":names_changed,
            "normalization_difference_pct":pct(names_changed,stats["input_rows"]),
            "missing_by_field":[{"field":f,"count":missing_by[f],"percentage":pct(missing_by[f],stats["input_rows"])} for f in FIELDS],
            "qc_distribution":ordered(qc),
            "excluded_reasons":ordered(excluded),
            "normalization":"Unicode NFKD, lowercase, remove diacritics/punctuation, collapse spaces; source display_name kept verbatim",
            "missing_policy":"No imputation of missing RxCUI, TTY, SAB, display_name; invalid terminology excluded from mapping",
            "duplicate_policy":"Collapse repeated identity (rxcui,tty,sab,display_name) for mapping-ready CSV only",
            "sample_mapping_ready":preview
        },
        "report_4_visualization":{
            "tty_distribution":ordered(tty),
            "sab_distribution":ordered(sab),
            "name_length_distribution":[{"label":b,"count":lengths[b]} for b in BUCKETS],
            "qc_distribution":ordered(qc),
            "mapping_readiness":[{"label":"Mapping-ready","count":stats["mapping_ready_rows"]},{"label":"Excluded/review before mapping","count":excluded_count}]
        },
        "report_3_multivariate":profile(mapping_path, source_path),
        "report_4_statistics":compute_report4(mapping_path),
        "mapping_handoff":{
            "source": "silver/rxnorm.csv",
            "temporary_output":"mapping_ready.csv",
            "natural_key":["rxcui","tty","sab","display_name"],
            "relationship_claim":"TERM_CANDIDATES_ONLY_NOT_VERIFIED_CLINICAL_EQUIVALENCE",
            "clinical_verified":False,
            "admissible":True,
            "note":"RxNorm current prescribable terminology is not all RxNorm, nor does text parsing provide official RXNREL evidence"
        }
    }
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if html_path:
        Path(html_path).parent.mkdir(parents=True,exist_ok=True)
        Path(html_path).write_text(render_html(report),encoding="utf-8")
    print(json.dumps({"report":"rxnorm_eda","source_rows":stats["input_rows"],"mapping_ready_rows":stats["mapping_ready_rows"],"distinct_rxcui":len(concept_ids),"excluded":excluded_count},ensure_ascii=False),flush=True)
    return report

def render_html(report):
    # Shared by the scheduled Silver pipeline and the published Vercel report.
    from silver_mapping.rxnorm_presentation import render_presentation
    return render_presentation(report)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--rxnorm",required=True)
    p.add_argument("--mapping-ready",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--html")
    opts=p.parse_args()
    analyze(opts.rxnorm,opts.mapping_ready,opts.report,opts.html)
