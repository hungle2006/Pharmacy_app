"""Feature-based observed-price estimation; separate from future market forecasts.

Registration-disjoint, strictly date-separated train/validation/calibration/test.
Only validation chooses the model. Calibration fits log-residual intervals. The
untouched test measures accuracy, coverage and baseline improvement once.
"""
import json
import math
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from ml_price.constants import FEATURES
from ml_price.segments import canonical, segment_id
from ml_price.train import clean_data, scores, predict_vnd
from ml_price.train_catalog import load_all_gold
from ml_price.baseline import build_priors, predict_with_priors

from ml_price.feature_schema import KIND, normalize, interval
MIN_PRODUCTS = 500


def prepare(raw):
    df = raw.copy()
    df['price_vnd'] = pd.to_numeric(df.price_vnd, errors='coerce')
    df['declaration_date'] = pd.to_datetime(df.declaration_date, errors='coerce', utc=True)
    df = df[np.isfinite(df.price_vnd) & df.price_vnd.gt(0) &
            df.declaration_date.notna() & df.declaration_date.le(pd.Timestamp.now(tz='UTC'))].copy()
    for col in FEATURES:
        df[col] = df[col].map(normalize)
    df = df[df.ingredient.ne('UNKNOWN')].copy()
    return clean_data(df)


def split_dates(df):
    if len(df) < MIN_PRODUCTS:
        raise ValueError('INSUFFICIENT_DISTINCT_PRODUCTS')
    dates = df.declaration_date
    boundaries = [dates.iloc[min(len(df)-1, int(len(df)*q))] for q in (.60, .75, .85)]
    a,b,c = boundaries
    parts = [df[dates.lt(a)].copy(), df[dates.ge(a) & dates.lt(b)].copy(),
             df[dates.ge(b) & dates.lt(c)].copy(), df[dates.ge(c)].copy()]
    if len(parts[0]) < 200 or min(map(len, parts[1:])) < 40:
        raise ValueError('INSUFFICIENT_DATE_SEPARATION')
    for i in range(3):
        if parts[i].declaration_date.max() >= parts[i+1].declaration_date.min():
            raise AssertionError('DATE_LEAKAGE')
        for j in range(i+1,4):
            if set(parts[i].product_group) & set(parts[j].product_group):
                raise AssertionError('REGISTRATION_LEAKAGE')
    return parts


def metrics(y,p):
    y,p = np.asarray(y,dtype=float),np.asarray(p,dtype=float)
    e=np.abs(y-p)
    return {**scores(y,p), 'rmsle':round(float(np.sqrt(np.mean((np.log1p(y)-np.log1p(p))**2))),5),
            'wape_pct':round(float(e.sum()/y.sum()*100),2),
            'median_ape_pct':round(float(np.median(e/y)*100),2),
            'within_20_pct':round(float(np.mean(e/y<=.2)*100),2),
            'within_50_pct':round(float(np.mean(e/y<=.5)*100),2)}


def fit_segment(raw,folder,version,iterations=650):
    df = prepare(raw)
    train,val,cal,test = split_dates(df)
    priors = build_priors(train)
    base_val,_ = predict_with_priors(val[FEATURES],priors)
    candidates=[]
    for name,transform,objective in [('catboost_log_rmse','log1p','RMSE'),
                                       ('catboost_log_mae','log1p','MAE'),
                                       ('catboost_vnd_mae','identity','MAE')]:
        model=CatBoostRegressor(iterations=iterations,depth=6,learning_rate=.055,
                 loss_function=objective,l2_leaf_reg=7,random_seed=42,thread_count=2,
                 verbose=False,allow_writing_files=False)
        y = np.log1p(train.price_vnd) if transform=='log1p' else train.price_vnd
        v = np.log1p(val.price_vnd) if transform=='log1p' else val.price_vnd
        model.fit(train[FEATURES],y,cat_features=FEATURES,eval_set=(val[FEATURES],v),
                  early_stopping_rounds=55,use_best_model=True)
        pred=predict_vnd(model,val[FEATURES],transform)
        for alpha in (0.,.25,.5,.75,1.):
            blended=(1-alpha)*base_val+alpha*pred
            candidates.append((float(np.mean(np.abs(val.price_vnd-blended))),name,alpha,transform,model))
    candidates.sort(key=lambda x:(x[0],x[2],x[1]))
    val_mae,name,alpha,transform,model=candidates[0]
    def predict(part):
        base,levels=predict_with_priors(part[FEATURES],priors)
        return (1-alpha)*base+alpha*predict_vnd(model,part[FEATURES],transform),base,levels
    cp,_,_=predict(cal)
    residual=np.abs(np.log1p(cal.price_vnd.to_numpy())-np.log1p(cp))
    level=min(1.,math.ceil((len(residual)+1)*.90)/len(residual))
    q=float(np.quantile(residual,level,method='higher'))
    pred,base,levels=predict(test)
    y=test.price_vnd.to_numpy(dtype=float)
    low,high=interval(pred,q)
    score,benchmark=metrics(y,pred),metrics(y,base)
    gain=(benchmark['mae_vnd']-score['mae_vnd'])/max(1.,benchmark['mae_vnd'])*100
    rng=np.random.default_rng(42)
    deltas=[]
    for _ in range(600):
        ix=rng.integers(0,len(test),len(test)); eb=np.abs(y[ix]-base[ix]).mean()
        deltas.append((eb-np.abs(y[ix]-pred[ix]).mean())/max(1.,eb)*100)
    ci=np.quantile(deltas,[.025,.975]).tolist()
    status='approved' if gain>=1 and ci[0]>0 else 'experimental'
    # Metrics for inputs this tool will actually accept, alongside all-test metrics.
    vocab={f:sorted(train[f].unique().tolist()) for f in FEATURES}
    served=test.ingredient.isin(vocab['ingredient']).to_numpy()
    public={
        'id':segment_id(raw.price_type.iloc[0],raw.unit.iloc[0]),'price_type':str(raw.price_type.iloc[0]),
        'unit':str(raw.unit.iloc[0]),'currency':'VND','version':version,'status':status,
        'n_raw':len(raw),'n_clean':len(df),'n_train':len(train),'n_validation':len(val),
        'n_calibration':len(cal),'n_test':len(test),'split_method':'registration_disjoint_strict_dates_60_15_10_15',
        'split_dates':{k:[str(p.declaration_date.min().date()),str(p.declaration_date.max().date())]
                       for k,p in zip(('train','validation','calibration','test'),(train,val,cal,test))},
        'features':FEATURES,'selected_model':name,'catboost_weight':alpha,'validation_mae_vnd':round(val_mae,2),
        'validation_candidates':[{'model':nm,'best_weight':w,'mae_vnd':round(mae,2)}
             for nm in ('catboost_log_rmse','catboost_log_mae','catboost_vnd_mae')
             for mae,_,w,_,_ in [min((x for x in candidates if x[1]==nm),key=lambda x:(x[0],x[2]))]],
        'validation_baseline_mae_vnd':round(float(np.mean(np.abs(val.price_vnd-base_val))),2),
        'metrics':score,'baseline_metrics':benchmark,'test_gain_pct':round(gain,3),
        'test_gain_ci95_pct':list(map(lambda x:round(float(x),3),ci)),
        'interval':{'nominal_pct':90,'test_coverage_pct':round(float(np.mean((y>=low)&(y<=high))*100),2),
                    'test_median_width_vnd':round(float(np.median(high-low)),2),'n_calibration':len(cal)},
        'supported_test':{'n':int(served.sum()),'coverage_pct':round(float(served.mean()*100),2),
                          'metrics':metrics(y[served],pred[served]) if served.any() else None},
        'feature_profile':[{'field':f,'unique':int(df[f].nunique()),'missing':int(df[f].eq('UNKNOWN').sum()),
                            'test_unseen_pct':round(float((~test[f].isin(vocab[f])).mean()*100),2)} for f in FEATURES],
        'feature_importance':[{'field':f,'value':round(float(v),3)} for f,v in
                              zip(FEATURES,model.get_feature_importance())],
        'scatter':[{'actual':round(float(y[i]),2),'predicted':round(float(pred[i]),2)}
                   for i in np.unique(np.linspace(0,len(y)-1,min(120,len(y)),dtype=int))],
        'error_bins':[{'name':n,'value':int(v)} for n,v in zip(
            ['< −50%','−50 đến < −20%','−20 đến < 0%','0 đến < 20%','20 đến < 50%','≥ 50%'],
            np.histogram((pred-y)/y*100,bins=[-np.inf,-50,-20,0,20,50,np.inf])[0])],
        'options':{f:[str(x) for x in train[f].value_counts().head(200).index if x!='UNKNOWN'] for f in FEATURES},
    }
    # Example inputs are held-out test rows, and observed targets are explicit.
    known=np.flatnonzero(served)
    demo_ix=known[np.unique(np.linspace(0,len(known)-1,min(5,len(known)),dtype=int))] if len(known) else []
    public['examples']=[{'features':{f:str(test.iloc[i][f]) for f in FEATURES},
                         'observed_price_vnd':float(y[i]),'predicted_price_vnd':round(float(pred[i]),2)} for i in demo_ix]
    private={'kind':KIND,'version':version,'features':FEATURES,'target_transform':transform,
             'alpha':alpha,'baseline_priors':priors,'vocab':vocab,'interval_q':q,
             'id':public['id'],'price_type':public['price_type'],'unit':public['unit'],'status':status,
             'metrics':score,'interval':public['interval'],'supported_test':public['supported_test']}
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    model.save_model(str(folder/'model.cbm'))
    (folder/'metadata.json').write_text(json.dumps(private,ensure_ascii=False),encoding='utf-8')
    return public


def train_all(raw,directory='models/features'):
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    version=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    df=raw.copy();df['price_type']=df.price_type.map(canonical);df['unit']=df.unit.map(canonical)
    df=df[df.price_type.ne('') & df.unit.ne('')]
    report={'schema_version':1,'kind':KIND,'version':version,'generated_at':datetime.now(timezone.utc).isoformat(),
            'source':'Neon Gold: dav_product JOIN price_record','features':FEATURES,'n_source':len(raw),
            'n_segmented':len(df),'min_products':MIN_PRODUCTS,'segments':[],
            'target':'Positive observed declared VND price per source unit; not future or retail price',
            'excluded_features':['drug_name','dav_row_id','registration_number','price_vnd','selected_scd_rxcui'],
            'method':'Latest positive dated price per registration within each price type and unit. Strictly separate dates and registrations across train, validation, calibration and test. Validation selects the candidate/blend, calibration fits 90% log-residual intervals, test is untouched. No refit after testing.',
            'limitations':['Historical declared prices are heterogeneous and may be outdated.',
              'Unknown ingredients are refused; other unseen categories trigger an explicit warning.',
              'Conformal intervals are calibrated on earlier data; time drift can reduce test coverage below 90%.',
              'Feature importance describes the CatBoost component, not causality; zero CatBoost weight means the group-median baseline is used.',
              'Test bootstrap assumes independent registrations within the held-out snapshot. It does not measure all future uncertainty.']}
    for (kind,unit),group in df.groupby(['price_type','unit'],sort=True):
        identifier=segment_id(kind,unit)
        entry={'id':identifier,'price_type':kind,'unit':unit,'n_raw':len(group),'status':'insufficient_data'}
        cleaned=prepare(group);entry['n_clean']=len(cleaned)
        if len(cleaned)>=MIN_PRODUCTS:
            try:
                entry=fit_segment(group,root/'segments'/identifier,version)
            except ValueError as exc:
                if str(exc) not in ('INSUFFICIENT_DISTINCT_PRODUCTS','INSUFFICIENT_DATE_SEPARATION'):
                    raise
                entry['reason']=str(exc)
        report['segments'].append(entry)
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        print('FEATURE_SEGMENT',unit,entry['status'],'products',entry['n_clean'],
              'test_MAE',entry.get('metrics',{}).get('mae_vnd'),'gain_pct',entry.get('test_gain_pct'),flush=True)
    report['evaluated_segments']=sum('metrics' in e for e in report['segments'])
    report['approved_segments']=sum(e['status']=='approved' for e in report['segments'])
    if not report['evaluated_segments']:
        raise RuntimeError('No segment has enough strictly separated actual Gold products')
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    return report


if __name__=='__main__':
    train_all(load_all_gold())
