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
