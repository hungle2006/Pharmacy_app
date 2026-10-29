"""Public aggregate market price trends for the PharmaBiz dashboard.

No individual-medicine forecasting API is provided.
All numbers originate in the real historical DAV data and validated R2 report.
"""
from fastapi import FastAPI, HTTPException
from ml_price.market_store import store

app=FastAPI(title="PharmaBiz Market Price Trends",docs_url=None,redoc_url=None)

@app.get("/health")
def health():
    return {"status":"ok","kind":"dav-market-price-trend",
            "report_loaded":store.report is not None}

@app.get("/ready")
def ready():
    store.refresh()
    if store.report is None:
        raise HTTPException(status_code=503,detail="NO_MARKET_REPORT")
    return {"ready":True,"kind":"dav-market-price-trend",
            "report_version":store.version,
            "approved_horizons":store.report.get("approved_horizons",[]),
            "historical_only":store.report.get("historical_only",True)}

@app.get("/market-forecast")
def market_forecast():
    store.refresh()
    if store.report is None:
        raise HTTPException(status_code=503,detail="MARKET_REPORT_NOT_READY")
    return store.report

# Additive feature-based price estimation. Market forecasts retain their API.
import hmac
import os
from fastapi import Header
from pydantic import BaseModel, Field, ConfigDict
from ml_price.feature_store import feature_store

class FeatureInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    price_type:str=Field(min_length=1,max_length=200)
    unit:str=Field(min_length=1,max_length=100)
    ingredient:str=Field(min_length=1,max_length=2048)
    strength:str=Field(default='',max_length=2048)
    dosage_form:str=Field(default='',max_length=2048)
    manufacturer:str=Field(default='',max_length=2048)
    country:str=Field(default='',max_length=2048)
    package:str=Field(default='',max_length=2048)

@app.get('/feature-price/report')
def feature_report():
    feature_store.refresh()
    if feature_store.report is None:raise HTTPException(503,detail='FEATURE_REPORT_NOT_READY')
    return feature_store.report

@app.post('/feature-price/predict')
def feature_predict(payload:FeatureInput,x_api_key:str=Header(default='')):
    expected=os.getenv('ML_API_KEY','')
    if not expected:raise HTTPException(503,detail='FEATURE_AUTH_NOT_CONFIGURED')
    if not hmac.compare_digest(expected,x_api_key):raise HTTPException(401,detail='UNAUTHORIZED')
    try:
        return feature_store.predict(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(422,detail=str(exc)) from None
    except Exception as exc:
        print('Feature prediction unavailable:',type(exc).__name__,flush=True)
        raise HTTPException(503,detail='FEATURE_MODEL_UNAVAILABLE') from None
