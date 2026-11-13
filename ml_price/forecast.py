"""Leakage-aware forecasting of the next *declared* medicine price.

The target is a future declaration recorded close to the chosen horizon, NOT a
daily retail spot price. Never reuse a current price as an evaluation label.
"""
import json
import math
import os
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error

from ml_price.forecast_schema import HORIZONS, TARGET_DAYS, TOLERANCES, CATEGORICAL, NUMERIC, FEATURES
MIN_TRAIN, MIN_VALIDATION, MIN_TEST = 100, 30, 30

SQL = """
SELECT d.dav_row_id, d.registration_number,
       d.active_ingredient_raw AS ingredient, d.strength_raw AS strength,
       d.dosage_form_raw AS dosage_form, d.manufacturer, d.country,
       d.package AS product_package,
       COALESCE(NULLIF(p.package,''), NULLIF(d.package,'')) AS package,
       d.source AS source_name, p.source AS price_source,
       p.declaration_date, p.price_vnd, p.price_type,
       COALESCE(to_jsonb(p)->>'source_date_basis','LEGACY_UNVERIFIED') AS source_date_basis,
       COALESCE(NULLIF(p.unit,''), NULLIF(d.unit,'')) AS unit
FROM public.dav_product d
JOIN public.price_record p ON p.dav_row_id=d.dav_row_id
WHERE p.price_vnd > 0 AND p.currency='VND' AND p.declaration_date IS NOT NULL
  AND NOT (COALESCE(d.source,'')='SILVER_R2' AND COALESCE(p.source,'')='DAV_PUBLIC_DRUG_PRICE')
  AND COALESCE(to_jsonb(p)->>'source_date_basis','LEGACY_UNVERIFIED') <> 'UNKNOWN'
"""

def load_gold():
    from sqlalchemy import create_engine, text
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or NEON_DATABASE_URL must be configured")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout":20})
    try:
        with engine.connect() as c:
            return pd.read_sql(text(SQL), c)
    finally:
        engine.dispose()

def clean_observations(raw):
    from ml_price.segments import canonical
    df = raw.copy()
    if {"source_name", "price_source"}.issubset(df.columns):
        df = df[~(df.source_name.eq("SILVER_R2") & df.price_source.eq("DAV_PUBLIC_DRUG_PRICE"))].copy()
    for k in CATEGORICAL + ["registration_number", "product_package"]:
        if k not in df:
            df[k] = ""
        df[k] = df[k].fillna("").astype(str).str.strip()
    df["registration_number"] = df["registration_number"].map(canonical)
    df["price_type"] = df["price_type"].map(canonical)
    df["unit"] = df["unit"].map(canonical)
    df["declaration_date"] = pd.to_datetime(df["declaration_date"], errors="coerce", utc=True)
    df["price_vnd"] = pd.to_numeric(df["price_vnd"], errors="coerce")
    df = df[df["registration_number"].ne("") &
            ~df["registration_number"].isin(["#n/a", "n/a", "na", "null", "unknown", "-"]) &
            df.price_type.ne("") & df.unit.ne("") &
            df.price_vnd.gt(0) & np.isfinite(df.price_vnd) &
            df.declaration_date.notna()].copy()
    # Stop a known data-join error: a product pack containing tablets must not
    # be treated as an ampoule when the price pack is an injectable ampoule pack.
    conflicting = df["product_package"].str.casefold().str.contains("viên", regex=False) & (
        df["unit"].isin(["ống", "lọ"])) & (
        df["package"].str.casefold().str.contains("ống", regex=False))
    df = df[~conflicting].copy()
    df = df[df.declaration_date.le(pd.Timestamp.now(tz="UTC"))].copy()
    for k in CATEGORICAL:
        df[k] = df[k].replace("", "UNKNOWN")
    df["date"] = df["declaration_date"].dt.normalize()
    # Repeated crawls are not new price declarations. Prefer verified DAV
    # filing/publication dates over unverified reception dates for the same ID.
    if "source_date_basis" not in df:
        df["source_date_basis"] = "LEGACY_UNVERIFIED"
    df["source_date_basis"] = df["source_date_basis"].fillna("LEGACY_UNVERIFIED")
    id_keys = ["dav_row_id", "price_type", "unit"]
    verified = df.source_date_basis.isin(["dav_filing_date", "dav_publication_date"])
    has_verified = verified.groupby([df[k] for k in id_keys]).transform("any")
    df = df[verified | ~has_verified].copy()
    verified = df.source_date_basis.isin(["dav_filing_date", "dav_publication_date"])
    multiple_dates = df.groupby(id_keys)["date"].transform("nunique").gt(1)
    fully_verified = verified.groupby([df[k] for k in id_keys]).transform("all")
    # Multiple legacy dates for one source ID are ambiguous revisions. Keep
    # multiple DISTINCT verified DAV filing dates, if they are not in conflict.
    df = df[~multiple_dates | fully_verified].copy()
    if df.empty:
        return df.assign(comparison_key=pd.Series(dtype=str))
    # Missing specifications cannot establish exact comparable-price history.
    complete = df[CATEGORICAL].apply(lambda col: col.map(canonical)).apply(
        lambda col: ~col.isin(["", "unknown", "n/a", "#n/a", "null", "-"])).all(axis=1)
    df = df[complete].copy()
    if df.empty:
        return df.assign(comparison_key=pd.Series(dtype=str))
    # Compare the same specification and packaging, not just a registration.
    df["comparison_key"] = df.apply(lambda row: json.dumps(
        [canonical(row[k]) for k in CATEGORICAL], ensure_ascii=False), axis=1)
    keys = ["registration_number", "comparison_key", "date"]
    prices = df.groupby(keys, sort=False).price_vnd.agg(["min", "max"])
    safe = prices[prices["max"].eq(prices["min"])].index
    df = df.set_index(keys).loc[safe].reset_index()
    df = df.sort_values(["date", "dav_row_id"]).drop_duplicates(keys, keep="last")
    return df.sort_values(keys).reset_index(drop=True)

def make_feature(observation, previous, horizon, history=None):
    """Build model inputs exclusively from declarations known at the origin."""
    last = float(observation.price_vnd)
    prev = float(previous.price_vnd) if previous is not None else last
    gap = int((observation.date - previous.date).days) if previous is not None else 0
    out = {k: str(getattr(observation, k) or "UNKNOWN") for k in CATEGORICAL}
    out.update(log_last_price=math.log(last),
               previous_change=float(np.clip(math.log(last / prev), -4, 4)),
               days_since_previous=float(min(3650, max(0, gap))),
               origin_year=float(observation.date.year),
               origin_month=float(observation.date.month),
               horizon_months=float(horizon))
    # Counts and volatility may use past source events only; NEVER future
    # window statistics, which belong to labels and descriptive diagnostics.
    earlier = list(history) if history is not None else []
    def age_days(event):
        return (observation.date - event.date).days
    out["past_filings_90d"] = float(sum(0 < age_days(e) <= 90 for e in earlier))
    out["past_filings_365d"] = float(sum(0 < age_days(e) <= 365 for e in earlier))
    absolute_moves = [
        abs(math.log(float(earlier[j].price_vnd) / float(earlier[j - 1].price_vnd)))
        for j in range(1, len(earlier))
        if 0 < age_days(earlier[j]) <= 365
    ]
    out["past_abs_log_move_365d"] = float(sum(absolute_moves))
    return out


def make_examples(observations, as_of=None):
    """Use ALL observed filings within complete calendar 3/6/12-month windows.

    Labels are CONDITIONAL on at least one new filing. A missing filing is
    *unknown*, not evidence of a flat price. The last observed filing in each
    completed window defines the observed-window endpoint (NOT a daily spot
    price). The entire window must end before the label can join a train fold.
    """
    cutoff = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now(tz="UTC")
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    cutoff = cutoff.normalize()
    rows = []
    audit = {str(h): {"origins": 0, "unfinished_windows": 0,
                      "no_observed_filing": 0, "labeled_windows": 0}
             for h in HORIZONS}
    if observations.empty:
        result = pd.DataFrame()
        result.attrs["label_audit"] = audit
        return result
    gcols = ["registration_number", "comparison_key"]
    for (registration, _signature), group in observations.groupby(gcols, sort=False):
        data = list(group.sort_values("date").itertuples(index=False))
        dates = [event.date for event in data]
        for i, origin in enumerate(data):
            previous = data[i - 1] if i else None
            history = data[:i]  # NO observations after the prediction origin
            for horizon in HORIZONS:
                diagnostic = audit[str(horizon)]
                diagnostic["origins"] += 1
                window_end = origin.date + pd.DateOffset(months=int(horizon))
                if window_end > cutoff:
                    diagnostic["unfinished_windows"] += 1
                    continue
                last_index = bisect_right(dates, window_end)
                subsequent = data[i + 1:last_index]
                if not subsequent:
                    diagnostic["no_observed_filing"] += 1
                    continue
                path = [origin] + subsequent
                moves = [math.log(float(b.price_vnd) / float(a.price_vnd))
                         for a, b in zip(path[:-1], path[1:])]
                target = subsequent[-1]
                features = make_feature(origin, previous, horizon, history=history)
                features.update(
                    registration_number=registration,
                    origin_date=origin.date,
                    target_date=window_end,  # label known only after window closes
                    observed_target_date=target.date,
                    last_price=float(origin.price_vnd),
                    target_price=float(target.price_vnd),
                    events_in_window=len(subsequent),
                    price_moves_in_window=sum(abs(x) > 1e-12 for x in moves),
                    total_abs_log_move=float(sum(abs(x) for x in moves)),
                    max_observed_price_vnd=float(max(e.price_vnd for e in path)),
                    min_observed_price_vnd=float(min(e.price_vnd for e in path)),
                    days_after_last_event=int((window_end - target.date).days),
                    label_type="CONDITIONAL_LAST_OBSERVED_FILING_IN_WINDOW",
                )
                rows.append(features)
                diagnostic["labeled_windows"] += 1
    result = pd.DataFrame(rows)
    result.attrs["label_audit"] = audit
    return result

def time_split(examples):
    if len(examples) < MIN_TRAIN+MIN_VALIDATION+MIN_TEST:
        return None
    unique_dates = sorted(examples.origin_date.unique())
    if len(unique_dates) < 8:
        return None
    first_val = unique_dates[int(len(unique_dates)*0.65)]
    first_test = unique_dates[int(len(unique_dates)*0.82)]
    # A training outcome may never be after a validation starting point.
    train = examples[(examples.origin_date < first_val) & (examples.target_date < first_val)].copy()
    val = examples[(examples.origin_date >= first_val) & (examples.origin_date < first_test)
                   & (examples.target_date < first_test)].copy()
    test = examples[examples.origin_date >= first_test].copy()
    if min(len(train)/MIN_TRAIN, len(val)/MIN_VALIDATION, len(test)/MIN_TEST) < 1:
        return None
    return train, val, test

def forecast_values(model, frame, weights):
    predicted_change = np.clip(np.asarray(model.predict(frame[FEATURES]),dtype=float), -4, 4)
    ml_price = np.asarray(frame.last_price, dtype=float)*np.exp(predicted_change)
    base = np.asarray(frame.last_price, dtype=float)
    w = np.asarray([weights.get(str(int(h)), 0.0) for h in frame.horizon_months])
    return (1-w)*base + w*ml_price

def fit_forecast(raw, output_dir="models/forecast"):
    root = Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    obs = clean_observations(raw)
    examples = make_examples(obs)
    report = {"schema_version":1, "kind":"future-declared-price-forecast",
              "version":datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
              "source_records":int(len(raw)), "clean_observations":int(len(obs)),
              "candidate_pairs":int(len(examples)), "horizons":{}, "status":"insufficient_history"}
    splits = time_split(examples) if not examples.empty else None
    if splits is None:
        (root/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        return report
    train,val,test=splits
    report.update(n_train=len(train),n_validation=len(val),n_test=len(test),
                  cutoff_validation=str(val.origin_date.min().date()),
                  cutoff_test=str(test.origin_date.min().date()))
    target = np.log(train.target_price.to_numpy()/train.last_price.to_numpy())
    model=CatBoostRegressor(iterations=550,depth=5,learning_rate=0.04,
                            loss_function="RMSE",l2_leaf_reg=7,random_seed=42,
                            thread_count=2,verbose=False,allow_writing_files=False)
    model.fit(train[FEATURES],target,cat_features=CATEGORICAL,
              eval_set=(val[FEATURES],np.log(val.target_price.to_numpy()/val.last_price.to_numpy())),
              early_stopping_rounds=55,use_best_model=True)
    val_pred=val.last_price.to_numpy()*np.exp(np.clip(model.predict(val[FEATURES]),-4,4))
    weights={}
    calibration={}
    for h in HORIZONS:
        selected = val.horizon_months.eq(h).to_numpy()
        if selected.sum() < 15:
            weights[str(h)]=0.0
            calibration[str(h)] = None
            continue
        y=val.target_price.to_numpy()[selected]
        baseline=val.last_price.to_numpy()[selected]
        predicted=val_pred[selected]
        reference_mae=mean_absolute_error(y,baseline)
        scores=sorted([(mean_absolute_error(y,(1-w)*baseline+w*predicted),w) for w in (0,.2,.4,.6,.8,1.0)])
        best,w=scores[0]
        weights[str(h)] = float(w) if best < reference_mae * .98 else 0.0
        combined=(1-weights[str(h)])*baseline+weights[str(h)]*predicted
        calibration[str(h)] = float(np.quantile(np.abs(np.log(y/np.maximum(combined,1))),.9))
    test_pred=forecast_values(model,test,weights)
    for h in HORIZONS:
        mask=test.horizon_months.eq(h).to_numpy()
        if mask.sum()<15:
            report["horizons"][str(h)]={"status":"insufficient_test", "n_test":int(mask.sum())}
            continue
        y=test.target_price.to_numpy()[mask]
        prev=test.last_price.to_numpy()[mask]
        estimated=test_pred[mask]
        mae=float(mean_absolute_error(y,estimated))
        baseline=float(mean_absolute_error(y,prev))
        gain=(baseline-mae)/max(1.,baseline)
        wape=float(np.sum(np.abs(y-estimated))/max(1.,np.sum(np.abs(y))))
        is_approved=(weights[str(h)]>0 and gain>=.01 and wape<=.5
                     and calibration[str(h)] is not None and np.isfinite(mae))
        report["horizons"][str(h)]={
          "status":"approved" if is_approved else "rejected_quality_gate",
          "n_train":int(train.horizon_months.eq(h).sum()),
          "n_validation":int(val.horizon_months.eq(h).sum()),"n_test":int(mask.sum()),
          "mae_vnd":round(mae,2),"baseline_mae_vnd":round(baseline,2),
          "mae_gain_fraction":round(gain,6),"wape":round(wape,5),
          "weight":weights[str(h)],"calibration_log_error_q90":calibration[str(h)]}
    report["approved_horizons"]=[int(h) for h,p in report["horizons"].items() if p["status"]=="approved"]
    report["status"]="approved" if report["approved_horizons"] else "rejected_quality_gate"
    report["features"]=FEATURES
    report["categorical_features"]=CATEGORICAL
    report["limitations"]="Predicted future declaration close to target month, not a daily market quotation. May not reflect a declaration when none occurs."
    if report["approved_horizons"]:
        model.save_model(str(root/"forecast_model.cbm"))
    (root/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    outcome=fit_forecast(load_gold())
    print("FORECAST_REPORT",json.dumps(outcome,ensure_ascii=False))
