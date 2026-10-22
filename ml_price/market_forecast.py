"""Market-wide *matched medicine* declaration-price change analysis.

Each observation compares the SAME registration number, price type and unit
at two actual DAV declaration dates. Ratios (not VND prices) can be aggregated
across units; this is a repeat-declarer sample, NOT a census price index.
Forecasts are only emitted if out-of-time squared-log-error improves on 0%.
"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml_price.forecast import load_gold, clean_observations

# Days around each requested forecast horizon; gaps do not imply daily prices.
HORIZONS = {1:(30,18), 3:(91,35), 6:(183,50), 12:(365,50)}
MIN_TRAIN = 60
MIN_VALIDATION = 20
MIN_TEST = 30
QUALITY_GAIN = .01

def make_market_pairs(observations):
    rows = []
    if observations.empty:
        return pd.DataFrame(columns=["horizon_months","registration_number",
            "price_type","unit","origin_date","target_date","log_change"])
    for (reg,kind,unit),group in observations.groupby(
            ["registration_number","price_type","unit"],sort=False):
        series = list(group.sort_values("date").itertuples(index=False))
        for i,current in enumerate(series[:-1]):
            for h,(days,tolerance) in HORIZONS.items():
                future = [p for p in series[i+1:]
                          if abs((p.date-current.date).days-days)<=tolerance]
                if not future:
                    continue
                target=min(future,key=lambda p:(abs((p.date-current.date).days-days),p.date))
                ratio=float(target.price_vnd)/float(current.price_vnd)
                if not math.isfinite(ratio) or ratio<=0:
                    continue
                log_change=math.log(ratio)
                # Extreme, likely non-comparable declarations cannot anchor
                # the general market: these are flagged for data-quality review.
                if abs(log_change)>math.log(8):
                    continue
                rows.append({
                    "registration_number":reg,"price_type":kind,"unit":unit,
                    "origin_date":current.date,"target_date":target.date,
                    "horizon_months":h,"log_change":log_change,
                })
    return pd.DataFrame(rows,columns=["registration_number","price_type","unit",
        "origin_date","target_date","horizon_months","log_change"])

def robust_mean(values):
    values=np.asarray(values,dtype=float)
    if not len(values):
        return 0.
    low,high=np.quantile(values,[.05,.95])
    return float(np.mean(np.clip(values,low,high)))

def stats(pairs):
    if len(pairs)==0:
        return {"n_pairs":0,"n_series":0,"historical_change_pct":None,
                "share_up_pct":None,"share_down_pct":None,"share_unchanged_pct":None,
                "p10_change_pct":None,"p90_change_pct":None}
    y=np.asarray(pairs.log_change,dtype=float)
    eps=1e-10
    return {
      "n_pairs":int(len(pairs)),
      "n_series":int(pairs[["registration_number","price_type","unit"]].drop_duplicates().shape[0]),
      "historical_change_pct":round(100*math.expm1(robust_mean(y)),2),
      "share_up_pct":round(100*float(np.mean(y>eps)),1),
      "share_down_pct":round(100*float(np.mean(y<-eps)),1),
      "share_unchanged_pct":round(100*float(np.mean(np.abs(y)<=eps)),1),
      "p10_change_pct":round(100*math.expm1(float(np.quantile(y,.1))),2),
      "p90_change_pct":round(100*math.expm1(float(np.quantile(y,.9))),2),
    }

def out_of_time_split(pairs):
    dates=sorted(pairs.origin_date.unique())
    if len(dates)<8:
        return None
    validation_date=dates[int(len(dates)*.65)]
    test_date=dates[int(len(dates)*.82)]
    tr=pairs[(pairs.origin_date<validation_date)&(pairs.target_date<validation_date)].copy()
    va=pairs[(pairs.origin_date>=validation_date)&(pairs.origin_date<test_date)
             &(pairs.target_date<test_date)].copy()
    te=pairs[pairs.origin_date>=test_date].copy()
    return tr,va,te

def evaluate_horizon(full,train,validation,test):
    record=stats(full)
    ntr,nva,nte=len(train),len(validation),len(test)
    record.update(n_train=ntr,n_validation=nva,n_test=nte,
                  forecast_change_pct=None,validation_gain_fraction=None,
                  test_gain_fraction=None,model_method="shrunken-robust-market-log-change")
    if min(ntr/MIN_TRAIN,nva/MIN_VALIDATION,nte/MIN_TEST)<1:
        record["status"]="insufficient_history"
        return record
    # Robust historical matched-pair drift, shrunk to the neutral 0% reference.
    proposal=robust_mean(train.log_change)
    val=np.asarray(validation.log_change,dtype=float)
    test_y=np.asarray(test.log_change,dtype=float)
    weights=(0.,.25,.5,.75,1.)
    best=min(weights,key=lambda w:(float(np.mean((val-w*proposal)**2)),w))
    if best==0:
        record["status"]="rejected_validation"
        return record
    predicted=float(np.clip(proposal*best,-math.log(1.5),math.log(1.5)))
    val_mse=float(np.mean((val-predicted)**2))
    val_baseline=float(np.mean(val**2))
    test_mse=float(np.mean((test_y-predicted)**2))
    test_baseline=float(np.mean(test_y**2))
    val_gain=(val_baseline-val_mse)/max(val_baseline,1e-12)
    test_gain=(test_baseline-test_mse)/max(test_baseline,1e-12)
    record["validation_gain_fraction"]=round(val_gain,6)
    record["test_gain_fraction"]=round(test_gain,6)
    if val_gain<QUALITY_GAIN or test_gain<QUALITY_GAIN:
        record["status"]="rejected_quality_gate"
        return record
    record["status"]="approved"
    record["forecast_change_pct"]=round(100*math.expm1(predicted),2)
    record["test_rmse_log"]=round(math.sqrt(test_mse),5)
    record["baseline_rmse_log"]=round(math.sqrt(test_baseline),5)
    return record

def build_market_report(raw, output_dir="models/market"):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    obs=clean_observations(raw)
    pairs=make_market_pairs(obs)
    report={
      "schema_version":1,"kind":"market-declaration-price-trend",
      "model_version":datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "total_source_records":int(len(raw)),
      "clean_observations":int(len(obs)),
      "paired_observations":int(len(pairs)),
      "forecast_scope":"Thuốc có ít nhất hai lần kê khai cùng số đăng ký, loại giá và đơn vị. Không đại diện toàn bộ thuốc.",
      "methodology":"Tỷ lệ biến động từ giá kê khai ghép cặp cùng thuốc. Trung bình log-ratio winsorized P5-P95; mô hình trôi dạt chung co về 0%. Chia thời gian có embargo và đánh giá trên tập test độc lập theo thời gian.",
      "horizons":{},
    }
    for horizon in HORIZONS:
        sample=pairs[pairs.horizon_months.eq(horizon)].copy() if not pairs.empty else pairs
        slices=out_of_time_split(sample) if len(sample) else None
        if slices is None:
            horizon_report=stats(sample)
            horizon_report.update(status="insufficient_history",n_train=0,
                                  n_validation=0,n_test=0,forecast_change_pct=None)
        else:
            horizon_report=evaluate_horizon(sample,*slices)
        report["horizons"][str(horizon)]=horizon_report
    report["approved_horizons"]=[int(h) for h,item in report["horizons"].items()
                                 if item["status"]=="approved"]
    report["status"]="approved" if report["approved_horizons"] else "historical_only"
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    result=build_market_report(load_gold())
    public={
      "version":result["model_version"],"status":result["status"],
      "paired_observations":result["paired_observations"],
      "horizons":result["horizons"],
    }
    print("MARKET_FORECAST_REPORT",json.dumps(public,ensure_ascii=False))
