"""Auditable latest-price snapshot for the six-feature experiment.

A registration contributes at most one observation per price type/unit. Never
choose an arbitrary price from conflicting latest-day observations, or silently
fall back to an older price when the newest observation is ambiguous.
"""
import hashlib
import json
import pandas as pd
import numpy as np
from ml_price.constants import FEATURES
from ml_price.feature_schema import normalize

POLICY_VERSION = 'latest-feature-snapshot-v2'


def latest_snapshot(raw, as_of=None):
    df = raw.copy()
    required = {'dav_row_id', 'registration_number', 'source_name',
                'declaration_date', 'price_vnd', *FEATURES}
    if not required.issubset(df.columns):
        raise ValueError('Missing snapshot columns: ' + ', '.join(sorted(required-set(df.columns))))
    cutoff = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now(tz='UTC')
    cutoff = cutoff.tz_localize('UTC') if cutoff.tzinfo is None else cutoff.tz_convert('UTC')
    df['price_vnd'] = pd.to_numeric(df.price_vnd, errors='coerce')
    df['declaration_date'] = pd.to_datetime(df.declaration_date, errors='coerce', utc=True)
    if 'source_date_basis' not in df:
        df['source_date_basis'] = 'LEGACY_UNVERIFIED'
    df['source_date_basis'] = df.source_date_basis.fillna('LEGACY_UNVERIFIED')
    valid = (np.isfinite(df.price_vnd) & df.price_vnd.gt(0) & df.declaration_date.notna()
             & df.declaration_date.le(cutoff) & df.source_date_basis.ne('UNKNOWN'))
    audit = {'policy': POLICY_VERSION, 'as_of': cutoff.isoformat(), 'n_raw': len(df),
             'excluded_invalid': int((~valid).sum())}
    df = df[valid].copy()
    for col in FEATURES:
        df[col] = df[col].map(normalize)
    df['registration_number'] = df.registration_number.fillna('').astype(str).str.strip().str.casefold()
    df['dav_row_id'] = df.dav_row_id.fillna('').astype(str).str.strip()
    # Missing identity cannot safely be deduplicated or split by registration.
    identifiable = df.registration_number.ne('') | df.dav_row_id.ne('')
    audit['excluded_missing_identity'] = int((~identifiable).sum())
    df = df[identifiable].copy()
    df['product_group'] = np.where(df.registration_number.ne(''), 'REG:'+df.registration_number, 'DAV:'+df.dav_row_id)
    # Select date first, before completeness: a bad latest row must not revive old prices.
    newest = df.groupby('product_group').declaration_date.transform('max')
    latest = df[df.declaration_date.eq(newest)].copy()
    signatures = latest[FEATURES+['price_vnd']].astype(str).apply(lambda row: '\x1f'.join(row), axis=1) if len(latest) else pd.Series(dtype=str)
    latest['_signature'] = signatures
    counts = latest.groupby('product_group')._signature.nunique()
    conflicts = set(counts[counts.gt(1)].index)
    audit['excluded_conflicting_latest_products'] = len(conflicts)
    latest = latest[~latest.product_group.isin(conflicts)].copy()
    audit['excluded_latest_unknown_ingredient'] = int(latest.loc[latest.ingredient.eq('UNKNOWN'), 'product_group'].nunique())
    latest = latest[latest.ingredient.ne('UNKNOWN')].copy()
    latest['_verified'] = latest.source_date_basis.isin(['dav_filing_date','dav_publication_date']).astype(int)
    latest = latest.sort_values(['product_group','_verified','dav_row_id'], ascending=[True,False,True])
    latest = latest.drop_duplicates('product_group').drop(columns=['_signature','_verified'])
    latest = latest.sort_values(['declaration_date','product_group']).reset_index(drop=True)
    audit['n_selected'] = len(latest)
    audit['selected_date_basis'] = {str(k):int(v) for k,v in latest.source_date_basis.value_counts().items()}
    return latest, audit


def snapshot_fingerprint(raw):
    """Order-independent hash of model inputs; exact duplicate crawls add no weight."""
    rows=[]
    for (kind,unit),group in raw.groupby(['price_type','unit'],sort=True):
        clean,_ = latest_snapshot(group)
        cols=['product_group','declaration_date','source_date_basis',*FEATURES,'price_vnd']
        for values in clean[cols].itertuples(index=False,name=None):
            rows.append([str(kind),str(unit),*[str(x) for x in values]])
    payload=json.dumps(sorted(rows),ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(payload.encode()).hexdigest()
