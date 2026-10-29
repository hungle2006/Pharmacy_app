"""Feature endpoint validates source-length strings and authenticates prediction."""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
from ml_price.serve import FeatureInput, feature_predict

class FeatureAPITests(unittest.TestCase):
    def test_real_source_length_fields_are_accepted_but_targets_and_identifiers_are_not(self):
        payload={'price_type':'kk nhập khẩu','unit':'lọ','ingredient':'ingredient',
                 'manufacturer':'m'*306,'package':'p'*355}
        request=FeatureInput(**payload)
        self.assertEqual(len(request.manufacturer),306)
        for more in ({'price_vnd':100},{'dav_row_id':'1'},{'ingredient':'a'*2049}):
            with self.assertRaises(ValidationError):FeatureInput(**{**payload,**more})

    def test_only_authenticated_requests_reach_predictor(self):
        request=FeatureInput(price_type='kind',unit='viên',ingredient='ingredient')
        with patch.dict('os.environ',{'ML_API_KEY':'unit-test-key'}),patch('ml_price.serve.feature_store.predict') as predict:
            with self.assertRaises(HTTPException) as denied:feature_predict(request,'wrong')
            self.assertEqual(denied.exception.status_code,401);predict.assert_not_called()
            predict.return_value={'prediction_vnd':100.}
            self.assertEqual(feature_predict(request,'unit-test-key')['prediction_vnd'],100.)
            predict.side_effect=ValueError('UNKNOWN_INGREDIENT')
            with self.assertRaises(HTTPException) as outside:feature_predict(request,'unit-test-key')
            self.assertEqual(outside.exception.status_code,422)

if __name__=='__main__':unittest.main()
