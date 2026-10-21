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
from ml_price.segments import canonical
from ml_price.segment_store import catalog_store
from ml_price.baseline import predict_with_priors, blend_predictions

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
    if store.model is None and not catalog_store.available():
        raise HTTPException(status_code=503, detail="NO_APPROVED_MODEL")
    return {"ready": True, "model_version": store.current_version,
            "approved_segments": len(catalog_store.available())}

@app.get("/segments")
def supported_segments():
    """Public list contains only approved segment labels and aggregate metrics."""
    segments = catalog_store.available()
    if not segments:
        store.refresh()
        if store.model is not None:
            segments = [{"price_type": SEGMENT_PRICE_TYPE, "unit": SEGMENT_UNIT,
                         "model_version": store.current_version,
                         "n_distinct_products": store.metadata.get("n_distinct_products"),
                         "mae_vnd": store.metadata.get("metrics", {}).get("mae_vnd"),
                         "mae_gain_fraction": store.metadata.get("mae_gain_fraction")}]
    return {"approved_segments": len(segments), "segments": segments}

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
    if not canonical(payload.price_type) or not canonical(payload.unit):
        raise HTTPException(status_code=422, detail="PRICE_TYPE_AND_UNIT_REQUIRED")
    selected_model, selected_metadata = catalog_store.get(payload.price_type, payload.unit)
    if selected_model is None and canonical(payload.price_type) == canonical(SEGMENT_PRICE_TYPE) and canonical(payload.unit) == canonical(SEGMENT_UNIT):
        # Continue supporting previously published unit=viên models during migration.
        store.refresh()
        selected_model, selected_metadata = store.model, store.metadata
    if selected_model is None or selected_metadata is None:
        raise HTTPException(status_code=422, detail="SEGMENT_NOT_APPROVED: no quality-gated model for this price type and unit")
    row = {name: (getattr(payload, name) or "UNKNOWN").strip() or "UNKNOWN" for name in FEATURES}
    output = float(selected_model.predict(pd.DataFrame([row], columns=FEATURES))[0])
    transform = selected_metadata.get("target_transform", "log1p")
    if transform == "log1p":
        estimated_vnd = math.expm1(min(output, 40))
    elif transform == "identity":
        estimated_vnd = output
    else:
        raise HTTPException(status_code=503, detail="UNSUPPORTED_MODEL_TRANSFORM")
    if not math.isfinite(estimated_vnd):
        raise HTTPException(status_code=503, detail="INVALID_MODEL_OUTPUT")
    coverage = None
    if "blend_weights" in selected_metadata:
        if "baseline_priors" not in selected_metadata:
            raise HTTPException(status_code=503, detail="MISSING_HYBRID_PRIORS")
        frame = pd.DataFrame([row], columns=FEATURES)
        baseline, levels = predict_with_priors(frame, selected_metadata["baseline_priors"])
        estimated_vnd = float(blend_predictions(baseline, [estimated_vnd], levels, selected_metadata["blend_weights"])[0])
        coverage = int(levels[0])
    estimated = max(0, round(estimated_vnd))
    return {
        "predicted_price_vnd": estimated, "currency": "VND",
        "unit": selected_metadata["unit"], "price_type": selected_metadata["price_type"],
        "model_version": selected_metadata["model_version"],
        "reference_level": coverage,
        "data_coverage_warning": "Chưa có lịch sử hoạt chất trong tập train; dự đoán không đủ tin cậy." if coverage == 0 else None,
        "test_mae_vnd": selected_metadata.get("metrics", {}).get("mae_vnd"),
        "note": "Giá dự đoán theo loại giá và đơn vị đã chọn. Không phải giá bán lẻ thực tế hay lời khuyên điều trị."
    }
