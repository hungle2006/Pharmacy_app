"""Read-only cache for the R2 market movement dashboard; no per-drug inference."""
import json
import os
import threading
import time
import boto3

from ml_price.upload_market_forecast import MARKET_KEY

class MarketReportStore:
    def __init__(self):
        self.lock=threading.RLock()
        self.checked_at=0.
        self.report=None
    def refresh(self,force=False):
        if not force and self.report and time.monotonic()-self.checked_at<180:
            return
        with self.lock:
            if not force and self.report and time.monotonic()-self.checked_at<180:
                return
            self.checked_at=time.monotonic()
            env=[os.getenv(key,"") for key in
                  ("ML_R2_ENDPOINT","ML_R2_BUCKET","ML_R2_ACCESS_KEY_ID","ML_R2_SECRET_ACCESS_KEY")]
            if not all(env):
                print("Market report store: R2 configuration missing",flush=True)
                return
            endpoint,bucket,access,secret=env
            try:
                s3=boto3.client("s3",endpoint_url=endpoint,aws_access_key_id=access,
                     aws_secret_access_key=secret,region_name="auto")
                report=json.loads(s3.get_object(Bucket=bucket,Key=MARKET_KEY)["Body"].read())
                if (report.get("schema_version")!=1 or
                    report.get("kind")!="market-declaration-price-trend" or
                    set(report.get("horizons",{}))!={"1","3","6","12"}):
                    raise ValueError("Bad market report schema")
                for item in report["horizons"].values():
                    if item["status"]!="approved" and item.get("forecast_change_pct") is not None:
                        raise ValueError("Unapproved market projection")
                self.report=report
            except Exception as exc:
                print("Market report unavailable:",type(exc).__name__,flush=True)

store=MarketReportStore()
