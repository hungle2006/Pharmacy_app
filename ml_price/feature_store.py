"""Read-only, version-checked feature model service, independent of market reports."""
import io
import json
import threading
import time
from collections import OrderedDict

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from botocore.config import Config

from ml_price.constants import FEATURES
from ml_price.segments import segment_id
from ml_price.segment_store import SegmentModelStore
from ml_price.feature_schema import KIND, normalize, interval
from ml_price.baseline import predict_with_priors

LATEST_KEY='ml/feature-price/latest.json'

class FeatureStore:
    def __init__(self):
        self.lock=threading.RLock();self.checked=0.;self.report=None;self.prefix=None
        self.models=OrderedDict()

    def refresh(self):
        if time.monotonic()-self.checked<120:
            return
        with self.lock:
            if time.monotonic()-self.checked<120:return
            s3,bucket=SegmentModelStore.s3()
            if s3 is None:return
            try:
                p=json.loads(s3.get_object(Bucket=bucket,Key=LATEST_KEY)['Body'].read())
                prefix=f"ml/feature-price/versions/{p['version']}"
                if p.get('prefix')!=prefix:raise ValueError('INVALID_FEATURE_PREFIX')
                if self.report and self.report['version']==p['version']:
                    self.checked=time.monotonic();return
                report=json.loads(s3.get_object(Bucket=bucket,Key=prefix+'/report.json')['Body'].read())
                if report.get('kind')!=KIND or report.get('schema_version')!=1 or report.get('version')!=p['version']:
                    raise ValueError('INVALID_FEATURE_REPORT')
                for e in report['segments']:
                    if e['id']!=segment_id(e['price_type'],e['unit']):raise ValueError('INVALID_SEGMENT')
                self.report=report;self.prefix=prefix;self.models.clear();self.checked=time.monotonic()
            except Exception as exc:
                self.checked=time.monotonic()-90
                print('Feature report unavailable:',type(exc).__name__,flush=True)

    def get(self,entry):
        with self.lock:
            identifier=entry['id']
            if identifier in self.models:
                self.models.move_to_end(identifier);return self.models[identifier]
            s3,bucket=SegmentModelStore.s3()
            if s3 is None:raise RuntimeError('FEATURE_MODEL_UNAVAILABLE')
            prefix=self.prefix+'/segments/'+identifier
            meta=json.loads(s3.get_object(Bucket=bucket,Key=prefix+'/metadata.json')['Body'].read())
            if meta.get('id')!=identifier or meta.get('version')!=self.report['version'] or meta.get('features')!=FEATURES:
                raise RuntimeError('FEATURE_METADATA_MISMATCH')
            model=CatBoostRegressor()
            # CatBoost requires a filename for a binary model; remove after loading.
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory(prefix='pharmabiz-feature-') as temp:
                path=Path(temp)/'model.cbm'
                path.write_bytes(s3.get_object(Bucket=bucket,Key=prefix+'/model.cbm')['Body'].read())
                model.load_model(str(path))
            self.models[identifier]=(model,meta)
            while len(self.models)>3:self.models.popitem(last=False)
            return model,meta

    def predict(self,payload):
        self.refresh()
        if self.report is None:raise RuntimeError('FEATURE_REPORT_NOT_READY')
        key=segment_id(payload['price_type'],payload['unit'])
        entry=next((e for e in self.report['segments'] if e['id']==key and 'metrics' in e),None)
        if entry is None:raise ValueError('UNSUPPORTED_PRICE_SEGMENT')
        model,meta=self.get(entry)
        values={f:normalize(payload.get(f)) for f in FEATURES}
        if values['ingredient'] not in meta['vocab']['ingredient']:
            raise ValueError('UNKNOWN_INGREDIENT')
        frame=pd.DataFrame([values],columns=FEATURES)
        base,levels=predict_with_priors(frame,meta['baseline_priors'])
        raw=np.asarray(model.predict(frame),dtype=float)
        learned=np.maximum(0,np.expm1(np.minimum(raw,40)) if meta['target_transform']=='log1p' else raw)
        value=(1-meta['alpha'])*base+meta['alpha']*learned
        low,high=interval(value,meta['interval_q'])
        return {'kind':KIND,'version':meta['version'],'status':entry['status'],
                'prediction_vnd':round(float(value[0]),2),'currency':'VND','unit':entry['unit'],
                'price_type':entry['price_type'],'lower_vnd':round(float(low[0]),2),'upper_vnd':round(float(high[0]),2),
                'interval_nominal_pct':90,'interval_test_coverage_pct':meta['interval']['test_coverage_pct'],
                'test_mae_vnd':meta['metrics']['mae_vnd'],'test_n':entry['n_test'],
                'supported_test':meta['supported_test'],
                'method':'group_median' if meta['alpha']==0 else 'catboost' if meta['alpha']==1 else 'catboost_group_median_blend',
                'baseline_match_level':int(levels[0]),'normalized_features':values,
                'unseen_fields':[f for f in FEATURES if values[f] not in meta['vocab'][f]],
                'notice':'Observed declared-price estimate for research; not future price or a retail quote.'}

feature_store=FeatureStore()
