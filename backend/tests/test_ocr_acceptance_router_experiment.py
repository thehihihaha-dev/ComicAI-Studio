import copy,unittest
from app.services.ocr_acceptance_router_experiment import HARD,SAFE,STRUCTURAL,metrics,route,short_bucket,signal_features
class RouterExperimentTests(unittest.TestCase):
 def features(self,count=1,confidence=.99,text="TEST"):
  logical={"bbox":[10,10,110,60],"region_type":"logical_text_region","aggregation_confidence":.8};fragments=[{"predicted_text":text,"ocr_confidence":confidence,"crop_bbox":[9,9,111,61]} for _ in range(count)];f=signal_features(logical,fragments);f["baseline_accepted"]=True;return f
 def test_signal_extraction_is_deterministic_and_gt_independent(self):
  a=self.features();b=self.features();self.assertEqual(a,b);self.assertNotIn("human_gt",a);self.assertEqual("single_block",a["reconstruction_mode"])
 def test_safe_hard_and_structural_contracts(self):
  self.assertEqual(SAFE,route(self.features(),"R2"));self.assertEqual(HARD,route(self.features(confidence=.5),"R2"));self.assertEqual(STRUCTURAL,route(self.features(count=2),"R2"))
 def test_merged_split_never_safe_in_structural_candidates(self):
  for name in ("R2","R3","R4"):self.assertEqual(STRUCTURAL,route(self.features(count=2),name))
 def test_short_text_buckets(self):self.assertEqual(["1-3","4-8","9+"],[short_bucket(x) for x in (3,8,9)])
 def test_false_safe_precision_and_correct_hard(self):
  rows=[{"features":self.features(),"correct":True},{"features":self.features(),"correct":False},{"features":self.features(confidence=.2),"correct":True}];m=metrics(rows,"R2");self.assertEqual((m["safe_count"],m["false_safe"],m["safe_precision"],m["correct_ocr_routed_hard"]),(2,1,.5,1))
 def test_cache_independence_and_human_gt_immutability(self):
  row={"features":self.features(),"correct":True,"human_gt":"ORIGINAL","cache":{"hit":False}};before=copy.deepcopy(row);metrics([row],"R2");self.assertEqual(before,row)
 def test_zero_model_call_surface(self):
  f=self.features();self.assertNotIn("vlm",f);self.assertNotIn("ollama",f);self.assertNotIn("model",f)
if __name__=="__main__":unittest.main()
