import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

from app.services.panel_conflict_resolver import semantic_hash

ROOT = Path(__file__).resolve().parents[2]
DAY12 = ROOT / "benchmarks/day12"
SCRIPT = ROOT / "scripts/panel_unseen_freeze_12_4.py"
SPEC = importlib.util.spec_from_file_location("panel_unseen_freeze_12_4", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


class PanelUnseenFreezeTests(unittest.TestCase):
    def payload(self, name):
        return json.loads((DAY12 / name).read_text())

    def test_locked_cohort_is_exact_exhaustive_complement(self):
        selection = self.payload("panel-unseen-selection-12.4.json")
        self.assertEqual(selection["selected_pages"], [3, 4, 5, 7, 18, 38])
        self.assertEqual(selection["excluded_pages"], [1, 2, 15, 17])
        self.assertEqual(set(selection["selected_pages"]) | set(selection["excluded_pages"]),
                         {1, 2, 3, 4, 5, 7, 15, 17, 18, 38})
        self.assertTrue(selection["correctness_blind"])

    def test_sources_match_frozen_identity_and_actual_bytes(self):
        selection = self.payload("panel-unseen-selection-12.4.json")
        for page in selection["pages"]:
            source = ROOT / page["source_path"]
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), page["source_sha256"])
            self.assertEqual(page["image_dimensions"], [900, 1280])

    def test_prediction_runner_has_no_database_or_gt_dependency(self):
        source = SCRIPT.read_text()
        self.assertNotIn("app.database", source)
        self.assertNotIn("PanelGroundTruthReview", source)
        self.assertNotIn("panel_ground_truth", source.lower())

    def test_all_semantic_hashes_and_freeze_links_reconcile(self):
        names = ["panel-unseen-selection-12.4.json", "panel-unseen-protocol-12.4.json",
                 "panel-unseen-raw-candidates-12.4.json", "panel-unseen-conflict-graph-12.4.json",
                 "panel-unseen-resolution-output-12.4.json", "panel-unseen-prediction-freeze-12.4.json"]
        payloads = {name: self.payload(name) for name in names}
        for payload in payloads.values():
            expected = payload.pop("semantic_sha256")
            self.assertEqual(semantic_hash(payload), expected)
        freeze = self.payload(names[-1])
        self.assertEqual(freeze["status"], "FROZEN_BEFORE_HUMAN_GT")
        self.assertFalse(freeze["human_gt_imported_or_queried"])
        self.assertTrue(freeze["extractor_two_run_identical"] and freeze["resolver_two_run_identical"])
        self.assertTrue(freeze["frozen_12_2_subset_identical"] and freeze["bbox_subset_and_identity"])

    def test_raw_candidates_exactly_match_frozen_12_2_subset(self):
        raw = self.payload("panel-unseen-raw-candidates-12.4.json")
        frozen = self.payload("panel-predictions-12.2.json")
        expected = [page for page in frozen["pages"] if page["page_order"] in RUNNER.PAGES]
        self.assertEqual(raw["pages"], expected)

    def test_output_geometry_is_candidate_subset_and_relations_are_stable(self):
        raw = self.payload("panel-unseen-raw-candidates-12.4.json")
        graph = self.payload("panel-unseen-conflict-graph-12.4.json")
        output = self.payload("panel-unseen-resolution-output-12.4.json")
        raw_by_page = {page["page_order"]: page for page in raw["pages"]}
        for graph_page, output_page in zip(graph["pages"], output["pages"], strict=True):
            source = {panel["panel_id"]: panel["bbox"] for panel in raw_by_page[output_page["page_order"]]["panels"]}
            emitted = {item["panel_id"]: item["bbox"] for item in output_page["candidates"]}
            self.assertEqual(source, emitted)
            self.assertFalse(output_page["geometry_mutated"])
            for relation in graph_page["spanning_relations"]:
                self.assertEqual(relation["member_ids"], sorted(relation["member_ids"]))

    def test_protocol_freezes_gates_and_zero_model_calls(self):
        protocol = self.payload("panel-unseen-protocol-12.4.json")
        self.assertEqual(protocol["gt_runtime_features"], [])
        self.assertFalse(protocol["human_gt_access"])
        self.assertFalse(protocol["reading_order_run"])
        self.assertEqual(protocol["model_calls"], {"ocr": 0, "vlm": 0, "ollama": 0})
        self.assertEqual(protocol["outcome_gates"]["A"]["precision"], 1.0)


if __name__ == "__main__":
    unittest.main()
