"""Training-only category median priors persisted for hybrid price inference.

Keys use JSON-encoded tuples to prevent collisions between ingredient names.
All priors are fitted on chronological TRAIN rows only (no validation/test leakage).
"""
import json
import numpy as np
from ml_price.constants import FEATURES

LEVEL_COLUMNS = (
    ("ingredient",),
    ("ingredient", "dosage_form"),
    ("ingredient", "strength", "dosage_form"),
)

def make_key(values):
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))

def build_priors(train):
    maps = {}
    for level, cols in enumerate(LEVEL_COLUMNS, start=1):
        group = train.groupby(list(cols), dropna=False)["price_vnd"].median()
        entries = {}
        for key, median in group.items():
            values = key if isinstance(key, tuple) else (key,)
            entries[make_key(values)] = float(median)
        maps[str(level)] = entries
    return {"maps": maps, "fallback": float(train["price_vnd"].median())}

def predict_with_priors(features, priors):
    """Return numeric baseline and match-level: 3 exact, 2 ing/form, 1 ing, 0 unknown."""
    missing = set(FEATURES) - set(features.columns)
    if missing:
        raise ValueError("Missing baseline inputs: " + ", ".join(sorted(missing)))
    count = len(features)
    preds = np.full(count, float(priors["fallback"]), dtype=float)
    levels = np.zeros(count, dtype=int)
    for level, cols in enumerate(LEVEL_COLUMNS, start=1):
        mapping = priors["maps"][str(level)]
        for i, values in enumerate(features[list(cols)].itertuples(index=False, name=None)):
            value = mapping.get(make_key(values))
            if value is not None:
                preds[i] = float(value)
                levels[i] = level
    return preds, levels

def blend_predictions(prior, model_prediction, levels, weights):
    weight = np.asarray([float(weights[str(int(level))]) for level in levels], dtype=float)
    if (weight < 0).any() or (weight > 1).any():
        raise ValueError("Hybrid weights must lie between zero and one")
    return np.maximum(0, (1 - weight) * np.asarray(prior) + weight * np.asarray(model_prediction))
