"""Gold incremental sync: 8 existing PostgreSQL tables + 1 evidence table.

Reads exactly 7 current Silver CSVs, validates mapping checkpoint hashes,
copies into transaction-scoped temp staging, and UPSERTs without deleting
history or replacing curated mapping fields. One small R2 checkpoint.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from gold_auto.sql import ALTERATIONS, UNIQUES, EVIDENCE_DDL, STATEMENTS

BUCKET=os.getenv("R2_BUCKET","pharmacy-data-lake")
CONTROL="_control/gold/latest.json"
MAPPING_CONTROL="_control/silver/mappings.json"
SOURCES={
    "dav":"silver/dav.csv",
    "rxnorm":"silver/rxnorm.csv",
    "icd":"silver/icd10.csv",
    "mapping":"silver/dav_rxnorm_mapping.csv",
    "evidence":"silver/dav_rxnorm_component_evidence.csv",
    "scd":"silver/rxnorm_scd_components.csv",
    "medi":"silver/medi_icd10_mapping.csv",
}
STAGES={x:"gold_stg_"+x for x in SOURCES}
HEADERS={
    "dav":{"dav_row_id","dav_drug_name","dav_active_ingredient_raw","dav_strength","dav_price_vnd",
           "dav_declaration_date","silver_qc_status","dav_price_type","dav_registration_number",
           "dav_dosage_form","dav_package","dav_unit","dav_manufacturer","dav_country"},
    "rxnorm":{"rxcui","display_name","tty","sab"},
    "icd":{"silver_code_canonical","name_vi","name_en","model","silver_qc_status","silver_qc_flags","source"},
    "mapping":{"dav_row_id","candidate_scd_rxcui","candidate_scd_name","mapping_status","review_reason","clinical_verified"},
    "evidence":{"dav_row_id","component_order","component_raw","ingredient_search_name",
                "ingredient_candidate_rxcui","ingredient_candidate_name","ingredient_candidate_tty",
                "candidate_count","match_method","evidence_status","review_reason","clinical_verified"},
    "scd":{"scd_rxcui","scd_name","dose_form_rxcui","dose_form_name","component_order",
           "scdc_rxcui","scdc_name","ingredient_rxcui","ingredient_name","component_strength",
           "component_raw","relation_status","evidence_method","clinical_verified"},
    "medi":{"medi_rxcui","medi_drug_description","medi_vocabulary","medi_code",
            "medi_indication_description","mapping_status","review_reason",
            "rxcui_found_in_rxnorm","clinical_verified"},
}
DEPENDENCIES={"mapping":"dav_rxnorm_mapping","evidence":"dav_rxnorm_component_evidence",
              "scd":"rxnorm_scd_components","medi":"medi_icd10_mapping"}
SQL_SOURCES={"dav_product":"dav","price_record":"dav",
             "disease":"icd","rxnorm_concept":"rxnorm","rxnorm_scd":"scd",
             "rxnorm_scd_component":"scd","dav_rxnorm_mapping":"mapping",
             "dav_rxnorm_evidence":"evidence","medi_relation":"medi"}

def revision():
    h=hashlib.sha256()
    for name in ("sync.py","sql.py"):h.update((Path(__file__).parent/name).read_bytes())
    return h.hexdigest()[:16]

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(2**20),b""):h.update(b)
    return h.hexdigest()

def r2_client():
    import boto3
    required=("R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY")
    absent=[x for x in required if not os.getenv(x)]
    if absent:raise RuntimeError("Missing R2 GitHub secrets: "+", ".join(absent))
    return boto3.client("s3",region_name="auto",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])

def read_control(s3,key):
    from botocore.exceptions import ClientError
    try:return json.loads(s3.get_object(Bucket=BUCKET,Key=key)["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404","NotFound","NoSuchKey"):return None
        raise

def download_consistent(s3,base):
    checkpoint=read_control(s3,MAPPING_CONTROL)
    if not checkpoint:raise RuntimeError("Missing Silver mapping checkpoint")
    paths={};inputs={}
    for label,key in SOURCES.items():
        before=s3.head_object(Bucket=BUCKET,Key=key)
        if before.get("ContentLength",0)==0:raise ValueError("Empty Silver CSV: "+key)
        path=Path(base)/(label+".csv")
        s3.download_file(BUCKET,key,str(path))
        after=s3.head_object(Bucket=BUCKET,Key=key)
        digest=sha256(path)
        if (after["ContentLength"]!=before["ContentLength"] or
            after.get("ETag")!=before.get("ETag") or
            (after.get("Metadata",{}).get("sha256") and after["Metadata"]["sha256"]!=digest)):
            raise RuntimeError("Silver modified while downloading: "+key)
        if label in DEPENDENCIES:
            if digest!=checkpoint.get("output_sha256",{}).get(DEPENDENCIES[label]):
                raise RuntimeError("Mapping CSV and committed Silver manifest differ: "+key)
        else:
            upstream={"dav":"dav","rxnorm":"rxnorm","icd":"icd10"}[label]
            meta=checkpoint.get("inputs",{}).get(upstream,{})
            if meta.get("sha") and digest!=meta["sha"]:
                raise RuntimeError("Silver source is newer than committed mappings: "+key)
            if not meta.get("sha") and before.get("ETag")!=meta.get("etag"):
                raise RuntimeError("Silver mapping source ETag differs: "+key)
        with path.open("r",encoding="utf-8-sig",newline="") as f:
            columns=next(csv.reader(f),[])
        if len(columns)!=len(set(columns)) or not HEADERS[label].issubset(columns):
            raise ValueError("Unexpected source columns in "+key+": "+str(HEADERS[label]-set(columns)))
        inputs[label]={"key":key,"sha256":digest,"bytes":path.stat().st_size}
        paths[label]=path
    return paths,inputs

def stage_csv(cur,tablename,path):
    from psycopg import sql
    with Path(path).open("r",encoding="utf-8-sig",newline="") as f:columns=next(csv.reader(f))
    cur.execute(sql.SQL("CREATE TEMP TABLE {} ({}) ON COMMIT DROP").format(
        sql.Identifier(tablename),sql.SQL(", ").join(
            sql.SQL("{} TEXT").format(sql.Identifier(column)) for column in columns)))
    cmd=sql.SQL("COPY {} ({}) FROM STDIN (FORMAT CSV, HEADER TRUE)").format(
        sql.Identifier(tablename),sql.SQL(", ").join(sql.Identifier(x) for x in columns))
    with cur.copy(cmd) as dest:
        with Path(path).open("rb") as source:
            for block in iter(lambda:source.read(2**20),b""):dest.write(block)
    cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(tablename)))
    count=cur.fetchone()[0]
    if count<1:raise ValueError("Cannot load empty Gold staging "+tablename)
    return count

def schema_setup(cur):
    from psycopg import sql
    cur.execute(EVIDENCE_DDL)
    for table,fields in ALTERATIONS.items():
        for col,typ in fields:
            cur.execute(sql.SQL("ALTER TABLE public.{} ADD COLUMN IF NOT EXISTS {} {}").format(
                sql.Identifier(table),sql.Identifier(col),sql.SQL(typ)))
    for table,cols in UNIQUES:
        ids=sql.SQL(",").join(sql.Identifier(k) for k in cols)
        where=sql.SQL(" AND ").join(sql.SQL("{} IS NOT NULL").format(sql.Identifier(k)) for k in cols)
        cur.execute(sql.SQL("SELECT {},COUNT(*) FROM public.{} WHERE {} GROUP BY {} HAVING COUNT(*)>1 LIMIT 1").format(
            ids,sql.Identifier(table),where,ids))
        duplicate=cur.fetchone()
        if duplicate:raise RuntimeError(f"Duplicate existing Gold key in {table}: {duplicate[:-1]}; aborting without deletion")
        name="gold_unique_"+table+"_"+"_".join(cols)
        cur.execute(sql.SQL("CREATE UNIQUE INDEX IF NOT EXISTS {} ON public.{} ({})").format(
            sql.Identifier(name),sql.Identifier(table),ids))

def stage_checks(cur):
    from psycopg import sql
    for table,cols in (("gold_stg_dav",("dav_row_id",)),
                       ("gold_stg_mapping",("dav_row_id",)),
                       ("gold_stg_evidence",("dav_row_id","component_order"))):
        ids=sql.SQL(",").join(sql.Identifier(c) for c in cols)
        cur.execute(sql.SQL("SELECT 1 FROM {} GROUP BY {} HAVING COUNT(*)>1 LIMIT 1").format(
            sql.Identifier(table),ids))
        if cur.fetchone():raise ValueError("Duplicate Silver identity "+table)
    for table in ("gold_stg_mapping","gold_stg_evidence","gold_stg_scd","gold_stg_medi"):
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {} WHERE clinical_verified IS DISTINCT FROM 'false'").format(
            sql.Identifier(table)))
        if cur.fetchone()[0]:raise ValueError("Source contains unverified clinical approval: "+table)

def write_gold(paths,fingerprints,db_url):
    import psycopg
    results={}
    with psycopg.connect(db_url,connect_timeout=30,application_name="pharmacy_gold_sync") as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext('pharmacy_gold_etl_v1'))")
                cur.execute("SET LOCAL lock_timeout='20s'")
                cur.execute("SET LOCAL statement_timeout='14min'")
                for label,path in paths.items():
                    results["stage_"+label]=stage_csv(cur,STAGES[label],path)
                schema_setup(cur)
                stage_checks(cur)
                for name,query in STATEMENTS:
                    cur.execute(query,{"source_sha":fingerprints[SQL_SOURCES[name]]["sha256"]})
                    results["changed_"+name]=max(cur.rowcount,0)
                # A genuinely identical existing row is not rewritten, so its old
                # silver_source_sha may differ. Reconcile by stable DAV identity.
                cur.execute("""SELECT COUNT(*) FROM gold_stg_dav s
                               JOIN public.dav_product d
                                 ON d.dav_row_id=s.dav_row_id""")
                if cur.fetchone()[0] != results["stage_dav"]:
                    raise ValueError("Gold reconciliation: DAV source keys are missing")
        # Commit if all statements succeeded; connection closes after COMMIT.
    return results

def run(s3,database_url,dry_run=False):
    with tempfile.TemporaryDirectory() as root:
        paths,inputs=download_consistent(s3,root)
        prev=read_control(s3,CONTROL)
        code=revision()
        if prev and prev.get("inputs")==inputs and prev.get("revision")==code:
            return {"status":"unchanged","inputs":len(inputs)}
        if dry_run:return {"status":"dry_run","input_files":len(inputs),"input_bytes":sum(v["bytes"] for v in inputs.values())}
        if not database_url:raise RuntimeError("GOLD_DATABASE_URL GitHub secret is not configured")
        report=write_gold(paths,inputs,database_url)
        record={"inputs":inputs,"revision":code,"updated":datetime.now(timezone.utc).isoformat(),
                "changed":{k:v for k,v in report.items() if k.startswith("changed_")}}
        # Commit R2 checkpoint AFTER PostgreSQL transaction; retries are idempotent.
        s3.put_object(Bucket=BUCKET,Key=CONTROL,
            Body=json.dumps(record,ensure_ascii=False,indent=2).encode(),ContentType="application/json")
        return {"status":"committed","results":report}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    result=run(r2_client(),os.getenv("GOLD_DATABASE_URL",""),args.dry_run)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf8") as f:
            f.write("## Neon Gold incremental sync\n\nStatus: "+result["status"]+"\n\n")
            for name,n in result.get("results",{}).items():f.write(f"- {name}: {n}\n")
if __name__=="__main__":main()
