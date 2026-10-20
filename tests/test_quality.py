import unittest
from decimal import Decimal
from silver_v3.quality import numeric_evidence,strength_signature,base_flags,decision
class TestQuality(unittest.TestCase):
 def test_ambiguous_number(self):
  self.assertEqual(numeric_evidence('1.000')[1],'AMBIGUOUS_THOUSANDS_DECIMAL')
  self.assertEqual(numeric_evidence('1,000')[1],'AMBIGUOUS_THOUSANDS_DECIMAL')
  self.assertEqual(numeric_evidence('1.000','vi')[0],Decimal(1000))
  self.assertEqual(numeric_evidence('1.000','en')[0],Decimal('1.000'))
 def test_dose_denominator(self):
  self.assertEqual(strength_signature('5 MG/5 ML'),(Decimal(1),'MG/ML'))
  self.assertEqual(strength_signature('1 G/L'),(Decimal(1),'MG/ML'))
  self.assertEqual(strength_signature('500 MCG/5 ML'),(Decimal('.1'),'MG/ML'))
 def test_safety(self):
  self.assertEqual(decision('dav_mapping',{'mapping_status':'VERIFIED_SCD'},[]),'REVIEW_REQUIRED')
  self.assertIn('ICD10CM_TO_WHO_VI_EQUIVALENCE_NOT_VERIFIED',base_flags('medi2',{'code_system':'ICD10CM','code_normalized':'N30','rxcui':'44'}))
 def test_invalid(self):
  self.assertEqual(decision('rxnorm_clean',{},['INVALID_RXCUI']),'REJECTED')
if __name__=='__main__':unittest.main()
