"""Publish complete feature experiment, including rejected results for transparency."""
import json
from pathlib import Path
from ml_price.feature_store import LATEST_KEY
from ml_price.segment_store import SegmentModelStore

def upload(directory='models/features'):
    root=Path(directory);report=json.loads((root/'report.json').read_text())
    s3,bucket=SegmentModelStore.s3()
    if s3 is None:raise RuntimeError('R2_NOT_CONFIGURED')
    prefix='ml/feature-price/versions/'+report['version']
    for e in report['segments']:
        if 'metrics' not in e:continue
        for name in ('model.cbm','metadata.json'):
            s3.upload_file(str(root/'segments'/e['id']/name),bucket,prefix+'/segments/'+e['id']+'/'+name)
    s3.upload_file(str(root/'report.json'),bucket,prefix+'/report.json')
    s3.put_object(Bucket=bucket,Key=LATEST_KEY,Body=json.dumps({'version':report['version'],'prefix':prefix}).encode(),
                  ContentType='application/json',CacheControl='no-cache')
    print('Published feature-price evaluation:',report['version'],report['evaluated_segments'],'segments')

if __name__=='__main__':upload()
