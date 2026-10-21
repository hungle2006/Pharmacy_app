"""API for honest, quality-gated forecasts of future declared medicine prices.

The old /predict-price route is intentionally removed. No fallback to
historical price estimation, no fabricated future quote, and no API credentials
sent to the browser.
"""
import hmac
import math
import os
from calendar import monthrange
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from ml_price.forecast_schema import HORIZONS, CATEGORICAL, FEATURES
from ml_price.forecast_store import store
from ml_price.segments import canonical

app=FastAPI(title="PharmaBiz Future Drug Price Forecast",docs_url=None,redoc_url=None)

class ForecastRequest(BaseModel):
    ingredient:str=Field(min_length=1,max_length=300)
    strength:str=Field(default="UNKNOWN",max_length=180)
    dosage_form:str=Field(default="UNKNOWN",max_length=180)
    manufacturer:str=Field(default="UNKNOWN",max_length=250)
    country:str=Field(default="UNKNOWN",max_length=150)
    package:str=Field(default="UNKNOWN",max_length=300)
    price_type:str=Field(min_length=1,max_length=180)
    unit:str=Field(min_length=1,max_length=100)
    latest_price_vnd:float=Field(gt=0,le=1e10)
    latest_price_date:date
    horizon_months:int=Field(default=3)

def advance_months(day,months):
    year=(day.year+(day.month-1+months)//12)
    month=(day.month-1+months)%12+1
    return date(year,month,min(day.day,monthrange(year,month)[1]))

def verify_api_key(x_api_key:Optional[str]):
    key=os.getenv("ML_API_KEY","")
    if not key:
        raise HTTPException(status_code=503,detail="ML_API_KEY_NOT_CONFIGURED")
    if not x_api_key or not hmac.compare_digest(x_api_key,key):
        raise HTTPException(status_code=401,detail="UNAUTHORIZED")

@app.get("/health")
def health():
    return {"status":"ok","kind":"future-price-forecast","model_loaded":store.model is not None}

@app.get("/ready")
def ready():
    store.refresh()
    if store.model is None:
        raise HTTPException(status_code=503,detail="NO_APPROVED_FORECAST")
    return {"ready":True,"model_version":store.version,
            "approved_horizons":store.report["approved_horizons"]}

@app.get("/forecast-horizons")
def horizons():
    store.refresh()
    if store.report is None:
        return {"ready":False,"approved_horizons":[],"notice":"Chưa có mô hình dự báo vượt kiểm định."}
    return {"ready":True,"model_version":store.version,
            "approved_horizons":store.report["approved_horizons"],
            "quality_metrics":{h:{"mae_vnd":v.get("mae_vnd"),"wape":v.get("wape"),
                                    "n_test":v.get("n_test")}
                               for h,v in store.report["horizons"].items() if v["status"]=="approved"}}

@app.post("/forecast-price")
def forecast_price(payload:ForecastRequest,x_api_key:Optional[str]=Header(default=None)):
    verify_api_key(x_api_key)
    if payload.horizon_months not in HORIZONS:
        raise HTTPException(status_code=422,detail="UNSUPPORTED_HORIZON")
    if payload.latest_price_date>date.today():
        raise HTTPException(status_code=422,detail="SOURCE_PRICE_DATE_IN_FUTURE")
    age=(date.today()-payload.latest_price_date).days
    if age>365:
        raise HTTPException(status_code=422,detail="BASE_PRICE_STALE: giá DAV đã quá 365 ngày; cần giá gần hơn để dự báo từ hiện tại")
    store.refresh()
    if store.model is None or store.report is None:
        raise HTTPException(status_code=503,detail="NO_APPROVED_FORECAST")
    h=str(payload.horizon_months)
    metrics=store.report["horizons"].get(h,{})
    if metrics.get("status")!="approved":
        raise HTTPException(status_code=422,detail="HORIZON_NOT_APPROVED: chưa có dự báo đủ tin cậy cho thời hạn này")
    row={k:canonical(getattr(payload,k)) if k in ("price_type","unit")
         else ((getattr(payload,k) or "UNKNOWN").strip() or "UNKNOWN") for k in CATEGORICAL}
    row.update(log_last_price=math.log(payload.latest_price_vnd),
               previous_change=0.0,days_since_previous=0.0,
               origin_year=float(date.today().year),
               origin_month=float(date.today().month),
               horizon_months=float(payload.horizon_months))
    frame=pd.DataFrame([row],columns=FEATURES)
    try:
        predicted_change=float(store.model.predict(frame)[0])
        predicted_change=min(4.0,max(-4.0,predicted_change))
        candidate=payload.latest_price_vnd*math.exp(predicted_change)
        weight=float(metrics["weight"])
        value=max(0.0,(1-weight)*payload.latest_price_vnd+weight*candidate)
        interval_error=float(metrics["calibration_log_error_q90"])
        if not (math.isfinite(value) and math.isfinite(interval_error)):
            raise ValueError("Non-finite model result")
    except Exception:
        raise HTTPException(status_code=503,detail="INVALID_FORECAST_OUTPUT")
    return {
        "forecast_price_vnd":round(value),
        "baseline_price_vnd":round(payload.latest_price_vnd),
        "currency":"VND","unit":payload.unit,"price_type":payload.price_type,
        "horizon_months":payload.horizon_months,
        "forecast_date":advance_months(date.today(),payload.horizon_months).isoformat(),
        "source_price_date":payload.latest_price_date.isoformat(),
        "change_percent":round((value/payload.latest_price_vnd-1)*100,2),
        "interval_low_vnd":round(value*math.exp(-interval_error)),
        "interval_high_vnd":round(value*math.exp(interval_error)),
        "test_mae_vnd":metrics["mae_vnd"],"test_wape":metrics["wape"],
        "model_version":store.version,
        "warning":"Giá DAV gốc đã hơn 180 ngày; cần cập nhật giá hiện tại." if age>180 else None,
        "note":"Dự báo mức giá kê khai có thể xuất hiện gần thời hạn chọn, không phải giá niêm yết chắc chắn tại ngày đó."
    }
