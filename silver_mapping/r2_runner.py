"""Publish current Pharmacy mapping tables to fixed Cloudflare R2 CSV keys.

Reads Silver DAV, RxNorm, ICD-10; optionally reads historical MEDI-2 HPS
as unverified code-system candidates. Never creates version directories.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime,timezone
from pathlib import Path

from silver_mapping.build import OUTPUTS, build_all
from silver_mapping.rxnorm_eda import analyze
from silver_auto.r2_runner import BUCKET, client, head_or_none, file_sha, get_json

SOURCES={
    "dav":"silver/dav.csv",
    "rxnorm":"silver/rxnorm.csv",
    "icd10":"silver/icd10.csv",
    "medi":"bronze/MEDI-2_HPS.csv",
}
CHECKPOINT="_control/silver/mappings.json"
EDA_OUTPUTS={"rxnorm_eda.json":"application/json","rxnorm_eda.html":"text/html; charset=utf-8"}
EDA_PREFIX="reports"

def code_revision():
    root=Path(__file__).resolve().parent
    paths=[
        root/"build.py",root/"r2_runner.py",root/"rxnorm_eda.py",
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
            for name in EDA_OUTPUTS:
                h=head_or_none(s3,f"{EDA_PREFIX}/{name}")
                if (not h or
                    h.get("Metadata",{}).get("sha256")!=checkpoint.get("eda_sha256",{}).get(name)
                    or h.get("ContentLength")!=checkpoint.get("eda_sizes",{}).get(name)):
                    verified=False
                    break
        if verified:
            return {"state":"unchanged","tables":checkpoint.get("rows",{}),
                    "rxnorm_eda":checkpoint.get("eda_summary",{})}
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
        # Report 3 + 4 first. Only the quality-gated terminology is passed to mapping.
        mapping_ready=wd/"rxnorm_mapping_ready.csv"
        report_json=wd/"rxnorm_eda.json"
        report_html=wd/"rxnorm_eda.html"
        eda=analyze(paths["rxnorm"],mapping_ready,report_json,report_html,
                    provenance=fingerprints.get("rxnorm",{}))
        result=build_all(paths["dav"],mapping_ready,paths["icd10"],
                         wd/"build",medi=paths.get("medi"))
        eda_paths={"rxnorm_eda.json":report_json,"rxnorm_eda.html":report_html}
        eda_sha={name:file_sha(p) for name,p in eda_paths.items()}
        export_dir=os.getenv("EDA_EXPORT_DIR","").strip()
        if export_dir:
            Path(export_dir).mkdir(parents=True,exist_ok=True)
            for name,p in eda_paths.items():
                shutil.copyfile(p,Path(export_dir)/name)
        state={
            "inputs":fingerprints,"revision":revision,"rows":result["rows"],
            "output_sha256":result["csv_sha256"],
            "eda_sha256":eda_sha,
            "eda_sizes":{name:p.stat().st_size for name,p in eda_paths.items()},
            "eda_summary":{"total_rows":eda["report_3_eda"]["total_rows"],
                           "mapping_ready_rows":eda["report_3_eda"]["mapping_ready_rows"],
                           "excluded_rows":eda["report_3_eda"]["excluded_rows"],
                           "distinct_rxcui":eda["report_3_eda"]["distinct_rxcui_mapping_ready"]},
            "output_sizes":{name:(wd/"build"/(name+".csv")).stat().st_size for name in OUTPUTS},
            "clinical_verified":False,
            "mapping_status":"REVIEW_REQUIRED_NO_OFFICIAL_RELATIONS",
            "built_at_utc":datetime.now(timezone.utc).isoformat(),
        }
        if dry_run:
            return {"state":"dry_run","tables":result["rows"],
                    "rxnorm_eda":state["eda_summary"]}
        # Store report presentation outside Bronze/Silver to avoid proliferating data files.
        for name,p in eda_paths.items():
            key=f"{EDA_PREFIX}/{name}"
            s3.upload_file(str(p),BUCKET,key,ExtraArgs={
                "ContentType":EDA_OUTPUTS[name],
                "Metadata":{"sha256":eda_sha[name]}})
            h=s3.head_object(Bucket=BUCKET,Key=key)
            if (h.get("ContentLength")!=p.stat().st_size or
                h.get("Metadata",{}).get("sha256")!=eda_sha[name]):
                raise RuntimeError("R2 RxNorm EDA report validation failed: "+key)
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
                "rxnorm_eda":state["eda_summary"],
                "objects":["silver/"+name+".csv" for name in OUTPUTS]+
                          [f"{EDA_PREFIX}/{name}" for name in eda_paths]}
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
            if r.get("rxnorm_eda"):
                eda=r["rxnorm_eda"]
                stream.write(f"RxNorm EDA: {eda['total_rows']:,} rows; {eda['mapping_ready_rows']:,} mapping-ready; {eda['excluded_rows']:,} excluded.\\n\\n")
            for name,count in r.get("tables",{}).items():
                stream.write(f"- {name}.csv: {count:,} rows\n")
    if r["state"]=="skipped":
        print("::warning::"+r["reason"])
if __name__=="__main__":main()
