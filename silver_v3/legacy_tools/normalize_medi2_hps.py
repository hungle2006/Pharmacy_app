#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, csv, re, unicodedata
from collections import Counter
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

def _col_index(ref):
    m = re.match(r"([A-Z]+)", ref)
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1

def read_first_sheet_xlsx(path):
    import zipfile
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{NS}si"):
                t = si.find(f"{NS}t")
                if t is not None:
                    shared.append(t.text or "")
                else:
                    shared.append("".join((rt.text or "") for rt in si.findall(f"{NS}r/{NS}t")))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        relmap = {x.attrib["Id"]: x.attrib["Target"] for x in rels}
        first = wb.find(f"{NS}sheets")[0]
        target = relmap[first.attrib[rid_ns]]
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")

        rows = []
        max_col = 0
        for _, elem in ET.iterparse(z.open(target), events=("end",)):
            if elem.tag == f"{NS}row":
                vals = {}
                for c in elem.findall(f"{NS}c"):
                    idx = _col_index(c.attrib.get("r", "A1"))
                    t = c.attrib.get("t")
                    v = c.find(f"{NS}v")
                    val = ""
                    if t == "s" and v is not None:
                        val = shared[int(v.text)]
                    elif t == "inlineStr":
                        tt = c.find(f".//{NS}t")
                        val = tt.text if tt is not None else ""
                    elif v is not None:
                        val = v.text or ""
                    vals[idx] = val
                    max_col = max(max_col, idx)
                row = [""] * (max_col + 1)
                for idx, val in vals.items():
                    if idx >= len(row):
                        row.extend([""] * (idx - len(row) + 1))
                    row[idx] = val
                rows.append(row)
                elem.clear()

    width = max(len(r) for r in rows) if rows else 0
    rows = [r + [""] * (width - len(r)) for r in rows]
    headers = rows[0]
    return [dict(zip(headers, r)) for r in rows[1:]]

def _xlsx_col_name(n):
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s

def _xml_escape(v):
    from xml.sax.saxutils import escape
    return escape("" if v is None else str(v), {'"': '&quot;'})

def _sheet_xml(headers, rows, widths=None, freeze=True):
    widths = widths or {}
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    ]
    if freeze:
        parts.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    if widths:
        parts.append("<cols>")
        for idx, width in sorted(widths.items()):
            parts.append(f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>')
        parts.append("</cols>")
    parts.append("<sheetData>")

    all_rows = [headers] + rows
    for r_idx, row in enumerate(all_rows, start=1):
        parts.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row, start=1):
            if value is None or value == "":
                continue
            ref = f"{_xlsx_col_name(c_idx)}{r_idx}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                txt = _xml_escape(value)
                style = ' s="1"' if r_idx == 1 else ''
                parts.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{txt}</t></is></c>')
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)

def write_simple_xlsx(path, sheets):
    import zipfile
    from pathlib import Path
    path = Path(path)

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    ]
    for i in range(1, len(sheets)+1):
        content_types.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    content_types.append("</Types>")

    workbook = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        '<sheets>'
    ]
    for i, (name, _, _, _) in enumerate(sheets, start=1):
        workbook.append(f'<sheet name="{_xml_escape(name)}" sheetId="{i}" r:id="rId{i}"/>')
    workbook.append('</sheets></workbook>')

    wb_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    ]
    for i in range(1, len(sheets)+1):
        wb_rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    wb_rels.append(f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    wb_rels.append("</Relationships>")

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1">'
        '<alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs>'
        '</styleSheet>'
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(content_types))
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", "".join(workbook))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wb_rels))
        z.writestr("xl/styles.xml", styles)
        for i, (_, headers, rows, widths) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(headers, rows, widths=widths))

def strip_accents(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c))

def clean_text(s):
    s = str(s or "").replace("\u00a0"," ").replace("–","-").replace("—","-")
    return re.sub(r"\s+"," ",s).strip()

def norm_text(s):
    s = strip_accents(clean_text(s)).lower().replace("đ","d")
    s = re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def normalize_code(vocab, code_raw):
    vocab = clean_text(vocab).upper()
    c = clean_text(code_raw).upper().replace(" ","")
    review = []
    code_type = "single"
    start = end = ""
    normalized = c
    nodot = ""
    code3 = ""
    eligible = 0

    if "-" in c:
        start, end = c.split("-",1)
        code_type = "range"
        normalized = f"{start}-{end}"
        review.append("RANGE_CODE_NOT_DIRECT_EXACT_MAPPING_KEY")
    else:
        if vocab == "ICD10CM":
            if "." not in c and re.fullmatch(r"[A-Z][0-9][0-9A-Z][0-9A-Z]{1,4}", c):
                c = c[:3] + "." + c[3:]
            normalized = c
            nodot = c.replace(".","")
            code3 = nodot[:3]
            eligible = 1 if re.fullmatch(r"[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?", c) else 0
            if not eligible:
                review.append("NONSTANDARD_ICD10CM_SINGLE_CODE")
        elif vocab == "ICD9CM":
            normalized = c
            nodot = c.replace(".","")
            if not re.fullmatch(r"[VE]?[0-9]{2,3}(?:\.[0-9]{1,2})?", c):
                review.append("NONSTANDARD_ICD9CM_SINGLE_CODE")
        else:
            review.append("UNSUPPORTED_VOCABULARY")

    return normalized,nodot,code3,code_type,start,end,eligible,review

def normalize(input_xlsx: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = read_first_sheet_xlsx(input_xlsx)
    rows = []
    review_counts = Counter()
    seen = set()
    duplicates_removed = 0

    for i, r in enumerate(raw, start=1):
        key = tuple(clean_text(r.get(h,"")) for h in ["RXCUI","DRUG_DESCRIPTION","VOCABULARY","CODE","INDICATION_DESCRIPTION"])
        if key in seen:
            duplicates_removed += 1
            continue
        seen.add(key)

        rxcui = clean_text(r.get("RXCUI",""))
        drug = clean_text(r.get("DRUG_DESCRIPTION",""))
        vocab = clean_text(r.get("VOCABULARY","")).upper()
        code_raw = clean_text(r.get("CODE",""))
        indication = clean_text(r.get("INDICATION_DESCRIPTION",""))
        normalized,nodot,code3,ctype,start,end,eligible,review = normalize_code(vocab, code_raw)

        if not re.fullmatch(r"\d+", rxcui):
            review.append("NONNUMERIC_RXCUI")
        for x in set(review):
            review_counts[x] += 1

        rows.append({
            "medi_relation_id": f"MEDI2HPS_{len(rows)+1:06d}",
            "source_row_id": i,
            "rxcui": rxcui,
            "drug_description": drug,
            "drug_description_norm": norm_text(drug),
            "code_system": vocab,
            "code_raw": code_raw,
            "code_normalized": normalized,
            "code_nodot": nodot,
            "code3": code3,
            "code_type": ctype,
            "code_range_start": start,
            "code_range_end": end,
            "indication_description": indication,
            "indication_description_norm": norm_text(indication),
            "icd10_vietnam_mapping_key": nodot if (vocab=="ICD10CM" and ctype=="single") else "",
            "eligible_exact_icd10_vietnam_mapping": eligible if (vocab=="ICD10CM" and ctype=="single") else 0,
            "relation_key": f"{rxcui}|{vocab}|{normalized}",
            "normalization_status": "REVIEW" if review else "READY",
            "review_reason": "|".join(dict.fromkeys(review)),
        })

    headers = list(rows[0].keys()) if rows else []
    csv_path = output_dir / "MEDI-2_HPS_normalized.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader(); w.writerows(rows)

    qc = [
        ["metric","value"],
        ["input_rows",len(raw)],
        ["exact_duplicate_rows_removed",duplicates_removed],
        ["output_rows",len(rows)],
        ["unique_rxcui",len({r["rxcui"] for r in rows})],
        ["unique_relation_key",len({r["relation_key"] for r in rows})],
        ["icd10cm_rows",sum(r["code_system"]=="ICD10CM" for r in rows)],
        ["icd9cm_rows",sum(r["code_system"]=="ICD9CM" for r in rows)],
        ["icd10cm_single_mapping_eligible",sum(r["eligible_exact_icd10_vietnam_mapping"]==1 for r in rows)],
        ["range_code_rows",sum(r["code_type"]=="range" for r in rows)],
        ["ready_rows",sum(r["normalization_status"]=="READY" for r in rows)],
        ["review_rows",sum(r["normalization_status"]=="REVIEW" for r in rows)],
    ]
    qc += [[f"review_reason__{k}",v] for k,v in review_counts.most_common()]
    qc_path = output_dir / "MEDI-2_HPS_normalization_qc.csv"
    with qc_path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(qc)

    xlsx_rows = [[r[h] for h in headers] for r in rows]
    xlsx_path = output_dir / "MEDI-2_HPS_Normalized.xlsx"
    widths = {1:22,2:12,3:14,4:40,5:36,6:14,7:20,8:20,9:18,10:12,11:12,12:18,13:18,14:55,15:45,16:24,17:18,18:34,19:16,20:38}
    write_simple_xlsx(xlsx_path, [
        ("MEDI2_HPS_NORMALIZED", headers, xlsx_rows, widths),
        ("QC_SUMMARY", qc[0], qc[1:], {1:42,2:20}),
    ])

    print("DONE")
    print("Input rows:", len(raw))
    print("Duplicates removed:", duplicates_removed)
    print("Output rows:", len(rows))
    print("ICD10CM:", sum(r["code_system"]=="ICD10CM" for r in rows))
    print("ICD9CM:", sum(r["code_system"]=="ICD9CM" for r in rows))
    print("Exact ICD10 VN mapping eligible:", sum(r["eligible_exact_icd10_vietnam_mapping"]==1 for r in rows))
    print("Excel:", xlsx_path)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="MEDI-2_HPS.xlsx")
    ap.add_argument("--output-dir", default="medi2_hps_normalized_output")
    args = ap.parse_args()
    normalize(Path(args.input).resolve(), Path(args.output_dir).resolve())