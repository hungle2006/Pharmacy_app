"""Publish aggregate market trend and backtest report, even if no forecast qualifies.

All unapproved future rates remain null. Historical paired changes are useful
on the dashboard and do not imply a future forecast. Older R2 keys untouched.
"""
import json
import os
from pathlib import Path
import boto3

MARKET_KEY="ml/market-forecast/latest.json"

def publish_market_report(root="models/market"):
    report=json.loads((Path(root)/"report.json").read_text(encoding="utf-8"))
    if report.get("schema_version")!=1 or report.get("kind")!="market-declaration-price-trend":
        raise ValueError("Invalid market forecast report")
    for key,entry in report["horizons"].items():
        if entry["status"]!="approved" and entry.get("forecast_change_pct") is not None:
            raise ValueError("Disallowed forecast in rejected horizon: "+key)
    bucket=os.environ["ML_R2_BUCKET"]
    client=boto3.client("s3",endpoint_url=os.environ["ML_R2_ENDPOINT"].rstrip("/"),
         aws_access_key_id=os.environ["ML_R2_ACCESS_KEY_ID"],
         aws_secret_access_key=os.environ["ML_R2_SECRET_ACCESS_KEY"],region_name="auto")
    data=json.dumps(report,ensure_ascii=False).encode("utf-8")
    version=report["model_version"]
    client.put_object(Bucket=bucket,Key=f"ml/market-forecast/versions/{version}.json",
                      Body=data,ContentType="application/json")
    # Update public summary pointer last; rejects remain clearly labeled.
    client.put_object(Bucket=bucket,Key=MARKET_KEY,Body=data,
                      ContentType="application/json",CacheControl="no-cache")
    print("MARKET_REPORT_PUBLISHED",version,"approved:",report["approved_horizons"])
    return True

if __name__=="__main__":
    publish_market_report()
