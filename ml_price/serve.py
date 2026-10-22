"""PharmaBiz aggregate medicine price trend API.

No per-drug estimate or prediction endpoints. GET /market-forecast returns
only a screened, aggregate paired-declaration report from Cloudflare R2.
"""
from fastapi import FastAPI, HTTPException
from ml_price.market_store import store

app=FastAPI(title="PharmaBiz Market Price Outlook",docs_url=None,redoc_url=None)

@app.get("/health")
def health():
    return {"status":"ok","kind":"aggregate-market-price-outlook",
            "report_loaded":store.report is not None}

@app.get("/ready")
def ready():
    store.refresh()
    if store.report is None:
        raise HTTPException(status_code=503,detail="MARKET_REPORT_NOT_PUBLISHED")
    return {"ready":True,"model_version":store.report["model_version"],
            "approved_horizons":store.report["approved_horizons"],
            "kind":"aggregate-market-price-outlook"}

@app.get("/market-forecast")
def market_forecast():
    store.refresh()
    if store.report is None:
        raise HTTPException(status_code=503,detail="MARKET_REPORT_NOT_PUBLISHED")
    return store.report

@app.post("/forecast-price")
def per_drug_forecast_removed():
    raise HTTPException(status_code=410,detail="PER_DRUG_FORECAST_RETIRED: use /market-forecast")
