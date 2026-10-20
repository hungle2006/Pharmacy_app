"""Publish current Pharmacy mapping tables to fixed Cloudflare R2 CSV keys.

Reads Silver DAV, RxNorm, ICD-10; optionally reads historical MEDI-2 HPS
as unverified code-system candidates. Never creates version directories.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime,timezone
from pathlib import Path

from silver_mapping.build import OUTPUTS, build_all
from silver_auto.r2_runner import BUCKET, client, head_or_none, file_sha, get_json

SOURCES={
    "dav":"silver/dav.csv",
    "rxnorm":"silver/rxnorm.csv",
    "icd10":"silver/icd10.csv",
    "medi":"bronze/MEDI-2_HPS.csv",
}
CHECKPOINT="_control/silver/mappings.json"

def code_revision():
    root=Path(__file__).resolve().parent
    paths=[
        root/"build.py",root/"r2_runner.py",
        root.parent/"silver_v3"/"legacy_tools"/"rxnorm_normalize.py",
        root.parent/"silver_v3"/"quality.py",
        root.parent/"silver_v3"/"safe_tools"/"dav_rxnorm_mapper_v3.py",
    ]
    digest=hashlib.sha256()
    for path in paths:digest.update(path.read_bytes())
    return digest.hexdigest()[:16]

def process(s3,dry_run=False):
    heads={name:head_or_none(s3,key) for name,key in SOURCES.items()}
    required=("dav","rxnorm","icd10")
    missing=[name for name in required if not heads[name]]
    if missing:
        return {"state":"skipped","reason":"Missing Silver source(s): "+", ".join(missing)}
    if any(heads[name].get("ContentLength",0)<=0 for name in required):
        raise ValueError("At least one required Silver source is empty")
    revision=code_revision()
    fingerprints={
        name:{"key":SOURCES[name],
              "sha":(heads[name].get("Metadata") or {}).get("sha256",""),
              "etag":heads[name].get("ETag",""),
              "size":heads[name].get("ContentLength",0)}
        for name in SOURCES if heads[name]
    }
    checkpoint=get_json(s3,CHECKPOINT)
    if (checkpoint and checkpoint.get("inputs")==fingerprints
            and checkpoint.get("revision")==revision):
        verified=True
        for name in OUTPUTS:
            h=head_or_none(s3,f"silver/{name}.csv")
            if (not h or
                h.get("Metadata",{}).get("sha256")!=checkpoint.get("output_sha256",{}).get(name)
                or h.get("ContentLength")!=checkpoint.get("output_sizes",{}).get(name)):
                verified=False
                break
        if verified:
            return {"state":"unchanged","tables":checkpoint.get("rows",{})}
    with tempfile.TemporaryDirectory() as t:
        wd=Path(t)
        paths={}
        for name,key in SOURCES.items():
            if not heads[name]:continue
            suffix=".csv"
            path=wd/(name+suffix)
            s3.download_file(BUCKET,key,str(path))
            after=s3.head_object(Bucket=BUCKET,Key=key)
            sha=file_sha(path)
            remote_meta=after.get("Metadata",{}).get("sha256","")
            expected_meta=heads[name].get("Metadata",{}).get("sha256","")
            if (remote_meta and sha!=remote_meta) or (expected_meta and sha!=expected_meta):
                raise RuntimeError("Source changed while reading "+key)
            if (heads[name].get("ETag")!=after.get("ETag")
                    or heads[name].get("ContentLength")!=after.get("ContentLength")):
                raise RuntimeError("Source ETag/size changed during read "+key)
            paths[name]=path
        result=build_all(paths["dav"],paths["rxnorm"],paths["icd10"],
                         wd/"build",medi=paths.get("medi"))
        state={
            "inputs":fingerprints,"revision":revision,"rows":result["rows"],
            "output_sha256":result["csv_sha256"],
            "output_sizes":{name:(wd/"build"/(name+".csv")).stat().st_size for name in OUTPUTS},
            "clinical_verified":False,
            "mapping_status":"REVIEW_REQUIRED_NO_OFFICIAL_RELATIONS",
            "built_at_utc":datetime.now(timezone.utc).isoformat(),
        }
        if dry_run:
            return {"state":"dry_run","tables":result["rows"]}
        # The mapping CSVs are fixed file names. Checkpoint is committed last.
        for name in OUTPUTS:
            local=wd/"build"/(name+".csv")
            key="silver/"+name+".csv"
            s3.upload_file(str(local),BUCKET,key,ExtraArgs={
                "ContentType":"text/csv; charset=utf-8",
                "Metadata":{"sha256":result["csv_sha256"][name]}})
            updated=s3.head_object(Bucket=BUCKET,Key=key)
            if (updated.get("ContentLength")!=local.stat().st_size or
                updated.get("Metadata",{}).get("sha256")!=result["csv_sha256"][name]):
                raise RuntimeError("R2 mapping upload validation failed: "+key)
        s3.put_object(Bucket=BUCKET,Key=CHECKPOINT,
                      Body=json.dumps(state,ensure_ascii=False,indent=2).encode(),
                      ContentType="application/json")
        return {"state":"published","tables":result["rows"],
                "objects":["silver/"+name+".csv" for name in OUTPUTS]}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    a=parser.parse_args()
    r=process(client(),dry_run=a.dry_run)
    print(json.dumps(r,ensure_ascii=False,indent=2))
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf8") as stream:
            stream.write("## Pharmacy Silver mappings\n\n")
            stream.write("Result: **"+r["state"]+"**\n\n")
            for name,count in r.get("tables",{}).items():
                stream.write(f"- {name}.csv: {count:,} rows\n")
    if r["state"]=="skipped":
        print("::warning::"+r["reason"])
if __name__=="__main__":main()
