#!/usr/bin/env python3
"""End-to-end EDA for the nine user-supplied patient-narrative files.

Run:
    pip install pandas pyarrow matplotlib numpy openpyxl
    python research/eda_all_datasets.py --input-dir /content/patient_data --output-dir /content/eda_output

Design constraints:
- Process Parquet by record batches (do not load ~900 MB of compressed input into RAM).
- Read ZIP members in place; inventory *all* members, flag unsupported formats.
- Track exact normalized-text overlap in on-disk SQLite, not an in-memory giant set.
- Never export raw patient narratives, author names, emails, phone numbers, IDs.
- Counts describe the collected datasets, not population prevalence or diagnoses.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pyarrow.parquet as pq

EXPECTED = [
    "train-00000-of-00001.parquet", "train.parquet",
    "train (1).parquet", "train (2).parquet", "train (3).parquet",
    "ViMedical_Disease.csv", "Corpus_Redone.zip",
    "Question_for_dataset.zip", "Corpus.zip",
]
TEXT_NAMES = ("question", "patient_question", "patient_text", "symptom_text",
              "complaint", "utterance", "prompt", "input", "query",
              "text", "content", "instruction", "sentence",
              "description", "user_message", "messages")
LABEL_NAMES = ("disease", "disease_label", "diagnosis", "diagnostic",
               "label", "icd10", "icd_code", "category", "class")
SYMPTOM_TERMS = (
    "đau", "sốt", "ho", "mệt", "buồn nôn", "chóng mặt", "đau bụng",
    "đau đầu", "khó thở", "tiểu buốt", "tiểu nhiều", "tiểu rát",
    "ợ chua", "ngứa", "tiêu chảy", "đau ngực", "mất ngủ", "nôn",
    "đau họng", "đau lưng", "khát nước", "phát ban"
)
PII = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone_candidate": re.compile(r"(?<!\d)(?:\+?84|0)[ .-]?(?:\d[ .-]?){8,10}(?!\d)"),
}
BOILERPLATE = re.compile(r"tôi có thể đang bị bệnh gì\s*\??", re.I)
DATE_WORDS = re.compile(r"\b(?:\d+\s*(?:ngày|tuần|tháng|năm)|mấy\s*(?:ngày|tuần)|hôm qua|hôm nay|gần đây)\b", re.I)
NEGATION = re.compile(r"\b(?:không có|không bị|chưa thấy|không thấy|không hề)\b", re.I)

def norm_col(x):
    return re.sub(r"[\s_-]+", "", str(x).lower())

def choose_column(columns, terms):
    d = {norm_col(x): x for x in columns}
    for name in terms:
        if norm_col(name) in d:
            return d[norm_col(name)]
    for name in terms:
        for col in columns:
            if norm_col(name) in norm_col(col):
                return col
    return None

def get_text(v):
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    if isinstance(v, str):
        return v.strip()
    # A conversation may be stored as an array of role/content dictionaries.
    if isinstance(v, (list, tuple)):
        for item in v:
            if isinstance(item, dict) and str(item.get("role", "")).lower() in ("user", "patient", "human"):
                return get_text(item.get("content") or item.get("text") or "")
        return ""
    if isinstance(v, dict):
        for key in ("user", "question", "patient", "content", "text"):
            if key in v:
                return get_text(v[key])
        return ""
    return ""

def fingerprint(txt):
    txt = re.sub(r"\s+", " ", txt.casefold()).strip()
    return hashlib.blake2b(txt.encode("utf-8"), digest_size=16).hexdigest()

def safe_cell(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple, dict)):
        return "<nested>"
    return str(v)[:160].replace("\n", " ")

def save_csv(path, rows, headers):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

class Collector:
    def __init__(self, path, maximum):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS presence(digest TEXT, source TEXT, PRIMARY KEY(digest,source))")
        self.db.execute("CREATE TABLE IF NOT EXISTS labeled(digest TEXT, source TEXT, disease TEXT, PRIMARY KEY(digest,source,disease))")
        self.db.commit()
        self.maximum = maximum
        self.metrics = {}
        self.members = []
        self.fields = defaultdict(lambda: {"nonempty": 0, "seen": 0})
        self.labels = Counter()
        self.symptoms = Counter()
        self.errors = []
        self.batches = 0

    def init_source(self, name, size):
        self.metrics[name] = {
            "source": name, "bytes": size, "status": "pending",
            "rows": 0, "rows_with_text": 0, "missing_text": 0,
            "exact_duplicate_rows": 0, "potential_pii_rows": 0,
            "boilerplate_rows": 0, "time_context_rows": 0,
            "negated_rows": 0, "word_count_sum": 0, "char_count_sum": 0,
            "detected_text_columns": set(), "detected_label_columns": set(),
            "content_formats": Counter(), "scanned_members": 0,
            "unsupported_members": 0, "failed_members": 0
        }

    def ingest(self, source, records, columns=None, member=""):
        stat = self.metrics[source]
        cols = list(columns) if columns else []
        pending_presence, pending_labels = [], []
        text_col = choose_column(cols, TEXT_NAMES) if cols else None
        label_col = choose_column(cols, LABEL_NAMES) if cols else None
        if text_col:
            stat["detected_text_columns"].add(str(text_col))
        if label_col:
            stat["detected_label_columns"].add(str(label_col))
        for rec in records:
            if self.maximum and stat["rows"] >= self.maximum:
                break
            if not isinstance(rec, dict):
                rec = {"text": str(rec)}
            stat["rows"] += 1
            if not cols:
                cols = list(rec.keys())
                text_col = choose_column(cols, TEXT_NAMES)
                label_col = choose_column(cols, LABEL_NAMES)
                if text_col:
                    stat["detected_text_columns"].add(str(text_col))
                if label_col:
                    stat["detected_label_columns"].add(str(label_col))
            for key, value in rec.items():
                z = self.fields[(source, str(key))]
                z["seen"] += 1
                if value is not None and str(value).strip().lower() not in ("", "nan", "none", "null"):
                    z["nonempty"] += 1
            text = get_text(rec.get(text_col)) if text_col else ""
            disease = safe_cell(rec.get(label_col)).strip() if label_col else ""
            if disease:
                self.labels[(source, disease)] += 1
            if not text:
                stat["missing_text"] += 1
                continue
            stat["rows_with_text"] += 1
            stat["word_count_sum"] += len(text.split())
            stat["char_count_sum"] += len(text)
            if BOILERPLATE.search(text): stat["boilerplate_rows"] += 1
            if DATE_WORDS.search(text): stat["time_context_rows"] += 1
            if NEGATION.search(text): stat["negated_rows"] += 1
            if any(pattern.search(text) for pattern in PII.values()):
                stat["potential_pii_rows"] += 1
            low = text.casefold()
            for term in SYMPTOM_TERMS:
                if term in low: self.symptoms[(source, term)] += 1
            d = fingerprint(text)
            pending_presence.append((d, source))
            if disease: pending_labels.append((d, source, disease[:160]))
        if pending_presence:
            before = self.db.total_changes
            self.db.executemany("INSERT OR IGNORE INTO presence VALUES(?,?)", pending_presence)
            distinct_new = self.db.total_changes - before
            stat["exact_duplicate_rows"] += len(pending_presence) - distinct_new
        if pending_labels:
            self.db.executemany("INSERT OR IGNORE INTO labeled VALUES(?,?,?)", pending_labels)
        self.batches += 1
        if self.batches % 25 == 0: self.db.commit()

def read_pandas_batches(frame, c, source, member=""):
    if isinstance(frame, pd.DataFrame):
        if len(frame) <= 3000:
            c.ingest(source, frame.to_dict(orient="records"), frame.columns, member)
        else:
            for i in range(0, len(frame), 3000):
                c.ingest(source, frame.iloc[i:i+3000].to_dict(orient="records"), frame.columns, member)
    else:
        for batch in frame:
            c.ingest(source, batch.to_dict(orient="records"), batch.columns, member)
            if c.maximum and c.metrics[source]["rows"] >= c.maximum: break

def scan_parquet(path, c, source, member=""):
    p = pq.ParquetFile(path)
    for batch in p.iter_batches(batch_size=2500):
        c.ingest(source, batch.to_pylist(), batch.schema.names, member)
        if c.maximum and c.metrics[source]["rows"] >= c.maximum: break
    return {"parquet_metadata_rows": p.metadata.num_rows,
            "columns": list(p.schema_arrow.names), "row_groups": p.metadata.num_row_groups}

def scan_tabular(file, ext, c, source, member=""):
    if ext in (".csv", ".tsv"):
        delim = "\t" if ext == ".tsv" else ","
        f = io.TextIOWrapper(file, encoding="utf-8-sig", errors="replace", newline="")
        # csv.DictReader correctly handles multiline quoted narratives.
        reader = csv.DictReader(f, delimiter=delim)
        buf = []
        for rec in reader:
            buf.append(rec)
            if len(buf) == 2500:
                c.ingest(source, buf, reader.fieldnames, member)
                buf = []
            if c.maximum and c.metrics[source]["rows"] >= c.maximum: break
        if buf: c.ingest(source, buf, reader.fieldnames, member)
        return {"columns": reader.fieldnames or []}
    if ext in (".jsonl", ".ndjson"):
        f = io.TextIOWrapper(file, encoding="utf-8-sig", errors="replace")
        buf = []
        for line in f:
            if not line.strip(): continue
            try: buf.append(json.loads(line))
            except json.JSONDecodeError: continue
            if len(buf) >= 1000:
                c.ingest(source, buf, member=member);buf=[]
            if c.maximum and c.metrics[source]["rows"] >= c.maximum: break
        if buf: c.ingest(source, buf, member=member)
        return {}
    if ext == ".json":
        obj = json.load(io.TextIOWrapper(file, encoding="utf-8-sig", errors="replace"))
        if isinstance(obj, dict):
            candidate = next((v for v in obj.values() if isinstance(v, list)), None)
            obj = candidate if candidate is not None else [obj]
        if not isinstance(obj, list): obj = [obj]
        for i in range(0,len(obj),1500):
            c.ingest(source, obj[i:i+1500], member=member)
            if c.maximum and c.metrics[source]["rows"] >= c.maximum: break
        return {}
    if ext in (".txt", ".md"):
        f = io.TextIOWrapper(file, encoding="utf-8-sig", errors="replace")
        buf = []
        for line in f:
            if not line.strip(): continue
            buf.append({"text": line.strip()})
            if len(buf) >= 2000:
                c.ingest(source, buf, ["text"], member)
                buf=[]
            if c.maximum and c.metrics[source]["rows"] >= c.maximum: break
        if buf: c.ingest(source, buf, ["text"], member)
        return {"interpretation": "one non-empty line per record"}
    raise ValueError("unsupported input type " + ext)

def process_zip(path, c, source):
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir():continue
            name = info.filename
            ext = Path(name).suffix.lower()
            entry = {"source": source, "member": name, "uncompressed_bytes": info.file_size,
                     "compressed_bytes": info.compress_size, "format": ext, "status": "", "rows_added": 0}
            old = c.metrics[source]["rows"]
            if info.file_size > 1024**3:
                entry["status"]="SKIPPED_MEMBER_OVER_1GB"
                c.metrics[source]["unsupported_members"] += 1
            elif ext in (".csv", ".tsv", ".txt", ".md", ".jsonl", ".ndjson", ".json"):
                try:
                    with z.open(info) as stream:
                        scan_tabular(stream, ext, c, source, name)
                    entry["status"]="SCANNED"
                    c.metrics[source]["scanned_members"] += 1
                    c.metrics[source]["content_formats"][ext] += 1
                except Exception as e:
                    entry["status"]="ERROR_" + type(e).__name__
                    c.metrics[source]["failed_members"] += 1
                    c.errors.append({"source": source, "member": name, "error": str(e)[:200]})
            elif ext == ".parquet":
                try:
                    # pyarrow requires seekable file; ZIP entry is copied individually, not the whole archive.
                    with z.open(info) as src, tempfile.NamedTemporaryFile(suffix=".parquet") as temp:
                        while True:
                            chunk = src.read(2**20)
                            if not chunk: break
                            temp.write(chunk)
                        temp.flush()
                        scan_parquet(temp.name, c, source, name)
                    entry["status"]="SCANNED"
                    c.metrics[source]["scanned_members"] += 1
                    c.metrics[source]["content_formats"][ext] += 1
                except Exception as e:
                    entry["status"]="ERROR_" + type(e).__name__
                    c.metrics[source]["failed_members"] += 1
                    c.errors.append({"source": source, "member": name, "error": str(e)[:200]})
            else:
                entry["status"]="UNSUPPORTED_FORMAT"
                c.metrics[source]["unsupported_members"] += 1
            entry["rows_added"]=c.metrics[source]["rows"]-old
            c.members.append(entry)
            if c.maximum and c.metrics[source]["rows"]>=c.maximum: break

def plot_bar(path, names, vals, xlabel, title):
    if not names: return
    fig,ax=plt.subplots(figsize=(11, 5))
    ax.barh(names[::-1], vals[::-1])
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input-dir",required=True,help="Folder containing all nine files")
    ap.add_argument("--output-dir",default="eda_output")
    ap.add_argument("--max-rows",type=int,default=0,help="0 = all rows, or positive for quick smoke test")
    args=ap.parse_args()
    base=Path(args.input_dir);out=Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    db=out/"text_presence.sqlite3"
    c=Collector(db,args.max_rows)
    for name in EXPECTED:
        path=base/name
        c.init_source(name,path.stat().st_size if path.exists() else 0)
        st=c.metrics[name]
        if not path.exists():
            st["status"]="MISSING_FILE"
            print("[MISSING]",name)
            continue
        print("[START]",name,flush=True)
        try:
            ext=path.suffix.lower()
            if ext==".zip":
                process_zip(path,c,name)
            elif ext==".parquet":
                meta=scan_parquet(path,c,name)
                st["metadata"]=meta
                st["content_formats"][".parquet"]+=1
            else:
                with open(path,"rb") as f: scan_tabular(f,ext,c,name)
                st["content_formats"][ext]+=1
            st["status"]="DONE" if st["failed_members"]==0 else "PARTIAL_ERRORS"
        except Exception as e:
            st["status"]="ERROR_"+type(e).__name__
            c.errors.append({"source":name,"member":"","error":str(e)[:300]})
        c.db.commit()
        print("[DONE]",name,st["status"],"rows:",st["rows"],flush=True)

    metrics=[]
    for name in EXPECTED:
        r=c.metrics[name]
        n=r["rows_with_text"]
        r_out={k:v for k,v in r.items() if k not in ("detected_text_columns","detected_label_columns","content_formats","metadata")}
        r_out["unique_text"]=n-r["exact_duplicate_rows"]
        r_out["duplicate_rate"]=round(100*r["exact_duplicate_rows"]/n,2) if n else None
        r_out["avg_words"]=round(r["word_count_sum"]/n,2) if n else None
        r_out["avg_characters"]=round(r["char_count_sum"]/n,2) if n else None
        r_out["boilerplate_rate"]=round(100*r["boilerplate_rows"]/n,2) if n else None
        r_out["text_columns"]=" | ".join(sorted(r["detected_text_columns"]))
        r_out["label_columns"]=" | ".join(sorted(r["detected_label_columns"]))
        r_out["source_formats"]=" | ".join(sorted(r["content_formats"]))
        r_out["parquet_metadata_rows"]=r.get("metadata",{}).get("parquet_metadata_rows")
        r_out["parquet_row_groups"]=r.get("metadata",{}).get("row_groups")
        metrics.append(r_out)
    save_csv(out/"source_metrics.csv",metrics,list(metrics[0]))
    save_csv(out/"zip_members.csv",c.members,["source","member","uncompressed_bytes","compressed_bytes","format","status","rows_added"])
    labels=[{"source":s,"label":lab,"count":num} for (s,lab),num in c.labels.most_common()]
    save_csv(out/"disease_labels.csv",labels,["source","label","count"])
    symptoms=[{"source":s,"keyword":kw,"count":num} for (s,kw),num in c.symptoms.most_common()]
    save_csv(out/"symptom_keyword_heuristics.csv",symptoms,["source","keyword","count"])
    fields=[{"source":source,"column":col,"seen":x["seen"],"nonempty":x["nonempty"],
             "missing":x["seen"]-x["nonempty"],
             "completeness_pct":round(100*x["nonempty"]/x["seen"],2) if x["seen"] else 0}
             for (source,col),x in sorted(c.fields.items())]
    save_csv(out/"column_completeness.csv",fields,["source","column","seen","nonempty","missing","completeness_pct"])

    overlap=[]
    c.db.commit()
    for a,b,n in c.db.execute(
        """SELECT a.source,b.source,COUNT(*) FROM presence a JOIN presence b
           ON a.digest=b.digest AND a.source<b.source
           GROUP BY a.source,b.source ORDER BY 3 DESC"""
    ):
        overlap.append({"source_a":a,"source_b":b,"exact_text_overlap":n})
    save_csv(out/"cross_source_overlap.csv",overlap,["source_a","source_b","exact_text_overlap"])
    conflicts=c.db.execute(
        """SELECT COUNT(*) FROM (
             SELECT digest FROM labeled GROUP BY digest HAVING COUNT(DISTINCT disease)>1
           )"""
    ).fetchone()[0]
    c.db.close()
    save_csv(out/"errors.csv",c.errors,["source","member","error"])

    plot_bar(out/"source_record_counts.png",[r["source"] for r in metrics],[r["rows"] for r in metrics],
             "Scanned records", "Records per uploaded file (not deduplicated)")
    plot_bar(out/"duplicate_rates.png",[r["source"] for r in metrics],[r["duplicate_rate"] or 0 for r in metrics],
             "% within-source exact normalized text duplicates","Exact normalized-text duplicates")
    major=[(s,k,v) for (s,k),v in c.symptoms.most_common(20)]
    plot_bar(out/"top_symptom_keyword_mentions.png",[s[:11]+":"+k for s,k,v in major],[v for s,k,v in major],
             "Number of rows containing keyword","Keyword heuristics: not validated symptom extraction")

    total=sum(r["rows"] for r in metrics)
    notable=[
        "Dataset row counts are NOT population prevalence or case incidence.",
        "Exact-text overlap is measured after case-folding and whitespace normalization only; semantic near-duplicates remain.",
        "Keyword counts are heuristic mentions, not clinically validated entities; negation requires separate annotation.",
        "Synthetic prompts and real patients must be distinguished by verified provenance, not guessed from writing style.",
        "Labels under different ICD systems must never be joined blindly; check code_system and matching status.",
        "ZIP unsupported/failed entries are in zip_members.csv / errors.csv and are not counted as analyzed samples.",
        "Never upload raw identifiable patient narratives to a public dashboard."
    ]
    report=[
        "# Overall Picture — Vietnamese Patient Symptom Datasets",
        "",
        "**Status:** Processing summary generated from all supplied input files present in the input directory.",
        f"**Processed records (sum, before cross-source deduplication):** {total:,}",
        f"**Unique source files expected:** {len(EXPECTED)}",
        f"**Cross-source pairs with exact overlap:** {len(overlap)}",
        f"**Text hashes associated with >1 distinct disease label:** {conflicts:,}",
        "",
        "## Per-source metrics",
        "",
        "| File | Status | Rows scanned | Rows with text | Unique text | Exact dup % | Avg words |",
        "|---|---|---:|---:|---:|---:|---:|"
    ]
    for r in metrics:
        report.append(f"| {r['source']} | {r['status']} | {r['rows']:,} | {r['rows_with_text']:,} | {r['unique_text']:,} | {r['duplicate_rate'] or 0:.2f} | {r['avg_words'] or 0:.2f} |")
    report+=["","## Label ambiguity",f"- Unique normalized texts associated with multiple disease labels: **{conflicts:,}**.","",
             "## Data interpretation cautions"]
    report+=["- "+x for x in notable]
    report+=["","## Artifacts", "- source_metrics.csv — each of the 9 files",
             "- zip_members.csv — contents and scan status for every ZIP member",
             "- column_completeness.csv — observed schema and missingness",
             "- disease_labels.csv — source label frequencies",
             "- symptom_keyword_heuristics.csv — exploratory keyword mentions",
             "- cross_source_overlap.csv — exact text overlap between files",
             "- errors.csv — parsing errors",
             "- three PNG charts and text_presence.sqlite3 (hashed text only)."]
    (out/"overall_report.md").write_text("\n".join(report),encoding="utf-8")
    print("\n".join(report[:17]))
    print("[OUTPUT]",out.resolve())

if __name__=="__main__":
    main()
