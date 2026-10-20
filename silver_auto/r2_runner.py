"""Automatic, per-source, atomic Silver publication from R2 Bronze CSV.

Reuses existing GitHub Bronze secrets; R2 writes only silver/v4/ namespace.
MEDI-2 needs an explicitly approved newer release marker before ingest.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from silver_auto.etl import BRONZE, write_outputs

BUCKET = os.getenv("R2_BUCKET","pharmacy-data-lake")
PREFIX = "silver/v4"
def missing(exc):
    from botocore.exceptions import ClientError
    return isinstance(exc,ClientError) and exc.response.get("Error",{}).get("Code") in ("404","NotFound","NoSuchKey")
def get_json(s3,key):
    try:
        return json.loads(s3.get_object(Bucket=BUCKET,Key=key)["Body"].read())
    except Exception as exc:
        if missing(exc):return None
        raise
def client():
    import boto3
    names=("R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY")
    absent=[k for k in names if not os.getenv(k)]
    if absent:raise RuntimeError("Missing existing Bronze R2 secrets: "+", ".join(absent))
    return boto3.client("s3",region_name="auto",
      endpoint_url="https://"+os.environ["R2_ACCOUNT_ID"]+".r2.cloudflarestorage.com",
      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
def process(s3,source,base,dry_run):
    key=BRONZE[source]
    if source=="medi_hps":
        release=os.getenv("MEDI_HPS_APPROVED_RELEASE","").strip()
        if not release or release=="2020" or release.startswith("2020"):
            return {"source":source,"state":"skipped","reason":"MEDI newer release not approved"}
        provenance=get_json(s3,"_control/compact/medi_hps.json")
        if not provenance or provenance.get("release") != release:
            return {"source":source,"state":"skipped","reason":"MEDI Bronze release provenance not verified"}
    try:head=s3.head_object(Bucket=BUCKET,Key=key)
    except Exception as exc:
        if missing(exc):
            return {"source":source,"state":"skipped","reason":"Bronze canonical CSV missing","key":key}
        raise
    if head.get("ContentLength",0)<=0:raise ValueError("Empty Bronze R2 object "+key)
    pointer_key=f"{PREFIX}/{source}/latest.json"
    latest=get_json(s3,pointer_key)
    expected_sha=head.get("Metadata",{}).get("sha256","")
    if latest and expected_sha and latest.get("bronze_sha256")==expected_sha:
        return {"source":source,"state":"unchanged","version":expected_sha[:24]}
    with tempfile.TemporaryDirectory(dir=base) as d:
        root=Path(d);bronze=root/"bronze.csv";s3.download_file(BUCKET,key,str(bronze))
        source_sha=hashlib.sha256(bronze.read_bytes()).hexdigest()
        after_source=s3.head_object(Bucket=BUCKET,Key=key)
        after_sha=after_source.get("Metadata",{}).get("sha256","")
        if expected_sha and expected_sha!=source_sha:
            raise RuntimeError("Bronze object changed or integrity metadata invalid while reading: "+key)
        if after_sha and after_sha!=source_sha:
            raise RuntimeError("Bronze object updated during Silver processing; retry next run: "+key)
        version=source_sha[:24]
        prefix=f"{PREFIX}/{source}/version={version}/"
        if latest and latest.get("bronze_sha256")==source_sha:
            return {"source":source,"state":"unchanged","version":version}
        # A prior run may have uploaded the full version but failed before moving latest.
        previous=get_json(s3,prefix+"manifest.json")
        if previous and previous.get("bronze_sha256")==source_sha:
            ready=True
            for name in previous.get("output_sha256",{}):
                try:s3.head_object(Bucket=BUCKET,Key=prefix+name)
                except Exception as exc:
                    if missing(exc):ready=False;break
                    raise
            if ready and len(previous.get("output_sha256",{}))==4:
                if not dry_run:
                    latest={"source":source,"version":version,"bronze_sha256":source_sha,
                            "prefix":prefix,"manifest":prefix+"manifest.json"}
                    s3.put_object(Bucket=BUCKET,Key=pointer_key,
                                  Body=json.dumps(latest).encode(),ContentType="application/json")
                return {"source":source,"state":"dry_run" if dry_run else "recovered","version":version}
        out=root/"silver"
        manifest=write_outputs(source,bronze,out,source_sha)
        if dry_run:
            return {"source":source,"state":"dry_run","version":version,
                    "rows":manifest["active_rows"],"review":manifest["review"]}
        # Upload all data first, commit manifest last.
        for name,digest in manifest["output_sha256"].items():
            path=out/name
            s3.upload_file(str(path),BUCKET,prefix+name,
                ExtraArgs={"ContentType":"text/csv; charset=utf-8","Metadata":{"sha256":digest}})
            uploaded=s3.head_object(Bucket=BUCKET,Key=prefix+name)
            if uploaded["ContentLength"]!=path.stat().st_size or uploaded.get("Metadata",{}).get("sha256")!=digest:
                raise RuntimeError("R2 upload verification failed: "+name)
        s3.upload_file(str(out/"manifest.json"),BUCKET,prefix+"manifest.json",
            ExtraArgs={"ContentType":"application/json"})
        after=s3.head_object(Bucket=BUCKET,Key=prefix+"manifest.json")
        if after["ContentLength"]!=(out/"manifest.json").stat().st_size:
            raise RuntimeError("Manifest upload verification failed")
        # Update only the pointer for this source, after data/manifest verified.
        latest={"source":source,"version":version,"bronze_sha256":source_sha,
                "prefix":prefix,"manifest":prefix+"manifest.json"}
        s3.put_object(Bucket=BUCKET,Key=pointer_key,
                      Body=json.dumps(latest).encode(),ContentType="application/json")
        return {"source":source,"state":"published","version":version,
                "rows":manifest["active_rows"],"review":manifest["review"],"prefix":prefix}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--source",choices=["all",*BRONZE.keys()],default="all")
    args=p.parse_args()
    s3=client()
    results=[];failures=[]
    sources=BRONZE.keys() if args.source=="all" else [args.source]
    with tempfile.TemporaryDirectory() as td:
        for source in sources:
            try:r=process(s3,source,td,args.dry_run)
            except Exception as exc:
                r={"source":source,"state":"failed","error":str(exc)}
                failures.append(source)
            results.append(r)
            print(json.dumps(r,ensure_ascii=False),flush=True)
    summary=os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf8") as f:
            f.write("## Pharmacy Silver v4 (R2)\n\n| Source | Status | Rows | Note |\n|---|---|---:|---|\n")
            for r in results:
                note=r.get("reason") or r.get("error") or r.get("version","")
                f.write(f"| {r['source']} | {r['state']} | {r.get('rows','-')} | {note} |\n")
    if failures:raise SystemExit("Silver failed for: "+", ".join(failures))
    if not any(r["state"] in ("published","dry_run","unchanged") for r in results):
        print("::warning::No available Bronze source; nothing processed")
if __name__=="__main__":main()
