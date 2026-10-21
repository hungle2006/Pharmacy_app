"""Render Free FastAPI inference; load only approved models from private Cloudflare R2."""
import hmac
import json
import math
import os
import threading
import time
from pathlib import Path
from tempfile import gettempdir

import boto3
import pandas as pd
from catboost import CatBoostRegressor
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from ml_price.constants import FEATURES, SEGMENT_PRICE_TYPE, SEGMENT_UNIT

class PriceFeatures(BaseModel):
    ingredient: str = Field(min_length=1, max_length=300)
    strength: str = Field(default="UNKNOWN", max_length=180)
    dosage_form: str = Field(default="UNKNOWN", max_length=180)
    manufacturer: str = Field(default="UNKNOWN", max_length=250)
    country: str = Field(default="UNKNOWN", max_length=150)
    package: str = Field(default="UNKNOWN", max_length=200)
    price_type: str = SEGMENT_PRICE_TYPE
    unit: str = SEGMENT_UNIT

class ModelStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.model = None
        self.metadata = None
        self.current_version = None
        self.checked_at = 0.0

    def refresh(self):
        if time.monotonic() - self.checked_at < 300:
            return
        with self.lock:
            if time.monotonic() - self.checked_at < 300:
                return
            self.checked_at = time.monotonic()
            values = [os.getenv(name, "") for name in
                      ("ML_R2_ENDPOINT", "ML_R2_BUCKET", "ML_R2_ACCESS_KEY_ID", "ML_R2_SECRET_ACCESS_KEY")]
            if not all(values):
                return
            endpoint, bucket, access, secret = values
            try:
                s3 = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access,
                                 aws_secret_access_key=secret, region_name="auto")
                latest = json.loads(s3.get_object(Bucket=bucket, Key="ml/price/latest.json")["Body"].read())
                version, prefix = latest["model_version"], latest["prefix"]
                if version == self.current_version:
                    return
                info = json.loads(s3.get_object(Bucket=bucket, Key=prefix + "/metadata.json")["Body"].read())
                if info.get("status") != "approved" or info.get("model_version") != version:
                    raise ValueError("R2 version unapproved or inconsistent")
                if info.get("features") != FEATURES or info.get("unit") != SEGMENT_UNIT or info.get("price_type") != SEGMENT_PRICE_TYPE:
                    raise ValueError("Unsupported model features or segment")
                model_path = Path(gettempdir()) / ("pharma_price_" + version + ".cbm")
                model_path.write_bytes(s3.get_object(Bucket=bucket, Key=prefix + "/price_model.cbm")["Body"].read())
                candidate = CatBoostRegressor()
                candidate.load_model(str(model_path))
                model_path.unlink(missing_ok=True)
                self.model, self.metadata, self.current_version = candidate, info, version
            except Exception as error:
                # Keep last known-good version if remote update is unavailable.
                print("Model refresh unavailable:", type(error).__name__)

store = ModelStore()
app = FastAPI(title="PharmaBiz Price ML", docs_url=None, redoc_url=None)

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": store.model is not None}

@app.get("/ready")
def ready():
    store.refresh()
    if store.model is None:
        raise HTTPException(status_code=503, detail="NO_APPROVED_MODEL")
    return {"ready": True, "model_version": store.current_version}

def authorized(key):
    configured = os.getenv("ML_API_KEY", "")
    if not configured:
        raise HTTPException(status_code=503, detail="ML_API_KEY_NOT_CONFIGURED")
    if not key or not hmac.compare_digest(key, configured):
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")

@app.get("/model-info")
def model_info(x_api_key: str | None = Header(default=None)):
    authorized(x_api_key)
    store.refresh()
    if store.metadata is None:
        raise HTTPException(status_code=503, detail="NO_APPROVED_MODEL")
    keys = ("model_version", "trained_at", "status", "price_type", "unit",
            "currency", "features", "n_train", "n_test", "metrics", "baseline_metrics", "limitations")
    return {key: store.metadata.get(key) for key in keys}

@app.post("/predict-price")
def predict_price(payload: PriceFeatures, x_api_key: str | None = Header(default=None)):
    authorized(x_api_key)
    if payload.price_type != SEGMENT_PRICE_TYPE or payload.unit.strip().casefold() != SEGMENT_UNIT:
        raise HTTPException(status_code=422, detail="SEGMENT_MISMATCH: only wholesale VAT / viên")
    store.refresh()
    if store.model is None or store.metadata is None:
        raise HTTPException(status_code=503, detail="NO_APPROVED_MODEL")
    row = {name: (getattr(payload, name) or "UNKNOWN").strip() or "UNKNOWN" for name in FEATURES}
    output = float(store.model.predict(pd.DataFrame([row], columns=FEATURES))[0])
    transform = store.metadata.get("target_transform", "log1p")
    if transform == "log1p":
        estimated_vnd = math.expm1(min(output, 40))
    elif transform == "identity":
        estimated_vnd = output
    else:
        raise HTTPException(status_code=503, detail="UNSUPPORTED_MODEL_TRANSFORM")
    if not math.isfinite(estimated_vnd):
        raise HTTPException(status_code=503, detail="INVALID_MODEL_OUTPUT")
    estimated = max(0, round(estimated_vnd))
    return {
        "predicted_price_vnd": estimated, "currency": "VND",
        "unit": SEGMENT_UNIT, "price_type": SEGMENT_PRICE_TYPE,
        "model_version": store.current_version,
        "test_mae_vnd": store.metadata.get("metrics", {}).get("mae_vnd"),
        "note": "Dự đoán giá kê khai bán buôn dự kiến có VAT theo viên, không phải báo giá bán lẻ hay lời khuyên điều trị."
    }
