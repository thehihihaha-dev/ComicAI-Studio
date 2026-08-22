import hashlib,json,unittest
from pathlib import Path
from app.services.reading_order_geometry_experiment import MANGA,WEBTOON,contains,tier_order
class ReadingOrderGeometryTests(unittest.TestCase):
 def item(self,id,x1,y1,x2,y2):return {"id":id,"bbox":[x1,y1,x2,y2]}
 def test_same_tier_right_to_left_manga(self):
  items=[self.item("L",0,0,40,30),self.item("R",60,2,100,32)];self.assertEqual(["R","L"],tier_order(items,"A_VERTICAL_OVERLAP",MANGA)["order"])
 def test_different_tier_top_to_bottom(self):
  items=[self.item("BOTTOM",50,60,90,90),self.item("TOP",10,0,40,25)];self.assertEqual(["TOP","BOTTOM"],tier_order(items,"C_HYBRID_TALL_PROTECTION")["order"])
 def test_tall_panel_does_not_join_two_rows(self):
  items=[self.item("TALL",80,0,120,120),self.item("TOP",20,0,60,30),self.item("BOTTOM",20,80,60,110)];result=tier_order(items,"C_HYBRID_TALL_PROTECTION");self.assertNotEqual(next(i for i,t in enumerate(result["tiers"]) if "TOP" in t),next(i for i,t in enumerate(result["tiers"]) if "BOTTOM" in t))
 def test_stable_tie_break_and_repeat(self):
  items=[self.item("B",10,0,20,10),self.item("A",10,0,20,10)];first=tier_order(items,"B_NORMALIZED_CENTER");self.assertEqual(first,tier_order(items,"B_NORMALIZED_CENTER"));self.assertEqual(["A","B"],first["order"])
 def test_nested_and_ambiguous(self):
  outer=self.item("O",0,0,100,100);inner=self.item("I",20,20,40,40);self.assertTrue(contains(outer,inner));result=tier_order([outer,inner,self.item("X",110,20,140,40)],"A_VERTICAL_OVERLAP");self.assertEqual(3,len(result["order"]))
 def test_source_type_policy(self):
  items=[self.item("L",0,0,40,30),self.item("R",60,0,100,30)];self.assertEqual(["R","L"],tier_order(items,"A_VERTICAL_OVERLAP",MANGA)["order"]);self.assertEqual(["L","R"],tier_order(items,"A_VERTICAL_OVERLAP",WEBTOON)["order"])
 def test_frozen_control_and_human_gt_immutability(self):
  day=Path(__file__).resolve().parents[2]/"benchmarks/day11";control=json.loads((day/"reader-order-control-11.16.json").read_text());self.assertEqual("PASS",control["comparability"]);self.assertEqual(control["frozen_sha256"],hashlib.sha256((day/"reader-reading-order-comparison-11.11.json").read_bytes()).hexdigest());self.assertEqual(8,control["reproduced_metrics"]["inversions"])
 def test_candidate_metrics_stability_and_page3(self):
  day=Path(__file__).resolve().parents[2]/"benchmarks/day11";summary=json.loads((day/"reader-order-summary-11.16.json").read_text());self.assertEqual("A_VERTICAL_OVERLAP",summary["best_candidate"]);self.assertEqual("A. GEOMETRY FIX PASS",summary["decision"]);self.assertEqual((7,43,120,4),(summary["best_metrics"]["exact_pages"]["correct"],summary["best_metrics"]["exact_positions"]["correct"],summary["best_metrics"]["pairwise"]["correct"],summary["best_metrics"]["inversions"]));self.assertEqual((3,7,0),(summary["best_metrics"]["pages_improved"],summary["best_metrics"]["pages_unchanged"],summary["best_metrics"]["pages_regressed"]));self.assertTrue(summary["page_3"]["candidates"]["A_VERTICAL_OVERLAP"]["prediction"]==summary["page_3"]["candidates"]["A_VERTICAL_OVERLAP"]["human"]);self.assertTrue(summary["stability"]["stable_selection"])
 def test_no_inference_and_group_gt_not_inferred(self):
  day=Path(__file__).resolve().parents[2]/"benchmarks/day11";summary=json.loads((day/"reader-order-summary-11.16.json").read_text());candidates=json.loads((day/"reader-order-candidates-11.16.json").read_text());self.assertEqual((0,0,0),(summary["safety"]["ocr_inference_calls"],summary["safety"]["vlm_calls"],summary["safety"]["ollama_calls"]));self.assertTrue(summary["safety"]["human_gt_unchanged"]);self.assertEqual([],candidates["gt_runtime_features"]);self.assertEqual("N/A",candidates["group_metrics"]["exact_group_structure"])
if __name__=="__main__":unittest.main()
