"""Compact Silver: exactly one CSV per available Bronze source on Cloudflare R2.

Source state is reconstructed from Bronze's cumulative event CSV. QC flags and
original fields stay in the same CSV, with no per-run versions or duplicate
accepted/review/rejected objects. Only small control JSON is stored outside Silver.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from silver_auto.etl import BRONZE, write_outputs

BUCKET = os.getenv("R2_BUCKET", "pharmacy-data-lake")
CONTROL_PREFIX = "_control/silver"
SILVER_PREFIX = "silver"

def pipeline_revision():
    paths = [Path(__file__), Path(__file__).with_name("etl.py"),
             Path(__file__).parent.parent / "silver_v3" / "quality.py"]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]

def missing(exc):
    from botocore.exceptions import ClientError
    return isinstance(exc, ClientError) and exc.response.get("Error", {}).get("Code") in (
        "404", "NotFound", "NoSuchKey")

def get_json(s3, key):
    try:
        return json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except Exception as exc:
        if missing(exc):
            return None
        raise

def client():
    import boto3
    required = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    absent = [name for name in required if not os.getenv(name)]
    if absent:
        raise RuntimeError("Missing existing R2 GitHub secrets: " + ", ".join(absent))
    return boto3.client(
        "s3", region_name="auto",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])

def head_or_none(s3, key):
    try:
        return s3.head_object(Bucket=BUCKET, Key=key)
    except Exception as exc:
        if missing(exc):
            return None
        raise

def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as input_file:
        for data in iter(lambda: input_file.read(2 ** 20), b""):
            digest.update(data)
    return digest.hexdigest()

def enumerate_keys(s3, prefix):
    token = None
    while True:
        request = {"Bucket": BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            request["ContinuationToken"] = token
        page = s3.list_objects_v2(**request)
        for item in page.get("Contents", []):
            yield item["Key"]
        if not page.get("IsTruncated"):
            break
        token = page["NextContinuationToken"]

def cleanup_legacy(s3, source, expected_sha, dry_run=False):
    """Remove only proven old Silver copies for this source, never Bronze.

    The replacement silver/{source}.csv must already exist and match SHA-256.
    """
    new_key = f"{SILVER_PREFIX}/{source}.csv"
    current = head_or_none(s3, new_key)
    if not current or current.get("Metadata", {}).get("sha256") != expected_sha:
        raise RuntimeError("Refusing legacy deletion: new Silver CSV not verified")
    keys = []
    for prefix in (
        f"{SILVER_PREFIX}/{source}/",       # original sha256=... directories
        f"{SILVER_PREFIX}/v4/{source}/",    # old version=... directories
        f"{SILVER_PREFIX}/v3/{source}/",    # optional prior output format
    ):
        keys.extend(enumerate_keys(s3, prefix))
    for key in sorted(set(keys)):
        if not dry_run:
            s3.delete_object(Bucket=BUCKET, Key=key)
            if head_or_none(s3, key):
                raise RuntimeError("Legacy deletion did not complete: " + key)
    return len(set(keys))

def process(s3, source, base, dry_run=False, cleanup=False):
    if source not in BRONZE:
        raise ValueError("Unknown Silver source")
    if source == "medi_hps":
        release = os.getenv("MEDI_HPS_APPROVED_RELEASE", "").strip()
        if not release or release.startswith("2020"):
            return {"source": source, "state": "skipped", "reason": "MEDI newer release not approved"}
        provenance = get_json(s3, "_control/compact/medi_hps.json")
        if not provenance or provenance.get("release") != release:
            return {"source": source, "state": "skipped", "reason": "MEDI Bronze release provenance unverified"}
    bronze_key = BRONZE[source]
    bronze_head = head_or_none(s3, bronze_key)
    if bronze_head is None:
        return {"source": source, "state": "skipped", "reason": "Bronze CSV not available"}
    if bronze_head.get("ContentLength", 0) <= 0:
        raise ValueError("Bronze empty: " + bronze_key)

    out_key = f"{SILVER_PREFIX}/{source}.csv"
    ctl_key = f"{CONTROL_PREFIX}/{source}.json"
    state = get_json(s3, ctl_key)
    revision = pipeline_revision()
    source_hash_meta = bronze_head.get("Metadata", {}).get("sha256", "")
    output_head = head_or_none(s3, out_key)
    if (state and source_hash_meta and
        state.get("bronze_sha256") == source_hash_meta and
        state.get("pipeline_revision") == revision and output_head and
        output_head.get("Metadata", {}).get("sha256") == state.get("silver_csv_sha256") and
        output_head.get("ContentLength") == state.get("silver_csv_size")):
        removed = cleanup_legacy(s3, source, state["silver_csv_sha256"], dry_run) if cleanup else 0
        return {"source": source, "state": "unchanged", "rows": state.get("active_rows"),
                "legacy_removed": removed}

    with tempfile.TemporaryDirectory(dir=base) as d:
        path = Path(d)
        bronze = path / "bronze.csv"
        s3.download_file(BUCKET, bronze_key, str(bronze))
        bronze_sha = file_sha(bronze)
        after_bronze = s3.head_object(Bucket=BUCKET, Key=bronze_key)
        after_sha = after_bronze.get("Metadata", {}).get("sha256", "")
        if ((source_hash_meta and source_hash_meta != bronze_sha) or
            (after_sha and after_sha != bronze_sha) or
            after_bronze.get("ContentLength") != bronze_head.get("ContentLength")):
            raise RuntimeError("Bronze changed during read or checksum mismatch; refusing publish")

        if (state and state.get("bronze_sha256") == bronze_sha and
            state.get("pipeline_revision") == revision and output_head and
            output_head.get("Metadata", {}).get("sha256") == state.get("silver_csv_sha256") and
            output_head.get("ContentLength") == state.get("silver_csv_size")):
            removed = cleanup_legacy(s3, source, state["silver_csv_sha256"], dry_run) if cleanup else 0
            return {"source": source, "state": "unchanged", "rows": state.get("active_rows"),
                    "legacy_removed": removed}

        manifest = write_outputs(source, bronze, path / "result", bronze_sha)
        manifest["pipeline_revision"] = revision
        manifest["silver_key"] = out_key
        manifest["storage_policy"] = "ONE_CSV_PER_SOURCE_OVERWRITE_ON_CHANGE"
        if dry_run:
            return {"source": source, "state": "dry_run", "rows": manifest["active_rows"],
                    "accepted": manifest["accepted"], "review": manifest["review"],
                    "rejected": manifest["rejected"], "legacy_removed": 0}

        silver = path / "result" / "silver.csv"
        s3.upload_file(str(silver), BUCKET, out_key,
                       ExtraArgs={"ContentType": "text/csv; charset=utf-8",
                                  "Metadata": {"sha256": manifest["silver_csv_sha256"]}})
        uploaded = s3.head_object(Bucket=BUCKET, Key=out_key)
        if (uploaded.get("ContentLength") != manifest["silver_csv_size"] or
            uploaded.get("Metadata", {}).get("sha256") != manifest["silver_csv_sha256"]):
            raise RuntimeError("Silver upload verification failed: " + out_key)
        # Commit tiny manifest only after one CSV was verified.
        s3.put_object(Bucket=BUCKET, Key=ctl_key,
                      Body=json.dumps(manifest, ensure_ascii=False).encode("utf-8"),
                      ContentType="application/json")
        removed = cleanup_legacy(s3, source, manifest["silver_csv_sha256"]) if cleanup else 0
        return {"source": source, "state": "published", "rows": manifest["active_rows"],
                "accepted": manifest["accepted"], "review": manifest["review"],
                "rejected": manifest["rejected"], "key": out_key,
                "bytes": manifest["silver_csv_size"], "legacy_removed": removed}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["all", *BRONZE], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cleanup-legacy", action="store_true",
                        help="Remove outdated Silver copies only after verifying single replacement CSV")
    args = parser.parse_args()
    results, failures = [], []
    s3 = client()
    with tempfile.TemporaryDirectory() as td:
        for source in BRONZE if args.source == "all" else [args.source]:
            try:
                row = process(s3, source, td, args.dry_run, args.cleanup_legacy)
            except Exception as exc:
                row = {"source": source, "state": "failed", "error": str(exc)}
                failures.append(source)
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("## Compact Silver: one CSV per source\n\n| Source | Status | Rows | Old objects deleted |\n|---|---|---:|---:|\n")
            for row in results:
                f.write(f"| {row['source']} | {row['state']} | {row.get('rows','-')} | {row.get('legacy_removed',0)} |\n")
    if failures:
        raise SystemExit("Silver failed for: " + ", ".join(failures))
    if not any(row["state"] in ("published", "dry_run", "unchanged") for row in results):
        print("::warning::No eligible Bronze source; nothing published")

if __name__ == "__main__":
    main()
