"""Publish aggregate DAV market-trend report, including honest 'historical only' status.

This file contains NO per-product forecasts. The R2 report is separate from
the legacy individual-price forecast keys, which remain unused.
"""
import json
import os
from pathlib import Path

import boto3

LATEST_KEY="ml/market/trends/latest.json"

def publish_market(root="models/market"):
    directory=Path(root)
    report=json.loads((directory/"report.json").read_text(encoding="utf-8"))
    if report.get("kind")!="dav-market-price-trend" or report.get("schema_version")!=1:
        raise ValueError("Unexpected market report")
    if set(report.get("approved_horizons",[]))- {3,6,12}:
        raise ValueError("Unsupported horizon in market report")
    client=boto3.client("s3",
                        endpoint_url=os.environ["ML_R2_ENDPOINT"].rstrip("/"),
                        aws_access_key_id=os.environ["ML_R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["ML_R2_SECRET_ACCESS_KEY"],
                        region_name="auto")
    bucket=os.environ["ML_R2_BUCKET"]
    version=report["version"]
    target=f"ml/market/trends/versions/{version}/report.json"
    # Versioned upload first, atomic manifest switch only after upload succeeds.
    client.upload_file(str(directory/"report.json"),bucket,target,
                       ExtraArgs={"ContentType":"application/json","CacheControl":"no-cache"})
    client.put_object(Bucket=bucket,Key=LATEST_KEY,
                      Body=json.dumps({"version":version,"key":target}).encode("utf-8"),
                      ContentType="application/json",CacheControl="no-store")
    print("MARKET_REPORT_PUBLISHED",version,"approved:",report["approved_horizons"],
          "historical_only:",report["historical_only"])
    return True

if __name__=="__main__":
    publish_market()
