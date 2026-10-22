"""Safe, refreshable aggregate market report reader (no individual-drug model)."""
import json
import os
import threading
import time

import boto3
from ml_price.upload_market import LATEST_KEY

class MarketReportStore:
    def __init__(self):
        self.lock=threading.RLock()
        self.updated_at=0.0
        self.report=None
        self.version=None
        self.last_error=None

    def refresh(self):
        if time.monotonic()-self.updated_at<180:
            return
        with self.lock:
            if time.monotonic()-self.updated_at<180:
                return
            self.updated_at=time.monotonic()
            required=[os.getenv(k) for k in
                      ("ML_R2_ENDPOINT","ML_R2_BUCKET","ML_R2_ACCESS_KEY_ID","ML_R2_SECRET_ACCESS_KEY")]
            if not all(required):
                self.last_error="R2_NOT_CONFIGURED"
                return
            endpoint,bucket,key,secret=required
            try:
                s3=boto3.client("s3",endpoint_url=endpoint,aws_access_key_id=key,
                                aws_secret_access_key=secret,region_name="auto")
                latest=json.loads(s3.get_object(Bucket=bucket,Key=LATEST_KEY)["Body"].read())
                version=latest["version"]
                if latest["key"]!=f"ml/market/trends/versions/{version}/report.json":
                    raise ValueError("Unsafe market report path")
                if version==self.version:
                    self.last_error=None
                    return
                report=json.loads(s3.get_object(Bucket=bucket,Key=latest["key"])["Body"].read())
                if (report.get("kind")!="dav-market-price-trend"
                    or report.get("schema_version")!=1 or report.get("version")!=version
                    or set(report.get("approved_horizons",[]))-{3,6,12}):
                    raise ValueError("Unsupported market report")
                for h in ("3","6","12"):
                    entry=report.get("horizons",{}).get(h,{})
                    if entry.get("status")!="approved" and entry.get("forecast_change_pct") is not None:
                        raise ValueError("Unapproved forecast value present")
                self.report=report
                self.version=version
                self.last_error=None
            except Exception as e:
                self.last_error=type(e).__name__
                print("Market report read failed:",self.last_error,flush=True)

store=MarketReportStore()
