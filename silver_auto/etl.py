"""Rebuild current rows from the append-only Bronze CSV event stream.

No clinical equivalence or automated DAV-RxNorm/ICD10CM mapping is asserted.
"""
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from silver_v3.quality import strength_signature

META = ("__operation", "__ingested_utc", "__row_hash")
BRONZE = {"dav": "bronze/dav.csv", "icd10": "bronze/icd10.csv",
          "rxnorm": "bronze/rxnorm.csv", "medi_hps": "bronze/medi_hps.csv"}
KEYS = {"dav": ("dav_row_id",), "icd10": ("model", "id"),
        "rxnorm": ("rxcui", "tty", "sab", "display_name")}
ICD = re.compile(r"^[A-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?$")
def text_norm(text):
    s = unicodedata.normalize("NFKD", str(text or "").replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.casefold()).strip()

def source_digest(row, headers):
    payload = json.dumps([row[x] for x in headers], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def load_current(source, path):
    if source not in BRONZE: raise ValueError("Unknown Bronze source: "+source)
    current = {}
    total = Counter()
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames
        if not headers or len(headers) != len(set(headers)) or any(k not in headers for k in META):
            raise ValueError("Invalid Bronze headers")
        raw = [k for k in headers if k not in META]
        if not raw or any(k in raw for k in META):raise ValueError("Empty source schema")
        keycols = KEYS.get(source, tuple(raw))
        if not set(keycols).issubset(raw): raise ValueError("Missing source identity columns")
        for lineno, row in enumerate(reader, start=2):
            total["events"] += 1
            if None in row or any(row.get(k) is None for k in headers):
                raise ValueError(f"Malformed CSV at line {lineno}")
            op = row["__operation"]
            if op not in ("INSERT","UPDATE","REMOVE"):
                raise ValueError(f"Unknown operation at line {lineno}: {op}")
            identity = tuple(row[k].strip() for k in keycols)
            if not all(identity):raise ValueError(f"Empty Bronze identity at line {lineno}")
            if row["__row_hash"] != source_digest(row,raw):
                raise ValueError(f"Bronze integrity mismatch at line {lineno}")
            if op == "REMOVE":
                current.pop(identity, None)
                total["removes"] += 1
            else:
                current[identity] = {k:row[k] for k in raw}
    if not current:raise ValueError("Bronze has no current rows: "+source)
    total["active"] = len(current)
    return raw, list(current.values()), total

def evaluate(source, original):
    row = dict(original)
    flags = []
    if source == "dav":
        ingredient = row.get("dav_active_ingredient_raw", "").strip()
        strength = row.get("dav_strength","").strip()
        row["silver_drug_name_norm"] = text_norm(row.get("dav_drug_name"))
        row["silver_ingredient_search_norm"] = text_norm(ingredient)
        row["silver_form_search_norm"] = text_norm(row.get("dav_dosage_form"))
        row["silver_strength_raw"] = strength
        if not ingredient:flags.append("MISSING_INGREDIENT")
        if not strength:flags.append("MISSING_STRENGTH")
        if strength:
            value,info = strength_signature(strength)
            if value is None:flags.append("STRENGTH_"+info)
            else:
                row["silver_strength_value"] = str(value)
                row["silver_strength_unit"] = info
        if any(ch in ingredient for ch in ("+",";","/")):
            flags.append("COMBINATION_REQUIRES_COMPONENT_EVIDENCE")
    elif source == "rxnorm":
        row["silver_search_name"] = text_norm(row.get("normalized_name") or row.get("display_name"))
        if not row.get("rxcui","").isdigit():flags.append("INVALID_RXCUI")
        if not row.get("tty","").strip():flags.append("MISSING_TTY")
        if not row.get("sab","").strip():flags.append("MISSING_SAB")
        if not row.get("display_name","").strip():flags.append("MISSING_DISPLAY_NAME")
    elif source == "icd10":
        code = row.get("code","").strip().upper()
        row["silver_code_canonical"] = code
        diagnosis_name = row.get("name_vi") or row.get("name_en") or row.get("name") or ""
        row["silver_name_search_norm"] = text_norm(diagnosis_name)
        if not code:flags.append("MISSING_ICD_CODE")
        elif not ICD.fullmatch(code):flags.append("REVIEW_ICD_CODE_FORMAT")
        if not diagnosis_name.strip():flags.append("MISSING_ICD_NAME")
    elif source == "medi_hps":
        flags.append("MEDI_SOURCE_RELEASE_REQUIRES_CURATED_MAPPING")
    else:raise ValueError(source)
    if any(f.startswith("INVALID_") for f in flags): status = "REJECTED"
    elif flags:status = "REVIEW_REQUIRED"
    else:status = "ACCEPTED"
    row["silver_qc_status"] = status
    row["silver_qc_flags"] = "|".join(sorted(set(flags)))
    row["silver_mapping_verified"] = "false"
    return row

def write_outputs(source, bronze_csv, folder, source_sha):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    raw, active, stats = load_current(source,bronze_csv)
    enriched = [evaluate(source,r) for r in active]
    extra = []
    for r in enriched:
        for k in r:
            if k not in raw and k not in extra:extra.append(k)
    headers = raw + extra
    counters = Counter(r["silver_qc_status"] for r in enriched)
    if counters["REJECTED"] / len(enriched) > 0.05:
        raise ValueError("Quality gate: more than 5% rejected")
    outputs = {}
    for subset,status in (("all",None),("accepted","ACCEPTED"),
                          ("review","REVIEW_REQUIRED"),("rejected","REJECTED")):
        path=folder/(subset+".csv")
        with path.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=headers,lineterminator="\n")
            writer.writeheader()
            for row in enriched:
                if status is None or row["silver_qc_status"]==status:writer.writerow(row)
        outputs[subset+".csv"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"source":source,"bronze_key":BRONZE[source],
       "bronze_sha256":source_sha,"events":stats["events"],"active_rows":stats["active"],
       "remove_events":stats["removes"],"accepted":counters["ACCEPTED"],
       "review":counters["REVIEW_REQUIRED"],"rejected":counters["REJECTED"],
       "mapping_verified":False,"columns":headers,"output_sha256":outputs,
       "built_utc":datetime.now(timezone.utc).isoformat()}
    (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf8")
    return manifest
