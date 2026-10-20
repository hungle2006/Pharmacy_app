"""Automated source crawl with immutable compressed snapshots and change reports."""
import argparse,csv,gzip,hashlib,io,json,os,subprocess,sys,tempfile
from pathlib import Path
from botocore.exceptions import ClientError
import boto3

BUCKET=os.getenv("R2_BUCKET","pharmacy-data-lake")
def client():
    return boto3.client("s3",region_name="auto",endpoint_url="https://"+os.environ["R2_ACCOUNT_ID"]+".r2.cloudflarestorage.com",
      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pointer(s,key):
    try:return json.loads(s.get_object(Bucket=BUCKET,Key=key)["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404","NoSuchKey","NotFound"):return None
        raise
def upload(s,key,p):
    s.upload_file(str(p),BUCKET,key,ExtraArgs={"Metadata":{"sha256":digest(p)}})
    if s.head_object(Bucket=BUCKET,Key=key)["ContentLength"]!=p.stat().st_size:raise RuntimeError("Upload size mismatch")
def save(s,key,item):s.put_object(Bucket=BUCKET,Key=key,Body=json.dumps(item,ensure_ascii=False).encode(),ContentType="application/json")
def zipcsv(src,target,keys):
    with src.open(encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f);cols=r.fieldnames;rows=list(r)
    if not cols or not rows:raise RuntimeError("Empty CSV")
    indexes=[tuple(row[k] for k in keys) for row in rows]
    if len(set(indexes))!=len(rows) or any(not all(i) for i in indexes):raise RuntimeError("Missing/duplicate key")
    rows.sort(key=lambda row:tuple(row[k] for k in keys))
    with gzip.open(target,"wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,lineterminator="\\n");w.writeheader();w.writerows(rows)
    return cols,rows
def run(source):
    root=Path(__file__).resolve().parent
    s=client()
    with tempfile.TemporaryDirectory() as t:
        wd=Path(t);out=wd/"out";out.mkdir()
        if source=="dav":
            subprocess.run([sys.executable,str(root/"crawl_dav.py"),"--output-dir",str(out),"--sorting","id ASC"],check=True)
            raw=list(out.glob("dav_gia_thuoc_raw_*.jsonl"))
            clean=list(out.glob("dav_gia_ban_buon_20*.csv"))
            keys=["dav_row_id"]
        else:
            subprocess.run([sys.executable,str(root/"crawl_icd10.py"),"--output-dir",str(out)],check=True)
            raw=[out/"icd10_tt06_vi_raw_nodes.json",out/"icd10_tt06_en_raw_nodes.json"]
            clean=[out/"ICD10_Vietnam_TT06_2026_FULL.csv"];keys=["model","id"]
        if not raw or not clean or not all(x.exists() for x in raw+clean):raise RuntimeError("Crawler outputs missing")
        snap=wd/"snapshot.csv.gz"
        cols,rows=zipcsv(clean[0],snap,keys)
        curr={"|".join(row[k] for k in keys):row for row in rows}
        old=pointer(s,f"_control/{source}/latest.json")
        before={}
        if old:
            prior=wd/"previous.csv.gz";s.download_file(BUCKET,old["snapshot"],str(prior))
            with gzip.open(prior,"rt",encoding="utf-8",newline="") as f:
                rd=csv.DictReader(f)
                if rd.fieldnames!=cols:raise RuntimeError("Source schema drift")
                before={"|".join(row[k] for k in keys):row for row in rd}
        added=[dict(operation="ADD",**row) for k,row in curr.items() if k not in before]
        updated=[dict(operation="UPDATE",**row) for k,row in curr.items() if k in before and before[k]!=row]
        missing=[dict(operation="MISSING_UNVERIFIED",**row) for k,row in before.items() if k not in curr]
        delta=wd/"delta.csv.gz"
        with gzip.open(delta,"wt",encoding="utf-8",newline="") as f:
            wr=csv.DictWriter(f,fieldnames=["operation"]+cols);wr.writeheader();wr.writerows(added+updated+missing)
        rawpaths=[]
        for i,p in enumerate(raw):
            data=p.read_bytes()
            if not data:raise RuntimeError("Empty raw file")
            new=wd/f"raw{i}.gz"
            with gzip.open(new,"wb",compresslevel=6) as f:f.write(data)
            rawpaths.append(new)
        hashes=[digest(p) for p in rawpaths]
        snap_sha=digest(snap)
        if old and old["snapshot_sha"]==snap_sha and old["raw_hashes"]==hashes:
            print("[UNCHANGED]",source);return
        objects=[]
        for i,p in enumerate(rawpaths):
            key=f"bronze/{source}/sha256={hashes[i]}/raw{i}.gz";upload(s,key,p);objects.append(key)
        csv_key=f"silver/{source}/sha256={snap_sha}/snapshot.csv.gz";upload(s,csv_key,snap)
        delta_key=f"silver/{source}/sha256={digest(delta)}/delta.csv.gz";upload(s,delta_key,delta)
        result={"source":source,"snapshot":csv_key,"snapshot_sha":snap_sha,"raw_hashes":hashes,
           "raw_objects":objects,"delta":delta_key,"rows":len(rows),
           "added":len(added),"updated":len(updated),"missing_unverified":len(missing)}
        save(s,f"_audit/{source}/{snap_sha}.json",result)
        save(s,f"_control/{source}/latest.json",result)
        print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",choices=["dav","icd10"],required=True)
    run(p.parse_args().source)
