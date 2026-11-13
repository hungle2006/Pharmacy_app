"""Publish complete feature experiment, including rejected results for transparency."""
import json
from pathlib import Path
from ml_price.feature_store import LATEST_KEY
from ml_price.segment_store import SegmentModelStore

def upload(directory='models/features'):
    root=Path(directory);report=json.loads((root/'report.json').read_text())
    # Validate the entire local bundle before publishing a new pointer.
    from ml_price.feature_schema import KIND
    from ml_price.constants import FEATURES
    from ml_price.segments import segment_id
    if report.get('kind') != KIND or report.get('evaluated_segments',0) < 1:
        raise ValueError('INVALID_FEATURE_REPORT')
    for entry in report['segments']:
        if 'metrics' not in entry:continue
        folder=root/'segments'/entry['id']
        meta=json.loads((folder/'metadata.json').read_text())
        if (entry['id'] != segment_id(entry['price_type'],entry['unit']) or
            meta.get('version') != report['version'] or meta.get('id') != entry['id'] or
            meta.get('features') != FEATURES or not (folder/'model.cbm').stat().st_size):
            raise ValueError('INVALID_FEATURE_BUNDLE')
    s3,bucket=SegmentModelStore.s3()
    if s3 is None:raise RuntimeError('R2_NOT_CONFIGURED')
    prefix='ml/feature-price/versions/'+report['version']
    for e in report['segments']:
        if 'metrics' not in e:continue
        for name in ('model.cbm','metadata.json'):
            s3.upload_file(str(root/'segments'/e['id']/name),bucket,prefix+'/segments/'+e['id']+'/'+name)
    s3.upload_file(str(root/'report.json'),bucket,prefix+'/report.json')
    for name in ('input.csv.gz','refresh.json'):
        if (root/name).exists():s3.upload_file(str(root/name),bucket,prefix+'/'+name)
    s3.put_object(Bucket=bucket,Key=LATEST_KEY,Body=json.dumps({'version':report['version'],'prefix':prefix,'training_identity':report.get('training_identity')}).encode(),
                  ContentType='application/json',CacheControl='no-cache')
    print('Published feature-price evaluation:',report['version'],report['evaluated_segments'],'segments')

if __name__=='__main__':upload()
