"""Train all sufficiently sampled VND price type × unit segments, independently.

Never pool prices across units or label types. Each segment must pass its own
untouched chronological test against the same train-only median benchmark.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from ml_price.segments import canonical, segment_id
from ml_price.train import train, clean_data

SQL_CATALOG = """
SELECT d.dav_row_id, d.registration_number,
       d.active_ingredient_raw AS ingredient, d.strength_raw AS strength,
       d.dosage_form_raw AS dosage_form, d.manufacturer, d.country,
       COALESCE(NULLIF(p.package,''),NULLIF(d.package,'')) AS package,
       d.source AS source_name, p.declaration_date, p.price_vnd,
       p.price_type, COALESCE(NULLIF(p.unit,''), NULLIF(d.unit,'')) AS unit
FROM public.dav_product d
JOIN public.price_record p ON p.dav_row_id = d.dav_row_id
WHERE p.price_vnd > 0 AND p.currency = 'VND'
  AND p.declaration_date IS NOT NULL AND p.price_type IS NOT NULL
"""
MIN_DISTINCT = 300

def load_all_gold():
    from sqlalchemy import create_engine, text
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
    if not url:
        raise RuntimeError("Missing DATABASE_URL / NEON_DATABASE_URL GitHub secret")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 20})
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(SQL_CATALOG), conn)
    finally:
        engine.dispose()

def train_catalog(raw, directory="models/price", min_rows=MIN_DISTINCT):
    if not 300 <= min_rows:
        raise ValueError("Minimum segment size must be >=300 to keep reliable splits")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    df = raw.copy()
    df["price_type"] = df["price_type"].map(canonical)
    df["unit"] = df["unit"].map(canonical)
    df = df[df.price_type.ne("") & df.unit.ne("")].copy()
    summary = {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "minimum_rows": min_rows, "initial_rows": int(len(raw)),
        "grouped_rows": int(len(df)), "evaluated_segments": 0,
        "segments": [],
    }
    for (price_type, unit), group in df.groupby(["price_type", "unit"], sort=True):
        segment = segment_id(price_type, unit)
        entry = {"id": segment, "price_type": price_type, "unit": unit,
                 "n_raw": int(len(group))}
        if len(group) < min_rows:
            entry["status"] = "insufficient_rows"
        else:
            # This dedupe check avoids attempting training on tiny unique cohorts.
            unique = clean_data(group)
            entry["n_distinct_products"] = int(len(unique))
            if len(unique) < min_rows:
                entry["status"] = "insufficient_distinct_products"
            else:
                report = train(group, str(root / "segments" / segment),
                               price_type=price_type, unit=unit)
                summary["evaluated_segments"] += 1
                entry.update({"status": report["status"], "n_distinct_products": report["n_distinct_products"],
                              "model_version": report["model_version"], "metrics": report["metrics"],
                              "baseline_metrics": report["baseline_metrics"],
                              "mae_gain_fraction": report["mae_gain_fraction"]})
        summary["segments"].append(entry)
        # Persist partial progress, even if a later model encounters a genuine error.
        (root / "catalog.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Segment", price_type, "/", unit, ":", entry["status"], flush=True)
    summary["approved_segments"] = sum(s["status"] == "approved" for s in summary["segments"])
    summary["rejected_segments"] = sum(s["status"] == "rejected_baseline" for s in summary["segments"])
    summary["insufficient_segments"] = sum(s["status"].startswith("insufficient") for s in summary["segments"])
    (root / "catalog.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("CATALOG_REPORT", json.dumps({k:v for k,v in summary.items() if k != "segments"}, ensure_ascii=False), flush=True)
    return summary

if __name__ == "__main__":
    result = train_catalog(load_all_gold())
    if result["evaluated_segments"] == 0:
        raise SystemExit("No price segment had enough distinct observations")
