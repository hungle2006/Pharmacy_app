"""Build Bronze CSVs from downloads and crawlers, migrate prior snapshots safely."""
from __future__ import annotations
import argparse
import csv
import gzip
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

from compact_csv import BUCKET, CANONICAL, KEYS, all_objects, cleanup_legacy_bronze, exists, merge_snapshot, r2
import rxnorm_pipeline
import medi_watch

HERE = Path(__file__).resolve().parent

def json_object(s3, key):
    try:
        return json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except Exception as e:
        from compact_csv import missing
        if missing(e):
            return None
        raise

def excel_to_csv(s3, source_key, output):
    """Preserve original spreadsheet headers; never invent missing columns."""
    workbook = openpyxl.load_workbook(
        io.BytesIO(s3.get_object(Bucket=BUCKET, Key=source_key)["Body"].read()),
        read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = iter(sheet.values)
        headers = [str(x).strip() if x is not None else "" for x in next(rows)]
        if not headers or any(not h for h in headers) or len(headers) != len(set(headers)):
            raise RuntimeError(f"{source_key}: invalid headers")
        count = 0
        with open(output, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                if not row or all(v is None for v in row):
                    continue
                writer.writerow(["" if value is None else str(value) for value in row])
                count += 1
        return headers, count
    finally:
        workbook.close()

def seed_from_old_snapshot(s3, source, out):
    obj = json_object(s3, f"_control/{source}/latest.json")
    if not obj or not obj.get("snapshot"):
        return False
    with tempfile.TemporaryDirectory() as t:
        zip_path = Path(t) / "snapshot.csv.gz"
        s3.download_file(BUCKET, obj["snapshot"], str(zip_path))
        with gzip.open(zip_path, "rt", encoding="utf-8-sig", newline="") as inp, open(out, "w", encoding="utf-8", newline="") as dst:
            while True:
                chunk = inp.read(2**20)
                if not chunk:
                    break
                dst.write(chunk)
    return True

def bootstrap(s3):
    """Make replacements FIRST, verify, THEN old Bronze files can be deleted."""
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        for source, minrows in (("icd10", 1000), ("rxnorm", 1000)):
            if exists(s3, CANONICAL[source]):
                print(f"[SEED SKIP] {source} CSV already exists")
                continue
            incoming = root / f"{source}.csv"
            if not seed_from_old_snapshot(s3, source, incoming):
                raise RuntimeError(f"Missing legacy Silver snapshot for {source}, cannot delete its raw data")
            merge_snapshot(s3, source, incoming, minimum=minrows, allow_removes=(source == "rxnorm"))
        # Seed DAV and MEDI ONLY if the original user-uploaded Excel still exists.
        for source, old_key in (("dav", "DAV.xlsx"), ("medi_hps", "MEDI-2_HPS.xlsx")):
            if exists(s3, CANONICAL[source]):
                continue
            if not exists(s3, old_key):
                print(f"[SEED SKIP] {old_key} no longer exists. Keeping old data untouched.")
                continue
            incoming = root / f"{source}.csv"
            fields, count = excel_to_csv(s3, old_key, incoming)
            if source == "dav":
                if not set(KEYS[source]).issubset(fields):
                    print(f"[SEED SKIP] DAV.xlsx lacks {KEYS[source]}, headers={fields}. Run live crawl instead.")
                    continue
                merge_snapshot(s3, source, incoming, minimum=1)
            else:
                # MEDI-2 HPS is historical: seed ONCE. No automatic 2020 re-download.
                # Use full row as key because the exact source schema can vary by release.
                merge_snapshot(s3, source, incoming, keys=fields, minimum=1)
    # Only after successful writes are existing legacy raw objects deleted.
    cleanup_legacy_bronze(s3, dry_run=False)

def execute(source, s3):
    if source == "medi":
        # Preserve prior policy: monitor release only, never download MEDI-2 2020.
        response = __import__("requests").get(medi_watch.URL, timeout=45)
        response.raise_for_status()
        result = medi_watch.inspect(response.text)
        print(json.dumps({"source": "medi", "status": "version_check_only", **result}))
        if result["versions_after_medi2"] or result["candidate_hps_links"]:
            print("::warning::MEDI newer release candidate found; review manually before ingest")
        return
    with tempfile.TemporaryDirectory() as d:
        wd = Path(d)
        folder = wd / "crawled"
        folder.mkdir()
        incoming = wd / "snapshot.csv"
        if source == "dav":
            subprocess.run([sys.executable, str(HERE/"crawl_dav.py"), "--output-dir", str(folder)], check=True)
            files = list(folder.glob("dav_gia_ban_buon_20*.csv"))
            if len(files) != 1:
                raise RuntimeError(f"DAV failed to produce exactly one complete snapshot: {files}")
            incoming = files[0]
        elif source == "icd10":
            subprocess.run([sys.executable, str(HERE/"crawl_icd10.py"), "--output-dir", str(folder)], check=True)
            incoming = folder / "ICD10_Vietnam_TT06_2026_FULL.csv"
        elif source == "rxnorm":
            url, release = rxnorm_pipeline.latest()
            state = json_object(s3, "_control/compact/rxnorm.json")
            legacy = json_object(s3, "_control/rxnorm/latest.json")
            if exists(s3, CANONICAL["rxnorm"]) and (
                state and state.get("release") == release or
                not state and legacy and legacy.get("release") == release
            ):
                print(f"[UNCHANGED RELEASE] {release}")
                return
            z = wd/release
            rxnorm_pipeline.download(url, z)
            db = rxnorm_pipeline.convert(z, wd/"rxnorm.sqlite")
            try:
                with incoming.open("w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f, lineterminator="\n")
                    w.writerow(rxnorm_pipeline.COLS)
                    w.writerows(db.execute("SELECT * FROM r ORDER BY rxcui,tty,display_name"))
            finally:
                db.close()
        else:
            raise ValueError(source)
        minimum = {"dav": 1000, "icd10": 1000, "rxnorm": 1000}[source]
        result = merge_snapshot(s3, source, incoming, minimum=minimum, allow_removes=(source == "rxnorm"))
        if source == "rxnorm":
            result["release"] = release
            s3.put_object(Bucket=BUCKET, Key="_control/compact/rxnorm.json", Body=json.dumps(result).encode(), ContentType="application/json")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["dav", "icd10", "rxnorm", "medi", "all"])
    p.add_argument("--migrate", action="store_true")
    args = p.parse_args()
    s3 = r2()
    if args.migrate:
        bootstrap(s3)
    if args.source:
        for source in (["dav","icd10","rxnorm","medi"] if args.source=="all" else [args.source]):
            execute(source, s3)

if __name__ == "__main__":
    main()
