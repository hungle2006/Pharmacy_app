"""Publish independent, quality-gated future-price forecasting artifacts.

The old price-estimation R2 keys are deliberately left intact for rollback,
but are no longer referenced by the web/API or ongoing training workflow.
"""
import json
import os
from pathlib import Path
import boto3

LATEST_KEY="ml/forecast/latest.json"

def publish(root="models/forecast"):
    root=Path(root)
    report=json.loads((root/"report.json").read_text(encoding="utf-8"))
    if report.get("status")!="approved" or not report.get("approved_horizons"):
        print("NO_APPROVED_FORECAST: nothing published; website must not invent future prices")
        return False
    client=boto3.client("s3",endpoint_url=os.environ["ML_R2_ENDPOINT"].rstrip("/"),
                        aws_access_key_id=os.environ["ML_R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["ML_R2_SECRET_ACCESS_KEY"],region_name="auto")
    bucket=os.environ["ML_R2_BUCKET"]
    version=report["version"]
    prefix=f"ml/forecast/versions/{version}"
    client.upload_file(str(root/"forecast_model.cbm"),bucket,prefix+"/forecast_model.cbm")
    client.upload_file(str(root/"report.json"),bucket,prefix+"/report.json")
    client.put_object(Bucket=bucket,Key=LATEST_KEY,
                      Body=json.dumps({"version":version,"prefix":prefix,
                                       "approved_horizons":report["approved_horizons"]}).encode("utf-8"),
                      ContentType="application/json",CacheControl="no-cache")
    print("FORECAST_PUBLISHED",version,report["approved_horizons"])
    return True

if __name__=="__main__":
    publish()
