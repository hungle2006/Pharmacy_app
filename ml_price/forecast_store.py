"""Read only verified future-forecast models; never fall back to old price estimator."""
import json
import os
import threading
import time
from pathlib import Path
from tempfile import gettempdir

import boto3
from catboost import CatBoostRegressor
from ml_price.forecast_schema import FEATURES, HORIZONS
from ml_price.upload_forecast import LATEST_KEY

class ForecastStore:
    def __init__(self):
        self.lock=threading.RLock()
        self.checked_at=0
        self.model=None
        self.report=None
        self.version=None

    def refresh(self):
        if time.monotonic()-self.checked_at < 180:
            return
        with self.lock:
            if time.monotonic()-self.checked_at < 180:
                return
            self.checked_at=time.monotonic()
            required=[os.environ.get(k) for k in (
                "ML_R2_ENDPOINT","ML_R2_BUCKET","ML_R2_ACCESS_KEY_ID","ML_R2_SECRET_ACCESS_KEY")]
            if not all(required):
                print("Forecast store missing R2 environment configuration",flush=True)
                return
            endpoint,bucket,key,secret=required
            try:
                client=boto3.client("s3",endpoint_url=endpoint,aws_access_key_id=key,
                                    aws_secret_access_key=secret,region_name="auto")
                latest=json.loads(client.get_object(Bucket=bucket,Key=LATEST_KEY)["Body"].read())
                version=latest["version"]
                prefix=latest["prefix"]
                if not prefix==f"ml/forecast/versions/{version}":
                    raise ValueError("Invalid forecast R2 prefix")
                if version==self.version:
                    return
                metadata=json.loads(client.get_object(Bucket=bucket,Key=prefix+"/report.json")["Body"].read())
                if (metadata.get("version")!=version or metadata.get("status")!="approved"
                    or metadata.get("features")!=FEATURES or not metadata.get("approved_horizons")
                    or set(metadata["approved_horizons"])-set(HORIZONS)):
                    raise ValueError("Forecast metadata has not passed quality gate")
                path=Path(gettempdir())/("pharmabiz_forecast_"+version+".cbm")
                try:
                    path.write_bytes(client.get_object(Bucket=bucket,Key=prefix+"/forecast_model.cbm")["Body"].read())
                    candidate=CatBoostRegressor()
                    candidate.load_model(str(path))
                finally:
                    path.unlink(missing_ok=True)
                self.model=candidate
                self.report=metadata
                self.version=version
            except Exception as error:
                # Keep last approved model; no silent switch back to old estimator.
                print("Forecast model not available:",type(error).__name__,flush=True)

store=ForecastStore()
