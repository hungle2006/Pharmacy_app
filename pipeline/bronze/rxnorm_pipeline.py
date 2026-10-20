"""NLM license-free RxNorm ZIP -> RXNCONSO.RRF -> CSV.gz and delta in R2."""
import csv,gzip,hashlib,io,json,os,re,sqlite3,tempfile,zipfile
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests,boto3
from bs4 import BeautifulSoup
from botocore.exceptions import ClientError
PAGE="https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html"
BUCKET=os.environ.get("R2_BUCKET","pharmacy-data-lake")
COLS=["normalized_name","rxcui","display_name","tty","sab"]
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def endpoint():
    import boto3
    return boto3.client("s3",region_name="auto",endpoint_url="https://"+os.environ["R2_ACCOUNT_ID"]+".r2.cloudflarestorage.com",
      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
def get_state(s):
    try:return json.loads(s.get_object(Bucket=BUCKET,Key="_control/rxnorm/latest.json")["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey","404","NotFound"):return None
        raise
def latest():
    r=requests.get(PAGE,timeout=50);r.raise_for_status()
    links=[]
    for a in BeautifulSoup(r.text,"html.parser").select("a[href]"):
        url=urljoin(r.url,a["href"]);name=Path(urlparse(url).path).name
        m=re.fullmatch(r"RxNorm_full_prescribe_(\d{8})\.zip",name,re.I)
        if m and urlparse(url).hostname=="download.nlm.nih.gov":links.append((m.group(1)[4:]+m.group(1)[:4],url,name))
    if not links:raise RuntimeError("No license-free RxNorm Prescribable ZIP found")
    return max(links)[1:]
def download(url,p):
    with requests.get(url,stream=True,timeout=(20,120)) as r:
        r.raise_for_status()
        if urlparse(r.url).hostname!="download.nlm.nih.gov":raise RuntimeError("Unexpected download redirect")
        total=0
        with p.open("wb") as f:
            for block in r.iter_content(1024*1024):
                if not block:continue
                total+=len(block)
                if total>650*1024*1024:raise RuntimeError("Archive too large")
                f.write(block)
    if not zipfile.is_zipfile(p):raise RuntimeError("Not a ZIP archive")
def normalize(s):
    import unicodedata
    s=unicodedata.normalize("NFKD",s).casefold()
    s="".join(x for x in s if not unicodedata.combining(x))
    return " ".join("".join(x if x.isalnum() else " " for x in s).split())
def convert(z,db):
    con=sqlite3.connect(db)
    con.execute("CREATE TABLE r (normalized_name TEXT,rxcui TEXT,display_name TEXT,tty TEXT,sab TEXT,PRIMARY KEY(normalized_name,rxcui,display_name,tty,sab)) WITHOUT ROWID")
    with zipfile.ZipFile(z) as archive:
        matches=[x for x in archive.infolist() if Path(x.filename).name.upper()=="RXNCONSO.RRF"]
        if len(matches)!=1:raise RuntimeError("Missing or duplicate RXNCONSO.RRF")
        if matches[0].file_size>4*1024**3:raise RuntimeError("Oversized RRF")
        with archive.open(matches[0]) as f:
            for i,line in enumerate(io.TextIOWrapper(f,encoding="utf-8-sig"),1):
                a=line.rstrip("\r\n").split("|")
                if a[-1]=="":a.pop()
                if len(a)!=18:raise RuntimeError("Unexpected RRF columns at "+str(i))
                if a[1]=="ENG" and a[11]=="RXNORM" and a[16]=="N" and a[14] and a[0]:
                    con.execute("INSERT OR IGNORE INTO r VALUES(?,?,?,?,?)",(normalize(a[14]),a[0],a[14],a[12],"RXNORM"))
                if i%20000==0:con.commit()
    con.commit()
    if not con.execute("SELECT COUNT(*) FROM r").fetchone()[0]:raise RuntimeError("No RxNorm entries")
    return con
def gz_csv(path,fields,rows):
    with gzip.open(path,"wt",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(fields);w.writerows(rows)
def upload(s,p,key):
    s.upload_file(str(p),BUCKET,key,ExtraArgs={"Metadata":{"sha256":sha(p)}})
    if s.head_object(Bucket=BUCKET,Key=key)["ContentLength"]!=p.stat().st_size:raise RuntimeError("R2 size mismatch")
def main():
    url,name=latest();s=endpoint();state=get_state(s)
    if state and state.get("release")==name:
        print("[SKIP] Already ingested release",name);return
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);z=d/name;download(url,z)
        zip_sha=sha(z)
        if state and state.get("zip_sha")==zip_sha:
            print("[SKIP] Same ZIP",name);return
        conn=convert(z,d/"db.sqlite")
        snapshot=d/"rxnorm.csv.gz"
        gz_csv(snapshot,COLS,conn.execute("SELECT * FROM r ORDER BY rxcui,tty,display_name"))
        conn.execute("CREATE TABLE prev AS SELECT * FROM r WHERE 0")
        if state:
            old=d/"prev.csv.gz";s.download_file(BUCKET,state["snapshot"],str(old))
            with gzip.open(old,"rt",encoding="utf-8") as f:
                reader=csv.DictReader(f)
                if reader.fieldnames!=COLS:raise RuntimeError("Previous CSV format changed")
                conn.executemany("INSERT INTO prev VALUES(?,?,?,?,?)",([row[h] for h in COLS] for row in reader))
        query=" AND ".join("p."+k+"=c."+k for k in COLS)
        added=conn.execute("SELECT c.* FROM r c WHERE NOT EXISTS(SELECT 1 FROM prev p WHERE "+query+")").fetchall()
        removed=conn.execute("SELECT p.* FROM prev p WHERE NOT EXISTS(SELECT 1 FROM r c WHERE "+query+")").fetchall()
        delta=d/"rxnorm_delta.csv.gz"
        gz_csv(delta,["operation"]+COLS,[("ADD",*r) for r in added]+[("REMOVE",*r) for r in removed])
        zk=f"bronze/rxnorm/sha256={zip_sha}/{name}"
        sk=f"silver/rxnorm/sha256={sha(snapshot)}/rxnorm.csv.gz"
        dk=f"silver/rxnorm/sha256={sha(delta)}/delta.csv.gz"
        for key,path in ((zk,z),(sk,snapshot),(dk,delta)):upload(s,path,key)
        report={"release":name,"source_url":url,"zip_sha":zip_sha,"raw_zip":zk,"snapshot":sk,"delta":dk,
                "rows":conn.execute("SELECT COUNT(*) FROM r").fetchone()[0],"added":len(added),"removed":len(removed)}
        body=json.dumps(report,ensure_ascii=False).encode()
        s.put_object(Bucket=BUCKET,Key="_audit/rxnorm/"+zip_sha+".json",Body=body,ContentType="application/json")
        s.put_object(Bucket=BUCKET,Key="_control/rxnorm/latest.json",Body=body,ContentType="application/json")
        print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
