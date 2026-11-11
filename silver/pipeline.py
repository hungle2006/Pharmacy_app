"""Bronze -> Silver: non-destructive versioned transformation.
Configure source prefixes in sources.json; no synthetic clinical mappings.
"""
import csv
import fnmatch
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import boto3
import polars as pl

BUCKET = os.getenv("R2_BUCKET", "pharmacy-data-lake")
ENDPOINT = os.environ["R2_ENDPOINT"]
CONFIG = Path(os.getenv("SOURCES_CONFIG", "/app/sources.json"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
RX_FIELDS = ["RXCUI","LAT","TS","LUI","STT","SUI","ISPREF","RXAUI",
             "SAUI","SCUI","SDUI","SAB","TTY","CODE","STR","SRL",
             "SUPPRESS","CVF"]

def client():
    return boto3.client("s3", endpoint_url=ENDPOINT, region_name="auto")

def find_latest(s3, prefix, pattern):
    paginator = s3.get_paginator("list_objects_v2")
    matches = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if fnmatch.fnmatch(key.split("/")[-1], pattern):
                matches.append(obj)
    if not matches:
        raise FileNotFoundError(f"Missing Bronze input: {prefix} / {pattern}")
    return max(matches, key=lambda x: (x["LastModified"], x["Key"]))

def normalize(df):
    names = []
    seen = set()
    for col in df.columns:
        name = re.sub(r"[^a-z0-9]+", "_", col.strip().lower()).strip("_") or "field"
        root = name
        i = 2
        while name in seen:
            name = f"{root}_{i}"
            i += 1
        names.append(name)
        seen.add(name)
    df.columns = names
    string_cols = [col for col,dtype in df.schema.items() if dtype == pl.String]
    return df.with_columns([pl.col(c).str.strip_chars().replace("", None) for c in string_cols])

def transform(path, fmt):
    if fmt == "rxnconso":
        # RRF has a trailing separator, no header; read as strings to preserve identifiers.
        df = pl.read_csv(path, separator="|", has_header=False,
                         new_columns=RX_FIELDS+["TRAILING"], infer_schema_length=0,
                         encoding="utf8-lossy", truncate_ragged_lines=False)
        df = df.drop("TRAILING")
        if not {"RXCUI","STR","SAB"}.issubset(set(df.columns)):
            raise ValueError("Invalid RXNCONSO layout")
    elif fmt == "csv":
        df = pl.read_csv(path, infer_schema_length=0, encoding="utf8-lossy")
    else:
        raise ValueError(f"Unsupported format: {fmt}")
    df = normalize(df).unique(maintain_order=True)
    if df.height == 0:
        raise ValueError("Bronze file empty")
    return df

def main():
    s3 = client()
    specs = json.loads(CONFIG.read_text())["sources"]
    results = []
    for spec in specs:
        latest = find_latest(s3, spec["prefix"], spec["glob"])
        key = latest["Key"]
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "source"
            s3.download_file(BUCKET, key, str(src))
            digest = hashlib.sha256(src.read_bytes()).hexdigest()
            version = digest[:16]
            base = f"silver/{spec['name']}/version={version}/"
            manifest_key = base+"manifest.json"
            try:
                s3.head_object(Bucket=BUCKET, Key=manifest_key)
                results.append({"source":spec["name"],"state":"unchanged","version":version})
                continue
            except s3.exceptions.ClientError as exc:
                if exc.response["Error"]["Code"] not in ("404","NoSuchKey","NotFound"):
                    raise
            df = transform(src, spec["format"])
            out = Path(td) / "part-00000.parquet"
            df.write_parquet(out, compression="zstd")
            manifest = {"source":spec["name"],"bronze_key":key,"bronze_sha256":digest,
                        "version":version,"rows":df.height,"columns":df.columns,
                        "created_at":datetime.now(timezone.utc).isoformat()}
            if not DRY_RUN:
                s3.upload_file(str(out), BUCKET, base+"part-00000.parquet")
                s3.put_object(Bucket=BUCKET, Key=manifest_key,
                              Body=json.dumps(manifest,ensure_ascii=False).encode(),
                              ContentType="application/json")
            results.append({"source":spec["name"],"state":"dry_run" if DRY_RUN else "written",
                            "rows":df.height,"version":version})
    print(json.dumps(results,ensure_ascii=False))
if __name__ == "__main__":
    main()
