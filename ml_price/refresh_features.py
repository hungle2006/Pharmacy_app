"""Change-aware Gold snapshot -> evaluated feature model bundle (publication separate)."""
import hashlib
import json
import os
from pathlib import Path
from botocore.exceptions import ClientError
from ml_price.train_catalog import load_all_gold
from ml_price.segments import canonical
from ml_price.feature_dataset import snapshot_fingerprint, POLICY_VERSION
from ml_price.feature_store import LATEST_KEY
from ml_price.segment_store import SegmentModelStore


def recipe_fingerprint():
    root=Path(__file__).parent
    digest=hashlib.sha256()
    for name in ('feature_dataset.py','feature_price.py','feature_schema.py','baseline.py',
                 'train.py','train_catalog.py','constants.py','requirements-train.txt','refresh_features.py'):
        digest.update(name.encode());digest.update((root/name).read_bytes())
    return digest.hexdigest()


def published_identity(s3,bucket):
    try:
        pointer=json.loads(s3.get_object(Bucket=bucket,Key=LATEST_KEY)['Body'].read())
        return pointer.get('training_identity')
    except ClientError as exc:
        if str(exc.response.get('Error',{}).get('Code')) in ('NoSuchKey','404'):
            return None
        raise


def refresh(directory='models/features', force=False):
    from ml_price.feature_price import train_all
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    raw=load_all_gold()
    for col in ('price_type','unit'):raw[col]=raw[col].map(canonical)
    raw=raw[raw.price_type.ne('') & raw.unit.ne('')].copy()
    if raw.empty:raise RuntimeError('EMPTY_GOLD_SNAPSHOT')
    identity={'data_sha256':snapshot_fingerprint(raw),'recipe_sha256':recipe_fingerprint(),
              'policy':POLICY_VERSION}
    s3,bucket=SegmentModelStore.s3()
    if s3 is None:raise RuntimeError('R2_NOT_CONFIGURED')
    previous=published_identity(s3,bucket)
    changed=force or previous!=identity
    result={'changed':changed,'training_identity':identity,'source_rows':len(raw)}
    if changed:
        # A reproducible private input snapshot; not included in public API report.
        raw.to_csv(root/'input.csv.gz',index=False,compression='gzip')
        report=train_all(raw,directory)
        report['training_identity']=identity
        report['training_policy']={'serving_bundle':'frozen_evaluated_model',
            'refit_after_test':False,'reason':'Keep test metrics and calibration attached to the exact served model.',
            'latest_selection':'Latest valid source date per registration, price type and unit; ambiguous latest observations excluded.'}
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        result['version']=report['version']
    (root/'refresh.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('changed='+str(changed).lower()+'\n')
    print('FEATURE_REFRESH',json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    refresh(force=os.environ.get('FORCE_TRAIN','false').lower()=='true')
