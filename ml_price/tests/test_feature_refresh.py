import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from ml_price.refresh_features import refresh, published_identity
from ml_price.tests.test_feature_dataset import LatestDatasetTests
from botocore.exceptions import ClientError

class RefreshTests(unittest.TestCase):
    def test_unchanged_inputs_skip_training(self):
        raw=LatestDatasetTests().sample()
        with tempfile.TemporaryDirectory() as d, patch('ml_price.refresh_features.load_all_gold',return_value=raw), patch('ml_price.refresh_features.SegmentModelStore.s3',return_value=(Mock(),'bucket')), patch('ml_price.refresh_features.published_identity') as prev, patch('ml_price.feature_price.train_all') as train:
            from ml_price.feature_dataset import snapshot_fingerprint, POLICY_VERSION
            from ml_price.refresh_features import recipe_fingerprint
            prev.return_value={'data_sha256':snapshot_fingerprint(raw),'recipe_sha256':recipe_fingerprint(),'policy':POLICY_VERSION}
            r=refresh(d)
            self.assertFalse(r['changed']);train.assert_not_called()
            self.assertFalse((Path(d)/'input.csv.gz').exists())

    def test_missing_pointer_is_first_run_but_access_failure_is_not(self):
        s3=Mock()
        s3.get_object.side_effect=ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
        self.assertIsNone(published_identity(s3,'b'))
        s3.get_object.side_effect=ClientError({'Error':{'Code':'AccessDenied'}},'GetObject')
        with self.assertRaises(ClientError):published_identity(s3,'b')

    def test_new_data_writes_snapshot_and_identity(self):
        raw=LatestDatasetTests().sample()
        with tempfile.TemporaryDirectory() as d, patch('ml_price.refresh_features.load_all_gold',return_value=raw), patch('ml_price.refresh_features.SegmentModelStore.s3',return_value=(Mock(),'bucket')), patch('ml_price.refresh_features.published_identity',return_value=None), patch('ml_price.feature_price.train_all',return_value={'version':'v1'}) as train:
            r=refresh(d)
            self.assertTrue(r['changed']);train.assert_called_once()
            report=json.loads((Path(d)/'report.json').read_text())
            self.assertEqual(report['training_identity'],r['training_identity'])
            self.assertFalse(report['training_policy']['refit_after_test'])
            self.assertTrue((Path(d)/'input.csv.gz').exists())
