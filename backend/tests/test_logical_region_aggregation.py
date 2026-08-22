import unittest
from app.models.reader_correctness_review import ReaderCorrectnessReview
from app.models.reader_logical_review import ReaderLogicalReview
from app.services.logical_region_aggregation import aggregate_fragments,flatten
class AggregationTests(unittest.TestCase):
 def setUp(self):self.lines=[{"region_id":1,"bbox":[10,10,50,20],"region_type":"detected_text"},{"region_id":2,"bbox":[12,23,52,33],"region_type":"detected_text"},{"region_id":3,"bbox":[100,10,140,20],"region_type":"detected_text"}]
 def test_fragments_merge_and_provenance_is_complete(self):
  result=aggregate_fragments(self.lines);self.assertEqual(2,len(result["logical_regions"]));ids=[x for r in result["logical_regions"] for x in r["source_fragment_ids"]];self.assertEqual([1,2,3],sorted(ids));self.assertEqual(len(ids),len(set(ids)))
 def test_stable_ids_and_hash(self):
  a=aggregate_fragments(self.lines);b=aggregate_fragments(list(reversed(self.lines)));self.assertEqual(a["logical_regions"],b["logical_regions"]);self.assertEqual(a["representation_hash"],b["representation_hash"])
 def test_bbox_change_invalidates_representation_cache(self):
  a=aggregate_fragments(self.lines);changed=[dict(x) for x in self.lines];changed[0]={**changed[0],"bbox":[10,10,49,20]};self.assertNotEqual(a["representation_hash"],aggregate_fragments(changed)["representation_hash"])
 def test_panel_containment_is_preserved(self):
  result=aggregate_fragments(self.lines,"PANEL_A");self.assertTrue(all(r["panel_id"]=="PANEL_A" for r in result["logical_regions"]))
 def test_existing_bubble_is_not_fragmented_or_merged(self):
  result=aggregate_fragments([{"region_id":8,"bbox":[0,0,80,80],"region_type":"speech_bubble"}]);self.assertEqual([8],result["logical_regions"][0]["source_fragment_ids"]);self.assertEqual("speech_bubble",result["logical_regions"][0]["region_type"])
 def test_flatten_is_hierarchical_derived_output(self):self.assertEqual(["a","b","c"],flatten(["P1","P2"],{"P1":["a","b"],"P2":["c"]}))
 def test_fragment_gt_and_logical_gt_use_separate_versioned_tables(self):
  self.assertNotEqual(ReaderCorrectnessReview.__tablename__,ReaderLogicalReview.__tablename__);self.assertIn("representation_hash",ReaderLogicalReview.__table__.columns)
if __name__=="__main__":unittest.main()
