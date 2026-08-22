import importlib.util,json,sys,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("sample_11_11",ROOT/"scripts/reader_correctness_sample_11_11.py")
module=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=module;SPEC.loader.exec_module(module)

class CorrectnessSampleTests(unittest.TestCase):
 def test_stratified_manifest_is_deterministic_and_blinded_for_ui(self):
  first=module.build();second=module.build();self.assertEqual(first,second);self.assertEqual(10,first["selected_pages"])
  self.assertEqual(40,first["dataset_pages"]);self.assertEqual(0,first["model_calls"]["vlm"]);self.assertEqual(0,first["model_calls"]["ollama"])
  self.assertEqual(len({p["source_hash"] for p in first["pages"]}),10)
  reasons=[r for p in first["pages"] for r in p["selection_reasons"]]
  for required in ("FLAGGED_NEEDS_HUMAN_REVIEW","UNUSUAL_GEOMETRY","LOW_CONFIDENCE_OCR","HIGH_CONFIDENCE_EASY","RANDOM_ORDINARY","REGRESSION_11_9_PAGE_3"):
   self.assertIn(required,reasons)
  self.assertGreaterEqual(reasons.count("RANDOM_ORDINARY"),2)
  self.assertTrue(all(p["regions"] for p in first["pages"]))
  self.assertEqual(first["total_ocr_regions"],sum(len(p["regions"]) for p in first["pages"]))
 def test_gate_d_source_identity_is_preserved(self):
  gate=json.loads((ROOT/"benchmarks/day11/reader-v2-scale-40p-11.10.json").read_text());manifest=module.build()
  known={p["asset_id"]:p["source_hash"] for p in gate["pages"]}
  self.assertTrue(all(known[p["asset_id"]]==p["source_hash"] for p in manifest["pages"]))
if __name__=="__main__":unittest.main()
