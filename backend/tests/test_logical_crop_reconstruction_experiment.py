import hashlib,json,unittest
from pathlib import Path

from app.services.logical_crop_reconstruction_experiment import (
    adaptive_box, cache_key, clip_box, geometry_audit, ordered_fragments, proportional_box, reconstruct_text,
)


class LogicalCropReconstructionTests(unittest.TestCase):
    def fragments(self):
        return [{"region_id":2,"bbox":[10,30,40,45],"text":"sau"},{"region_id":1,"bbox":[10,10,40,25],"text":"trước"}]

    def test_bbox_padding_and_clipping(self):
        self.assertEqual([0,0,15,15],clip_box([1,1,10,10],(15,15),5))
        self.assertEqual([8,8,42,42],proportional_box([10,10,40,40],(100,100),.05))
        self.assertEqual([7,7,43,43],adaptive_box([10,10,40,40],(100,100)))

    def test_fragment_order_and_reconstruction_are_deterministic(self):
        self.assertEqual([1,2],[row["region_id"] for row in ordered_fragments(self.fragments())])
        self.assertEqual("trước sau",reconstruct_text(self.fragments()))
        self.assertEqual(ordered_fragments(self.fragments()),ordered_fragments(self.fragments()))

    def test_merge_and_split_protection(self):
        audit=geometry_audit([10,10,40,100],[{"region_id":1,"bbox":[10,10,40,20]},{"region_id":2,"bbox":[10,80,40,100]}])
        self.assertIn("AMBIGUOUS_FRAGMENT_OWNERSHIP",audit["tags"]);self.assertTrue(audit["structural_review"])
        clean=geometry_audit([10,10,40,45],self.fragments());self.assertNotIn("AMBIGUOUS_FRAGMENT_OWNERSHIP",clean["tags"])

    def test_overlap_duplicate_requires_structural_review(self):
        fragments=[{"region_id":1,"bbox":[1,1,20,20]},{"region_id":2,"bbox":[1,1,20,20]}]
        audit=geometry_audit([1,1,20,20],fragments);self.assertIn("DUPLICATED_FRAGMENTS",audit["tags"]);self.assertTrue(audit["structural_review"])

    def test_cache_key_is_input_sensitive(self):
        first=cache_key("hash",[1,2,3,4],[[1,2,3,4]],"adaptive","1.7.2")
        self.assertEqual(first,cache_key("hash",[1,2,3,4],[[1,2,3,4]],"adaptive","1.7.2"));self.assertNotEqual(first,cache_key("hash",[1,2,3,5],[[1,2,3,4]],"adaptive","1.7.2"))

    def test_frozen_replay_and_human_gt_immutability(self):
        day=Path(__file__).resolve().parents[2]/"benchmarks/day11";replay=json.loads((day/"reader-structural-replay-11.14.json").read_text())
        self.assertEqual(71,replay["verified"]);self.assertEqual(10,replay["unreadable"]);self.assertTrue(replay["source_hashes_valid"])
        self.assertEqual(replay["frozen_human_gt_sha256"],hashlib.sha256((day/"reader-router-validation-human-gt-11.13.json").read_bytes()).hexdigest())
        self.assertEqual(replay["frozen_manifest_sha256"],hashlib.sha256((day/"reader-router-validation-manifest-11.13.json").read_bytes()).hexdigest())

    def test_artifact_metrics_regressions_and_zero_models(self):
        day=Path(__file__).resolve().parents[2]/"benchmarks/day11";summary=json.loads((day/"reader-structural-summary-11.14.json").read_text());comparison=json.loads((day/"reader-structural-comparison-11.14.json").read_text());candidates=json.loads((day/"reader-structural-candidates-11.14.json").read_text())
        self.assertEqual("adaptive_bounded",summary["best_candidate"]);self.assertEqual("B. PARTIAL STRUCTURAL IMPROVEMENT",summary["decision"])
        self.assertEqual((8,8),(summary["control"]["exact"],summary["best_metrics"]["exact"]));self.assertEqual(1,summary["structural_47"]["repaired"])
        self.assertEqual(1,comparison["regression_safety"]["correct_to_wrong"]);self.assertEqual(5,comparison["regression_safety"]["large_cer_regressions"])
        self.assertEqual("FALSE_SAFE_TEXT_ERROR_REMAINS",comparison["false_safe_replay"]["11.13"]["structural_fix_result"])
        self.assertEqual("COMPLETED",candidates["status"]);self.assertIn("selection_features",candidates)
        self.assertEqual((0,0),(summary["safety"]["vlm_calls"],summary["safety"]["ollama_calls"]));self.assertTrue(summary["safety"]["human_gt_unchanged"]);self.assertTrue(summary["safety"]["authoritative_state_unchanged"])


if __name__=="__main__":unittest.main()
