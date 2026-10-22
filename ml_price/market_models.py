"""Leakage-safe DAV market model comparison; no per-product prices are published.

Candidate selection uses expanding walk-forward validation BEFORE a final
chronological holdout. The holdout is never used to choose a candidate.
"""
import math
import numpy as np
import pandas as pd

MODEL_NAMES = ('time_weighted', 'hierarchical', 'temporal_ridge')
LOG_LIMIT = math.log(4.0)
MIN_TRAIN, MIN_VALIDATION, MIN_TEST = 50, 20, 20


def _log_change(frame):
    return np.clip(np.log(frame.target_price.to_numpy(dtype=float) /
                          frame.last_price.to_numpy(dtype=float)), -LOG_LIMIT, LOG_LIMIT)


def _weights(train):
    dates = pd.to_datetime(train.origin_date, utc=True)
    age = (dates.max() - dates).dt.total_seconds().to_numpy() / 86400.0
    decay = np.exp(-math.log(2) * np.maximum(age, 0) / 730.0)
    counts = train.registration_number.astype(str).value_counts()
    return decay / train.registration_number.astype(str).map(counts).to_numpy(dtype=float)


def _features(frame):
    dates = pd.to_datetime(frame.origin_date, utc=True)
    year = (dates - pd.Timestamp('2020-01-01', tz='UTC')).dt.total_seconds().to_numpy() / (86400 * 365.25)
    month = dates.dt.month.to_numpy(dtype=float)
    previous = (pd.to_numeric(frame['previous_change'], errors='coerce').fillna(0).to_numpy(dtype=float)
                if 'previous_change' in frame else np.zeros(len(frame)))
    gap = (pd.to_numeric(frame['days_since_previous'], errors='coerce').fillna(0).to_numpy(dtype=float)
           if 'days_since_previous' in frame else np.zeros(len(frame)))
    return np.column_stack([np.ones(len(frame)), np.clip(year, -15, 20),
                            np.sin(2 * np.pi * month / 12), np.cos(2 * np.pi * month / 12),
                            np.clip(previous, -1, 1), np.clip(gap, 0, 1460) / 365.25])


def fit_predict(train, targets, candidate):
    """Only train labels and features available at the forecast origin are read."""
    y = _log_change(train)
    w = _weights(train)
    # Outliers cannot dominate the small repeated-declaration sample.
    lo, hi = np.quantile(y, [.05, .95])
    y = np.clip(y, lo, hi)
    global_trend = float(np.average(y, weights=w))
    if candidate == 'time_weighted':
        return np.full(len(targets), global_trend)
    if candidate == 'hierarchical':
        # Partial pooling: sparse subgroups shrink to their parent estimate.
        pred = np.full(len(targets), global_trend)
        for columns, strength in [(('price_type', 'unit'), 16.),
                                  (('ingredient',), 20.),
                                  (('ingredient', 'price_type', 'unit'), 30.)]:
            if not all(col in train and col in targets for col in columns):
                continue
            levels = train[list(columns)].fillna('UNKNOWN').astype(str).agg('\x1f'.join, axis=1)
            queries = targets[list(columns)].fillna('UNKNOWN').astype(str).agg('\x1f'.join, axis=1)
            sums = pd.DataFrame({'key': levels, 'wy': w * y, 'w': w})
            groups = sums.groupby('key', sort=False)[['wy', 'w']].sum()
            # Mean sample weight varies with recency, so use effective support count.
            scale = max(float(np.mean(w)), 1e-9)
            bykey = {k: (float(r.wy), float(r.w)) for k, r in groups.iterrows()}
            for index, key in enumerate(queries):
                if key in bykey:
                    wy, support = bykey[key]
                    pred[index] = (wy + strength * scale * pred[index]) / (support + strength * scale)
        return np.clip(pred, -math.log(1.5), math.log(1.5))
    if candidate == 'temporal_ridge':
        X = _features(train)
        T = _features(targets)
        # Heavy regularization for sparse and irregular yearly/monthly series.
        penalties = np.diag([2., 30., 20., 20., 35., 25.])
        weighted = X * w[:, None]
        coefficients = np.linalg.solve(X.T @ weighted + penalties,
                                       X.T @ (w * y))
        return np.clip(T @ coefficients, -math.log(1.5), math.log(1.5))
    raise ValueError('Unknown candidate: ' + str(candidate))


def rolling_folds(examples, horizon):
    """Expanding-window origin folds with a target-date embargo at each boundary."""
    frame = examples[examples.horizon_months.eq(horizon)].sort_values('origin_date').copy()
    dates = sorted(frame.origin_date.unique())
    if len(dates) < 12:
        return []
    # Fixed quantiles, never selected by model accuracy.
    cutoffs = [dates[int((len(dates)-1) * q)] for q in (.42, .57, .72, .84)]
    folds = []
    for start, end in zip(cutoffs[:-1], cutoffs[1:]):
        training = frame[frame.target_date.lt(start)].copy()
        validation = frame[frame.origin_date.ge(start) & frame.origin_date.lt(end) &
                           frame.target_date.lt(end)].copy()
        if len(training) >= MIN_TRAIN and len(validation) >= MIN_VALIDATION:
            folds.append((training, validation, start, end))
    return folds


def _bootstrap_gain(errors_model, errors_base, groups, repeats=300):
    """95% CI for out-of-sample MAE gain, resampling registration clusters."""
    group = np.asarray(groups).astype(str)
    unique, inv = np.unique(group, return_inverse=True)
    sums_model = np.bincount(inv, weights=errors_model, minlength=len(unique))
    sums_base = np.bincount(inv, weights=errors_base, minlength=len(unique))
    rng = np.random.default_rng(20261022)
    samples = rng.integers(0, len(unique), size=(repeats, len(unique)))
    model = sums_model[samples].sum(axis=1)
    base = sums_base[samples].sum(axis=1)
    gains = (base - model) / np.maximum(base, 1e-10)
    return [round(float(x * 100), 2) for x in np.quantile(gains, [.025, .975])]


def _market_references(observations, horizon):
    """Use latest *observed* filings; do not substitute unobserved future prices."""
    if observations is None or observations.empty:
        return pd.DataFrame()
    from ml_price.forecast import make_feature
    rows = []
    newest = pd.to_datetime(observations.date, utc=True).max()
    earliest = newest - pd.Timedelta(days=730)
    for (registration, kind, unit), group in observations.groupby(
            ['registration_number', 'price_type', 'unit'], sort=False):
        ordered = group.sort_values('date')
        if len(ordered) < 2:
            continue
        last = ordered.iloc[-1]
        if pd.Timestamp(last.date) < earliest:
            continue
        previous = ordered.iloc[-2]
        features = make_feature(last, previous, horizon)
        features.update(registration_number=registration, origin_date=last.date)
        rows.append(features)
    return pd.DataFrame(rows)


def evaluate_market_horizon(examples, horizon, observations=None):
    """Compare three models on rolling validation and one untouched final test."""
    frame = examples[examples.horizon_months.eq(horizon)].sort_values('origin_date').copy()
    result = dict(status='insufficient_history', forecast_change_pct=None,
                  reason='INSUFFICIENT_WALK_FORWARD_HISTORY', selected_model=None,
                  n_walkforward_folds=0, model_comparison=[], walkforward_folds=[],
                  n_train=0, n_validation=0, n_test=0, test_gain_ci95_pct_points=None,
                  forecast_sample_ci90_pct=None)
    if len(frame) < MIN_TRAIN + MIN_VALIDATION + MIN_TEST:
        return result
    dates = sorted(frame.origin_date.unique())
    if len(dates) < 12:
        return result
    # Final 16% of origin dates are locked away from candidate selection.
    holdout_start = dates[int((len(dates)-1) * .84)]
    trainpool = frame[frame.target_date.lt(holdout_start)].copy()
    holdout = frame[frame.origin_date.ge(holdout_start)].copy()
    result.update(n_train=len(trainpool), n_test=len(holdout),
                  holdout_start=str(pd.Timestamp(holdout_start).date()))
    if len(trainpool) < MIN_TRAIN or len(holdout) < MIN_TEST or holdout.registration_number.nunique() < 15:
        result['reason'] = 'INSUFFICIENT_CHRONOLOGICAL_HOLDOUT'
        return result
    folds = rolling_folds(frame, horizon)
    result['n_walkforward_folds'] = len(folds)
    result['n_validation'] = sum(len(v) for _, v, _, _ in folds)
    result['walkforward_folds'] = [dict(train=len(t), validation=len(v),
                                        train_labels_before=str(pd.Timestamp(start).date()),
                                        validation_ends_before=str(pd.Timestamp(end).date()))
                                    for t, v, start, end in folds]
    if len(folds) < 2:
        return result
    measured = {}
    for model in ('baseline',) + MODEL_NAMES:
        errors = []
        for training, validation, _, _ in folds:
            truth = _log_change(validation)
            predictions = np.zeros(len(validation)) if model == 'baseline' else fit_predict(training, validation, model)
            errors.extend(np.abs(truth - predictions).tolist())
        measured[model] = float(np.mean(errors))
    baseline = measured['baseline']
    comparison = sorted([(name, (baseline - score) / max(baseline, 1e-10), score)
                         for name, score in measured.items() if name != 'baseline'], key=lambda x: (-x[1], x[0]))
    result['model_comparison'] = [dict(name=name, validation_gain_pct=round(gain*100, 3),
                                        validation_log_mae=round(score, 6))
                                  for name, gain, score in comparison]
    result['validation_baseline_log_mae'] = round(baseline, 6)
    if not comparison or comparison[0][1] < .01 or baseline <= 1e-10:
        result.update(status='rejected_quality_gate', reason='NO_VALIDATION_IMPROVEMENT',
                      test_gain_fraction=None)
        return result
    winner = comparison[0][0]
    prediction = fit_predict(trainpool, holdout, winner)
    truth = _log_change(holdout)
    model_errors = np.abs(truth - prediction)
    baseline_errors = np.abs(truth)
    baseline_test = float(np.mean(baseline_errors))
    model_test = float(np.mean(model_errors))
    gain = (baseline_test - model_test) / max(baseline_test, 1e-10)
    ci = _bootstrap_gain(model_errors, baseline_errors, holdout.registration_number)
    result.update(selected_model=winner, test_gain_fraction=round(gain, 6),
                  test_gain_ci95_pct_points=ci,
                  test_log_mae=round(model_test, 6),
                  test_baseline_log_mae=round(baseline_test, 6),
                  test_n_products=int(holdout.registration_number.nunique()))
    if gain < .01:
        result.update(status='rejected_quality_gate', reason='TEST_NOT_BETTER_THAN_BASELINE')
        return result
    reference = _market_references(observations, horizon)
    if reference.empty or reference.registration_number.nunique() < 15:
        result['reason'] = 'INSUFFICIENT_CURRENT_REFERENCE'
        return result
    # After frozen holdout evaluation, retrain with now-known labeled history.
    final_preds = fit_predict(frame, reference, winner)
    mean_prediction = float(np.mean(final_preds))
    rng = np.random.default_rng(20261022 + horizon)
    draws = rng.integers(0, len(final_preds), size=(300, len(final_preds)))
    agg = 100 * np.expm1(np.mean(final_preds[draws], axis=1))
    result.update(status='approved', reason='approved',
                  forecast_change_pct=round(float(100 * np.expm1(mean_prediction)), 2),
                  forecast_sample_ci90_pct=[round(float(v), 2) for v in np.quantile(agg, [.05, .95])],
                  reference_products=int(reference.registration_number.nunique()),
                  forecast_asof=str(pd.to_datetime(reference.origin_date, utc=True).max().date()))
    return result


def exploratory_scenario(examples, horizon, observations=None, preferred_model=None):
    """Optional *unvalidated* scenario, never an approved forecast.

    Train with known observed price pairs. If recent repeated-filing reference
    products exist, produce a grouped log-change scenario using only their
    observable features. Without references, do not invent a future projection.
    """
    frame = examples[examples.horizon_months.eq(horizon)].copy()
    if len(frame) < 20 or frame.registration_number.nunique() < 15:
        return None
    reference = _market_references(observations, horizon)
    if reference.empty or reference.registration_number.nunique() < 15:
        return None
    model = preferred_model if preferred_model in MODEL_NAMES else 'time_weighted'
    predicted_logs = np.clip(fit_predict(frame, reference, model),
                             -math.log(1.5), math.log(1.5))
    # Give each registration equal weight, even if it has multiple price kinds.
    by_reg = pd.DataFrame({'registration': reference.registration_number.astype(str),
                           'change': predicted_logs}).groupby('registration').change.mean()
    value = float(100 * np.expm1(by_reg.mean()))
    if not math.isfinite(value):
        return None
    return {'experimental_change_pct': round(value, 2),
            'experimental_model': model,
            'experimental_reference_products': int(len(by_reg)),
            'experimental_source': 'observed_repeated_DAV_filings',
            'experimental_label': 'UNVALIDATED_EXPLORATORY_SCENARIO',
            'experimental_warning': ('Model estimate for research only. Has NOT passed '
                                     'the out-of-sample quality gate; not a validated price forecast.') }
