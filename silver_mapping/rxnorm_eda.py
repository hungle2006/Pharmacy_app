"""Report 3 (EDA/QC) + Report 4 (visualization) for RxNorm before mapping.

Reads current Silver CSV; does not mutate Bronze/Silver, does not invent links.
Outputs an analysis JSON, a standalone HTML report, and a temporary mapping-ready
CSV with the five raw terminology fields.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

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
    e=report["report_3_eda"];v=report["report_4_visualization"]
    def safe(x):return html.escape(str(x),quote=True)
    def bars(title,items,label_key="label",value_key="count",top=12):
        rows=items[:top]
        maxvalue=max((int(i[value_key]) for i in rows),default=1) or 1
        lines=[]
        for item in rows:
            value=int(item[value_key]);width=round(value/maxvalue*100,2)
            lines.append('<div class="bar-row"><span>'+safe(item[label_key])+'</span><div class="track"><div style="width:'+str(width)+'%"></div></div><b>'+format(value,",")+'</b></div>')
        return '<section class="panel"><h2>'+safe(title)+'</h2>'+''.join(lines)+'</section>'
    missing_rows=''.join('<tr><td>'+safe(x["field"])+'</td><td>'+format(x["count"],",")+'</td><td>'+str(x["percentage"])+'%</td></tr>' for x in e["missing_by_field"])
    html_head="""<!doctype html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PharmaBiz · RxNorm EDA & Mapping</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#183043;font:15px/1.5 system-ui,-apple-system,sans-serif}.shell{max-width:1200px;margin:auto;padding:36px 22px}h1{font-size:36px;margin:12px 0}h2{font-size:18px;margin:0 0 18px}h3{margin-bottom:6px}.eyebrow{letter-spacing:2px;color:#168379;font-size:12px;font-weight:750}p{color:#5c6c79}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}.metric,.panel{background:white;border:1px solid #e3e9ed;border-radius:16px;padding:20px}.metric strong{display:block;font-size:29px;color:#153f54}.metric span{color:#627480;font-size:12px}.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}.bar-row{display:grid;grid-template-columns:105px 1fr 85px;align-items:center;gap:12px;margin:11px 0;font-size:12px}.track{background:#e7eff0;border-radius:12px;height:13px;overflow:hidden}.track div{background:linear-gradient(90deg,#1a9788,#60bbbf);height:100%;border-radius:12px}.bar-row b{text-align:right}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e8ecee;text-align:left}th{color:#58707b}section{margin-bottom:17px}.arrow{color:#178e84;font-weight:700}.flow{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.flow span{padding:12px 17px;border-radius:11px;background:#e9f4f2;font-weight:650}footer{margin-top:25px;color:#687988;font-size:12px}@media(max-width:750px){.grid,.two{grid-template-columns:1fr 1fr}.bar-row{grid-template-columns:75px 1fr 65px}.shell{padding:20px 13px}}@media(max-width:450px){.grid,.two{grid-template-columns:1fr}}</style></head><body><main class="shell"><div class="eyebrow">PHARMABIZ · RXNORM ANALYTICS</div><h1>EDA → Data Visualization → Mapping</h1><p>Dữ liệu thuật ngữ RxNorm từ Silver, báo cáo chất lượng và độ sẵn sàng trước mapping DAV. Đây không phải kết quả thẩm định lâm sàng.</p>"""
    cards=[("Số dòng nguồn",e["total_rows"]),("RxCUI khác nhau",e["distinct_rxcui_mapping_ready"]),("Dòng đủ điều kiện mapping",e["mapping_ready_rows"]),("Tỷ lệ đủ điều kiện",str(e["mapping_ready_rate_pct"])+"%")]
    metrics='<div class="grid">'+''.join('<div class="metric"><span>'+safe(label)+'</span><strong>'+safe(format(val,",") if isinstance(val,int) else val)+'</strong></div>' for label,val in cards)+'</div>'
    r3='<section class="panel"><h2>Report 3 · Khám phá & xử lý dữ liệu</h2><p><strong>Missing values:</strong> không điền giả RxCUI, TTY, SAB hoặc tên. <strong>Normalize:</strong> Unicode NFKD, chữ thường, loại dấu, chuẩn hóa khoảng trắng. <strong>Duplicates:</strong> loại khỏi dữ liệu mapping theo khóa (RxCUI, TTY, SAB, display_name). Bảng gốc không bị sửa.</p><table><thead><tr><th>Cột</th><th>Giá trị thiếu</th><th>Tỷ lệ</th></tr></thead><tbody>'+missing_rows+'</tbody></table></section>'
    r4='<div class="two">'+bars("Report 4 · Phân bố TTY",v["tty_distribution"])+bars("Report 4 · Độ dài tên thuốc",v["name_length_distribution"])+bars("Trạng thái chất lượng Silver",v["qc_distribution"])+bars("Sẵn sàng cho Mapping",v["mapping_readiness"])+'</div>'
    flow='<section class="panel"><h2>Chuyển sang Mapping</h2><div class="flow"><span>RxNorm Silver</span><b class="arrow">→</b><span>EDA / QC / Normalize</span><b class="arrow">→</b><span>Mapping-ready CSV</span><b class="arrow">→</b><span>DAV ↔ RxNorm candidates</span></div><p>Đối chiếu thành phần hoạt chất, hàm lượng, dạng bào chế. Mọi khớp tự động vẫn cần rà soát; không suy ra tương đương thuốc từ trùng tên.</p></section>'
    footer='<footer>Dữ liệu '+safe(report["source"])+' · SHA-256 '+safe(report["source_sha256"])+' · Kết xuất '+safe(report["generated_utc"])+'</footer>'
    return html_head+metrics+r3+r4+flow+footer+"</main></body></html>"

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--rxnorm",required=True)
    p.add_argument("--mapping-ready",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--html")
    opts=p.parse_args()
    analyze(opts.rxnorm,opts.mapping_ready,opts.report,opts.html)
