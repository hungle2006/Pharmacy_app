"""One cumulative CSV per source on Cloudflare R2.

A R2 object cannot be appended in-place; each successful change builds a complete
local replacement and uploads it to the SAME key. No snapshot objects are created.
Latest state is reconstructed from the append-only event stream.
"""
from __future__ import annotations
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

BUCKET = os.getenv("R2_BUCKET", "pharmacy-data-lake")
META = ["__operation", "__ingested_utc", "__row_hash"]
KEYS = {
    "dav": ["dav_row_id"],
    "icd10": ["model", "id"],
    "rxnorm": ["rxcui", "tty", "sab", "display_name"],
}
CANONICAL = {s: f"bronze/{s}.csv" for s in ("dav", "icd10", "rxnorm")}
CANONICAL["medi_hps"] = "bronze/medi_hps.csv"

def r2():
    return boto3.client(
        "s3", region_name="auto",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )

def missing(exc):
    return isinstance(exc, ClientError) and exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound")

def exists(s3, key):
    try:
        return s3.head_object(Bucket=BUCKET, Key=key)
    except ClientError as ex:
        if missing(ex):
            return None
        raise

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(2**20), b""):
            h.update(chunk)
    return h.hexdigest()

def fields_of(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        fields = csv.DictReader(f).fieldnames
    if not fields or len(fields) != len(set(fields)):
        raise ValueError(f"Invalid/duplicate CSV header: {path}")
    if any(field in META for field in fields):
        raise ValueError("Source CSV must not use reserved metadata columns")
    return list(fields)

def key_for(row, columns):
    out = tuple(str(row[col]).strip() for col in columns)
    if not all(out):
        raise ValueError(f"Empty record key for columns {columns}: {out}")
    return out

def digest(row, fields):
    data = json.dumps([row[field] for field in fields], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def merge_snapshot(s3, source, incoming, keys=None, allow_removes=False, minimum=1):
    """CSV is a complete source snapshot (not a delta). Never commit partial crawls."""
    if source not in CANONICAL:
        raise ValueError(f"Unknown source {source}")
    incoming = Path(incoming)
    fields = fields_of(incoming)
    keys = list(keys if keys is not None else KEYS[source])
    if not set(keys).issubset(fields):
        raise ValueError(f"Missing natural key columns: {keys} from {fields}")
    remote = CANONICAL[source]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        prior = temp / "prior.csv"
        existing = {}
        previous_count = 0
        head = exists(s3, remote)
        if head:
            s3.download_file(BUCKET, remote, str(prior))
            with prior.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames != fields + META:
                    raise ValueError(f"Bronze column schema changed for {source}: {reader.fieldnames} != {fields + META}")
                for row in reader:
                    previous_count += 1
                    existing[key_for(row, keys)] = (row["__row_hash"], row["__operation"], row)
        fresh = {}
        with incoming.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ident = key_for(row, keys)
                if ident in fresh:
                    # Duplicate natural keys are unsafe for version comparison.
                    if fresh[ident][0] != digest(row, fields):
                        raise ValueError(f"Conflicting source record IDs for {source}: {ident}")
                    continue
                fresh[ident] = (digest(row, fields), row)
        if len(fresh) < minimum:
            raise ValueError(f"Source {source} has only {len(fresh)} valid rows; expected >= {minimum}")
        changes = []
        for ident, (newhash, row) in fresh.items():
            old = existing.get(ident)
            if old is None:
                op = "INSERT"
            elif old[0] != newhash or old[1] == "REMOVE":
                op = "UPDATE"
            else:
                continue
            changes.append({**row, "__operation": op, "__ingested_utc": stamp, "__row_hash": newhash})
        if allow_removes:
            for ident, (oldhash, oldop, oldrow) in existing.items():
                if ident not in fresh and oldop != "REMOVE":
                    changes.append({**{k: oldrow[k] for k in fields}, "__operation": "REMOVE",
                                    "__ingested_utc": stamp, "__row_hash": oldhash})
        if not changes:
            print(json.dumps({"source": source, "result": "UNCHANGED", "rows_seen": len(fresh), "bronze": remote}))
            return {"source": source, "status": "unchanged", "new_events": 0, "total_events": previous_count}
        staged = temp / "replacement.csv"
        # Existing history is copied as-is, then new events appended in deterministic ID order.
        with staged.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fields + META, lineterminator="\n")
            writer.writeheader()
            if head:
                with prior.open(encoding="utf-8-sig", newline="") as inputf:
                    for row in csv.DictReader(inputf):
                        writer.writerow(row)
            for change in sorted(changes, key=lambda r: key_for(r, keys)):
                writer.writerow(change)
        total_events = previous_count + len(changes)
        digest_of_file = sha256_file(staged)
        s3.upload_file(str(staged), BUCKET, remote,
                       ExtraArgs={"ContentType": "text/csv; charset=utf-8", "Metadata": {"sha256": digest_of_file}})
        after = s3.head_object(Bucket=BUCKET, Key=remote)
        if after["ContentLength"] != staged.stat().st_size or after.get("Metadata", {}).get("sha256") != digest_of_file:
            raise RuntimeError(f"R2 upload verification failed: {remote}")
        result = {"source": source, "status": "updated", "new_events": len(changes),
                  "total_events": total_events, "active_snapshot_rows": len(fresh),
                  "bronze": remote, "sha256": digest_of_file}
        s3.put_object(Bucket=BUCKET, Key=f"_control/compact/{source}.json",
                      Body=json.dumps(result, ensure_ascii=False).encode(), ContentType="application/json")
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return result

def all_objects(s3, prefix):
    token = None
    while True:
        request = {"Bucket": BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            request["ContinuationToken"] = token
        page = s3.list_objects_v2(**request)
        for record in page.get("Contents", []):
            yield record["Key"]
        if not page.get("IsTruncated"):
            break
        token = page["NextContinuationToken"]

def cleanup_legacy_bronze(s3, dry_run=True):
    """Never delete canonical CSVs, and never delete raw sources without a verified replacement."""
    protected = set(CANONICAL.values())
    candidates = [k for k in all_objects(s3, "bronze/") if k not in protected]
    pending = {}
    for k in candidates:
        group = k.split("/")[1] if "/" in k else ""
        if group not in CANONICAL:
            raise RuntimeError(f"Unknown legacy bronze prefix: {k}; refusing deletion")
        if not exists(s3, CANONICAL[group]):
            raise RuntimeError(f"Cannot delete {k} because {CANONICAL[group]} does not exist")
        pending.setdefault(group, []).append(k)
    if dry_run:
        print(json.dumps({"dry_run": True, "eligible_deletions": pending}, ensure_ascii=False))
        return pending
    for keys in pending.values():
        for key in keys:
            s3.delete_object(Bucket=BUCKET, Key=key)
            if exists(s3, key):
                raise RuntimeError(f"Delete not confirmed for {key}")
    print(json.dumps({"deleted": pending}, ensure_ascii=False))
    return pending
