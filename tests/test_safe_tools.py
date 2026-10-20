import unittest
from silver_v3.safe_tools.dav_normalizer_v3 import parse_num,norm_ascii
from silver_v3.safe_tools.dav_rxnorm_mapper_v3 import canonical_strength
class TestSafeTools(unittest.TestCase):
 def test_vietnamese_text(self):
  self.assertEqual(norm_ascii('Đường dùng: viên đặt dưới lưỡi'),'duong dung: vien dat duoi luoi')
 def test_numeric_guard(self):
  self.assertIsNone(parse_num('1.000'))
  self.assertIsNone(parse_num('1,000'))
  self.assertEqual(parse_num('0,125'),.125)
 def test_strength_per_denominator(self):
  self.assertEqual(canonical_strength(5,'MG/5ML'),(1,'MG/ML'))
  self.assertEqual(canonical_strength(1,'G/L'),(1,'MG/ML'))
  self.assertEqual(canonical_strength(500,'MCG/5ML'),(.1,'MG/ML'))
if __name__=='__main__':unittest.main()
