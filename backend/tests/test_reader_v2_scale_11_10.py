import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from reader_v2_scale_11_10 import page_key,EasyAdapter

class ScaleTests(unittest.TestCase):
 def test_cache_key_source_geometry_and_config_sensitive(self):
  page={"source_hash":"a"};regions=[{"id":1,"bbox":[1,2,3,4],"type":"x"}]
  first=page_key(page,regions);self.assertEqual(first,page_key(page,regions));self.assertNotEqual(first,page_key({"source_hash":"b"},regions));self.assertNotEqual(first,page_key(page,[{"id":1,"bbox":[1,2,4,4],"type":"x"}]))
 def test_adapter_contract_has_no_model_service(self):
  self.assertEqual(EasyAdapter.config["gpu"],False);self.assertNotIn("ollama",str(EasyAdapter.config).lower())
if __name__=="__main__":unittest.main()
