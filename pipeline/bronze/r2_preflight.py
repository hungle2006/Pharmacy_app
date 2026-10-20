"""Check GitHub-to-R2 write/read without changing existing Bronze objects."""
import os,uuid,json,hashlib
from datetime import datetime,timezone
import boto3
s=boto3.client("s3",endpoint_url="https://"+os.environ["R2_ACCOUNT_ID"]+".r2.cloudflarestorage.com",region_name="auto",aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
bucket=os.getenv("R2_BUCKET","pharmacy-data-lake")
key=f"_healthcheck/github_actions/{uuid.uuid4().hex}.json"
payload=json.dumps({"utc":datetime.now(timezone.utc).isoformat(),"purpose":"read-write-check"}).encode()
try:
    s.put_object(Bucket=bucket,Key=key,Body=payload,ContentType="application/json")
    got=s.get_object(Bucket=bucket,Key=key)["Body"].read()
    if hashlib.sha256(got).digest()!=hashlib.sha256(payload).digest():raise RuntimeError("R2 payload checksum mismatch")
    print("R2_PREFLIGHT_SUCCESS",bucket,len(got),flush=True)
finally:
    s.delete_object(Bucket=bucket,Key=key)
