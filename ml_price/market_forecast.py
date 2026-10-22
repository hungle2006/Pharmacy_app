"""Population-level DAV price-change report across repeated *same-drug* filings.

This replaces per-drug forecasts with an aggregate market trend dashboard.
Percent changes compare the same registration + price kind + unit; we never
average absolute VND prices across 'viên', 'hộp', 'lọ', etc.

Historical statistics can be published even if out-of-sample forecasting fails.
Forecast percentages are released ONLY after beating the 'no change' benchmark
on chronologically held-out test data, after validation-only shrinkage.
"""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml_price.forecast import clean_observations, load_gold, make_examples, time_split
from ml_price.forecast_schema import HORIZONS
from ml_price.market_models import evaluate_market_horizon

MIN_REFERENCE = 20
MIN_VALIDATION = 20
MIN_TEST = 20
MIN_TRAIN = 50
MAX_RATIO = 4.0  # robust tails for learning and historical summary; see outlier count

def pct(log_ratio):
    return 100.0 * np.expm1(log_ratio)

def finite_number(value, decimals=2):
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), decimals)

def sample_stats(rows):
    """Equal weight per registration: use most recent observed pair for each."""
    if rows.empty:
        return {"n_pairs": 0, "n_products": 0, "historical_change_pct": None}
    ordered = rows.sort_values(["origin_date", "registration_number"], kind="stable")
    latest = ordered.drop_duplicates("registration_number", keep="last")
    raw_log = np.log(latest.target_price.to_numpy(dtype=float)/latest.last_price.to_numpy(dtype=float))
    vals = np.clip(raw_log, -math.log(MAX_RATIO), math.log(MAX_RATIO))
    ratios = pct(vals)
    changed_threshold = math.log(1.01)
    times = latest.origin_date
    return {
        "n_pairs": int(len(rows)),
        "n_products": int(len(latest)),
        "observed_from": str(times.min().date()),
        "observed_to": str(latest.target_date.max().date()),
        "historical_change_pct": finite_number(np.median(ratios)),
        "historical_mean_pct": finite_number(np.mean(ratios)),
        "p10_pct": finite_number(np.quantile(ratios, .10)),
        "p90_pct": finite_number(np.quantile(ratios, .90)),
        "share_increase_pct": finite_number(np.mean(raw_log > changed_threshold)*100),
        "share_decrease_pct": finite_number(np.mean(raw_log < -changed_threshold)*100),
        "share_stable_pct": finite_number(np.mean(np.abs(raw_log) <= changed_threshold)*100),
        "extreme_ratio_count": int((np.abs(raw_log)>math.log(MAX_RATIO)).sum()),
        "method": "One most-recent historical pair per registration; relative change, winsorized for display at 4x",
    }

def history_by_year(rows):
    if rows.empty:
        return []
    latest=rows.sort_values("origin_date").drop_duplicates(
        ["registration_number", "origin_year"], keep="last").copy()
    latest["change"] = 100.0 * np.expm1(np.clip(
        np.log(latest.target_price/latest.last_price),-math.log(MAX_RATIO),math.log(MAX_RATIO)))
    output=[]
    for year,df in latest.groupby("origin_year"):
        if len(df)<6:continue
        output.append({"year":int(year),"n_products":int(df.registration_number.nunique()),
                       "median_change_pct":finite_number(df.change.median()),
                       "mean_change_pct":finite_number(df.change.mean())})
    return output[-12:]

def horizon_time_split(examples, horizon):
    """Split each horizon independently, embargoing outcomes that cross folds.

    Calendar-date boundaries prevent the same filing date being scattered
    across splits. A training outcome must precede the first validation
    origin; likewise a validation outcome must precede the first test origin.
    """
    subset = examples[examples.horizon_months.eq(horizon)].copy()
    if subset.empty:
        return None
    dates = sorted(subset.origin_date.unique())
    if len(dates) < 8:
        return None
    # Search only predeclared calendar cuts, not test-score-optimized cuts.
    candidates = [(0.60, 0.82), (0.55, 0.85), (0.50, 0.80),
                  (0.65, 0.85), (0.50, 0.85)]
    for first, second in candidates:
        a, b = dates[int(len(dates) * first)], dates[int(len(dates) * second)]
        train = subset[(subset.origin_date < a) & (subset.target_date < a)].copy()
        val = subset[(subset.origin_date >= a) & (subset.origin_date < b) &
                     (subset.target_date < b)].copy()
        test = subset[subset.origin_date >= b].copy()
        if (len(train) >= MIN_TRAIN and len(val) >= MIN_VALIDATION and
                len(test) >= MIN_TEST):
            return train, val, test
    return None


def train_change(train,val,test,horizon):
    """One global % change per horizon; select shrinkage only from validation."""
    x=train[train.horizon_months.eq(horizon)]
    v=val[val.horizon_months.eq(horizon)]
    t=test[test.horizon_months.eq(horizon)]
    result={"n_train":len(x),"n_validation":len(v),"n_test":len(t),
            "status":"insufficient_history", "forecast_change_pct":None}
    if len(x)<MIN_TRAIN or len(v)<MIN_VALIDATION or len(t)<MIN_TEST:
        return result
    limits=math.log(MAX_RATIO)
    history=np.clip(np.log(x.target_price.to_numpy()/x.last_price.to_numpy()),-limits,limits)
    v_truth=np.clip(np.log(v.target_price.to_numpy()/v.last_price.to_numpy()),-limits,limits)
    t_truth=np.clip(np.log(t.target_price.to_numpy()/t.last_price.to_numpy()),-limits,limits)
    # Robust global direction; units/price kinds are comparable only after ratio.
    central=float(np.mean(np.clip(history,*np.quantile(history,[.1,.9]))))
    baseline_val=float(np.mean(abs(v_truth)))
    candidates=sorted((float(np.mean(abs(v_truth-central*w))),w)
                      for w in [0,.25,.5,.75,1.0])
    val_mae,weight=candidates[0]
    applied=central*weight
    test_baseline=float(np.mean(abs(t_truth)))
    test_mae=float(np.mean(abs(t_truth-applied)))
    gain=(test_baseline-test_mae)/max(test_baseline,1e-8)
    approved=(weight>0 and val_mae < baseline_val*0.99 and gain>=0.01
              and len(t.registration_number.unique())>=15)
    result.update({
        "status":"approved" if approved else "rejected_quality_gate",
        "validation_log_mae":finite_number(val_mae,5),
        "validation_baseline_log_mae":finite_number(baseline_val,5),
        "test_log_mae":finite_number(test_mae,5),
        "test_baseline_log_mae":finite_number(test_baseline,5),
        "test_gain_fraction":finite_number(gain,5),
        "forecast_change_pct":finite_number(pct(applied)) if approved else None,
        "candidate_change_pct":finite_number(pct(applied)) if weight>0 else None,
        "selected_weight":float(weight),
        "reason":("approved" if approved else
                  "NO_DIRECTIONAL_SIGNAL" if weight==0 else
                  "VALIDATION_NOT_BETTER_THAN_BASELINE" if val_mae >= baseline_val*0.99 else
                  "INSUFFICIENT_DISTINCT_TEST_DRUGS" if len(t.registration_number.unique())<15 else
                  "TEST_NOT_BETTER_THAN_BASELINE"),
        "method":"Horizon-specific embargoed time split; zero-change baseline; log-ratio MAE",
    })
    return result

def make_market_report(raw, directory="models/market"):
    output=Path(directory)
    output.mkdir(parents=True,exist_ok=True)
    observations=clean_observations(raw)
    examples=make_examples(observations)
    report={
        "schema_version":1, "kind":"dav-market-price-trend",
        "version":datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "published_at":datetime.now(timezone.utc).isoformat(),
        "source_records":int(len(raw)),
        "clean_observations":int(len(observations)),
        "labeled_pairs":int(len(examples)),
        "population":"Repeated DAV declarations for the same registration, price type and unit; not all pharmaceuticals and not sales-weighted.",
        "horizons":{},
        "approved_horizons":[],
        "historical_only":True,
        "methodology":"Three candidate models, expanding walk-forward validation, unseen final chronological holdout, registration-cluster bootstrap.",
    }
    if examples.empty:
        for h in HORIZONS:
            report["horizons"][str(h)]={"status":"insufficient_history",
                                         "n_pairs":0, "forecast_change_pct":None}
        (output/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        return report
    for h in HORIZONS:
        subset=examples[examples.horizon_months.eq(h)]
        historical=sample_stats(subset)
        historical["yearly_history"]=history_by_year(subset)
        # Model selection is on embargoed rolling validation folds only.
        # A final chronological holdout determines if a forecast is publishable.
        verification=evaluate_market_horizon(examples,h,observations)
        result={**historical,**verification}
        report["horizons"][str(h)]=result
        if result["status"]=="approved":
            report["approved_horizons"].append(int(h))
    report["historical_only"]=len(report["approved_horizons"])==0
    report["caution"]="Historical statistics are descriptive, not future forecasts. Forecasts apply only to repeatedly declared DAV prices, not every medicine, and are not sales-weighted. Bootstrap ranges represent sample uncertainty, not predictive intervals."
    (output/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    summary=make_market_report(load_gold())
    print("MARKET_FORECAST_REPORT",json.dumps({
        k:({h:{"status":v["status"],"n_pairs":v.get("n_pairs"),
               "n_products":v.get("n_products"),"historical_change_pct":v.get("historical_change_pct"),
               "forecast_change_pct":v.get("forecast_change_pct"),"test_gain_fraction":v.get("test_gain_fraction")}
            for h,v in summary["horizons"].items()} if k=="horizons" else summary[k])
        for k in ("source_records","labeled_pairs","approved_horizons","historical_only","horizons")
    },ensure_ascii=False))
