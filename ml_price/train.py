"""Train a quality-gated CatBoost predictor for ONE comparable Neon Gold price segment."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml_price.constants import FEATURES, SEGMENT_PRICE_TYPE, SEGMENT_UNIT

SQL = """
SELECT d.dav_row_id, d.registration_number,
       d.active_ingredient_raw AS ingredient, d.strength_raw AS strength,
       d.dosage_form_raw AS dosage_form, d.manufacturer, d.country,
       COALESCE(NULLIF(p.package,''),NULLIF(d.package,'')) AS package,
       d.source AS source_name, p.declaration_date, p.price_vnd
FROM public.dav_product d
JOIN public.price_record p ON p.dav_row_id = d.dav_row_id
WHERE p.price_vnd > 0 AND p.currency='VND'
  AND p.price_type = :price_type
  AND LOWER(BTRIM(COALESCE(NULLIF(p.unit,''),NULLIF(d.unit,'')))) = :unit
  AND p.declaration_date IS NOT NULL
"""

def load_gold():
    from sqlalchemy import create_engine, text
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
    if not url:
        raise RuntimeError("Set DATABASE_URL (GitHub Actions secret) to read Neon Gold")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 20})
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(SQL), conn, params={"price_type": SEGMENT_PRICE_TYPE, "unit": SEGMENT_UNIT})
    finally:
        engine.dispose()

def clean_data(raw):
    df = raw.copy()
    needed = ["dav_row_id", "registration_number", "declaration_date", "price_vnd", "source_name", *FEATURES]
    missing = set(needed) - set(df.columns)
    if missing:
        raise ValueError("Gold query missing columns: " + ", ".join(sorted(missing)))
    df["price_vnd"] = pd.to_numeric(df["price_vnd"], errors="coerce")
    df["declaration_date"] = pd.to_datetime(df["declaration_date"], errors="coerce", utc=True)
    df = df[df["price_vnd"].gt(0) & df["price_vnd"].notna() & df["declaration_date"].notna()].copy()
    for field in FEATURES:
        df[field] = df[field].fillna("UNKNOWN").astype(str).str.strip().replace("", "UNKNOWN")
    df["dav_row_id"] = df["dav_row_id"].astype(str)
    df["registration_number"] = df["registration_number"].fillna("").astype(str).str.strip().str.casefold()
    df["product_group"] = np.where(df["registration_number"].ne(""),
                                   "REG:" + df["registration_number"], "DAV:" + df["dav_row_id"])
    df["silver_priority"] = df["source_name"].eq("SILVER_R2").astype(int)
    # Keep latest dated price per registration number; prefer Silver when same date.
    df = df.sort_values(["declaration_date", "silver_priority", "dav_row_id"],
                        ascending=[False, False, True]).drop_duplicates("product_group", keep="first")
    return df.sort_values(["declaration_date", "product_group"]).reset_index(drop=True)

def time_split(df):
    if len(df) < 300:
        raise ValueError(f"Only {len(df)} unique priced products; need >=300")
    n = len(df)
    a, b = int(n * 0.70), int(n * 0.85)
    train, val, test = df.iloc[:a].copy(), df.iloc[a:b].copy(), df.iloc[b:].copy()
    if min(len(train), len(val), len(test)) < 40:
        raise ValueError("Not enough rows for chronological train/validation/test")
    assert not (set(train.product_group) & set(val.product_group))
    assert not (set(train.product_group) & set(test.product_group))
    assert not (set(val.product_group) & set(test.product_group))
    return train, val, test

def group_median_baseline(train, test):
    groups = [["ingredient", "strength", "dosage_form"],
              ["ingredient", "dosage_form"], ["ingredient"]]
    fallback = float(train["price_vnd"].median())
    output = pd.Series(np.nan, index=test.index, dtype="float64")
    for cols in groups:
        reference = train.groupby(cols, dropna=False)["price_vnd"].median()
        keys = pd.MultiIndex.from_frame(test[cols]) if len(cols) > 1 else pd.Index(test[cols[0]])
        values = reference.reindex(keys).to_numpy(dtype="float64")
        output = output.fillna(pd.Series(values, index=test.index))
    return output.fillna(fallback).to_numpy()

def scores(y, prediction):
    return {
        "mae_vnd": round(float(mean_absolute_error(y, prediction)), 2),
        "rmse_vnd": round(float(np.sqrt(mean_squared_error(y, prediction))), 2),
        "r2": round(float(r2_score(y, prediction)), 5),
        "median_ae_vnd": round(float(np.median(np.abs(np.asarray(y) - np.asarray(prediction)))), 2),
    }

def predict_vnd(model, features, target_transform):
    """Convert model outputs back to VND for comparable validation/test MAE."""
    values = np.asarray(model.predict(features), dtype=float)
    if target_transform == "log1p":
        values = np.expm1(np.minimum(values, 40))
    elif target_transform != "identity":
        raise ValueError("Unknown model target transform: " + target_transform)
    return np.maximum(0, values)


def train(raw, directory="models/price"):
    df = clean_data(raw)
    train_df, val_df, test_df = time_split(df)
    # Choose a candidate using ONLY validation data. Never tune to the test set.
    # Log-RMSE can underpredict rare expensive drugs, so also try a direct
    # VND-MAE objective suited to the deployment quality gate.
    candidates = []
    for name, target_transform, objective in (
        ("log_rmse", "log1p", "RMSE"),
        ("vnd_mae", "identity", "MAE"),
    ):
        model = CatBoostRegressor(iterations=700, depth=5, learning_rate=0.05,
                                  loss_function=objective, l2_leaf_reg=5, random_seed=42,
                                  thread_count=2, verbose=False, allow_writing_files=False)
        y_train = np.log1p(train_df.price_vnd) if target_transform == "log1p" else train_df.price_vnd
        y_val = np.log1p(val_df.price_vnd) if target_transform == "log1p" else val_df.price_vnd
        model.fit(train_df[FEATURES], y_train, cat_features=FEATURES,
                  eval_set=(val_df[FEATURES], y_val),
                  early_stopping_rounds=60, use_best_model=True)
        val_pred = predict_vnd(model, val_df[FEATURES], target_transform)
        val_mae = float(mean_absolute_error(val_df.price_vnd, val_pred))
        candidates.append((val_mae, name, target_transform, model))
    candidates.sort(key=lambda item: item[0])
    _, selected_name, target_transform, model = candidates[0]
    prediction = predict_vnd(model, test_df[FEATURES], target_transform)
    baseline = group_median_baseline(train_df, test_df)
    result = scores(test_df.price_vnd, prediction)
    base = scores(test_df.price_vnd, baseline)
    gain = (base["mae_vnd"] - result["mae_vnd"]) / max(1., base["mae_vnd"])
    approved = bool(np.isfinite(gain) and gain >= float(os.getenv("ML_MIN_MAE_GAIN", "0.01")))
    info = {
        "model": "CatBoostRegressor",
        "model_version": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "status": "approved" if approved else "rejected_baseline",
        "price_type": SEGMENT_PRICE_TYPE, "currency": "VND", "unit": SEGMENT_UNIT,
        "features": FEATURES,
        "target_transform": target_transform,
        "selected_candidate": selected_name,
        "validation_mae_vnd": {name: round(mae, 2) for mae, name, _, _ in candidates},
        "target": "Positive observed expected wholesale price including VAT, VND per viên",
        "n_initial_rows": int(len(raw)), "n_distinct_products": int(len(df)),
        "n_train": int(len(train_df)), "n_validation": int(len(val_df)), "n_test": int(len(test_df)),
        "training_dates": [str(train_df.declaration_date.min().date()),
                           str(train_df.declaration_date.max().date())],
        "test_dates": [str(test_df.declaration_date.min().date()),
                       str(test_df.declaration_date.max().date())],
        "metrics": result, "baseline_metrics": base,
        "mae_gain_fraction": round(float(gain), 6),
        "limitations": "Price observation, not a retail quote or medical recommendation.",
    }
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    model.save_model(str(folder / "price_model.cbm"))
    (folder / "metadata.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return info

if __name__ == "__main__":
    report = train(load_gold())
    if report["status"] != "approved":
        print("QUALITY_GATE_REJECTED: CatBoost did not beat the baseline; artifacts retained, model NOT published.")
