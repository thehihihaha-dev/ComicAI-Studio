import importlib.util
import json
import sys
import unittest
import copy
import hashlib
import tempfile
from pathlib import Path

from app.services.panel_aware_reading_order import assign_regions, order_regions_in_panel, panel_aware_order

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("panel_order_12_5", ROOT / "scripts/panel_aware_reading_order_12_5.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class PanelAwareReadingOrderFixTests(unittest.TestCase):
    def test_complete_synthetic_contract(self):
        result = RUNNER.synthetic_suite()
        names = {row["fixture"] for row in result["results"]}
        required = {"2x2_rtl", "horizontal_pair", "vertical_pair", "tall_right_stacked_left",
                    "tall_left_stacked_right", "spanning_top", "spanning_bottom", "offset_panels",
                    "bridge_non_transitivity", "ambiguous_overlap", "explicit_cycle", "empty_panel",
                    "clean_containment", "majority_intersection", "cross_border_ambiguity",
                    "unassigned_region", "full_hierarchy", "permutation_stable_ids"}
        self.assertEqual(names, required)
        self.assertTrue(result["all_pass"])

    def test_assignment_hierarchy_and_boundary(self):
        contained = assign_regions([{"id":"r","bbox":[1,1,2,2]}], [{"panel_id":"p","bbox":[0,0,3,3]}])
        self.assertEqual(contained["assignments"][0]["method"], "UNIQUE_CONTAINMENT")
        majority = assign_regions([{"id":"r","bbox":[1,-1,3,3]}], [{"panel_id":"p","bbox":[0,0,4,4]}])
        self.assertEqual(majority["assignments"][0]["method"], "UNIQUE_CENTER_STRICT_MAJORITY")
        exactly_half = assign_regions([{"id":"r","bbox":[1,-2,3,2]}], [{"panel_id":"p","bbox":[0,0,4,4]}])
        self.assertEqual(len(exactly_half["unassigned"]), 1)

    def test_frozen_overlap_threshold_is_inclusive_and_labeled(self):
        # Each 10px-tall region overlaps by exactly 5px.
        result = order_regions_in_panel([{"id":"left","bbox":[0,0,10,10]}, {"id":"right","bbox":[20,5,30,15]}])
        self.assertEqual(result["tiers"], [["right", "left"]])
        self.assertEqual(result["parameter_status"], "BENCHMARK_FITTED")

    def test_full_hierarchy_rtl(self):
        result = panel_aware_order(
            [{"id":"r1","bbox":[70,10,80,20]}, {"id":"r2","bbox":[70,50,80,60]},
             {"id":"l","bbox":[10,20,20,30]}],
            [{"panel_id":"left","bbox":[0,0,40,100]}, {"panel_id":"right","bbox":[60,0,100,100]}])
        self.assertEqual(result["sequence"], ["r1", "r2", "l"])

    def test_runtime_hash_mutations_fail_before_database_access(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory); paths = {}
            for name, source in RUNNER.RUNTIME.items():
                target = temporary / source.name; target.write_bytes(source.read_bytes()); paths[name] = target
            logical = json.loads(paths["logical_geometry"].read_text()); logical["pages"][0]["logical_regions"][0]["bbox"][0] += 1
            paths["logical_geometry"].write_text(json.dumps(logical))
            with self.assertRaisesRegex(RuntimeError, "frozen runtime input hash mismatch"):
                RUNNER.load_runtime_inputs(runtime_paths=paths)
            paths["logical_geometry"].write_bytes(RUNNER.RUNTIME["logical_geometry"].read_bytes())
            realistic = json.loads(paths["realistic_legacy"].read_text()); realistic["pages"][0]["candidates"][0]["bbox"][0] += 1
            paths["realistic_legacy"].write_text(json.dumps(realistic))
            with self.assertRaisesRegex(RuntimeError, "frozen runtime input hash mismatch"):
                RUNNER.load_runtime_inputs(runtime_paths=paths)

    def test_human_order_contamination_is_rejected_from_actual_temp_json(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = dict(RUNNER.RUNTIME); target = Path(directory) / "logical.json"
            value = json.loads(RUNNER.RUNTIME["logical_geometry"].read_text()); value["human_order"] = ["forbidden"]
            target.write_text(json.dumps(value)); paths["logical_geometry"] = target
            expected = {name: RUNNER.fh(path) for name, path in paths.items()}
            with self.assertRaisesRegex(RuntimeError, "Human-order contaminated"):
                RUNNER.load_runtime_inputs(expected=expected, runtime_paths=paths)

    def test_source_byte_and_dimension_mutations_fail_closed(self):
        audit = json.loads((ROOT / "benchmarks/day12/panel-order-input-gt-audit-12.5.json").read_text())
        page = copy.deepcopy(audit["runtime_phase"]["pages"][4])
        record = {"page_order":page["page_order"], "source_image_hash":page["source_hash"], "image_dimensions":page["image_dimensions"]}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "source.jpg"; target.write_bytes((ROOT / page["source_path"]).read_bytes() + b"x")
            with self.assertRaisesRegex(RuntimeError, "source fingerprint mismatch"):
                RUNNER.verify_source_record(record, target)
            from PIL import Image
            image_path = Path(directory) / "dimension.png"; Image.new("RGB", (10, 11)).save(image_path)
            dimension_record = {"page_order":999, "source_image_hash":hashlib.sha256(image_path.read_bytes()).hexdigest(), "image_dimensions":[10, 12]}
            with self.assertRaisesRegex(RuntimeError, "source dimension mismatch"):
                RUNNER.verify_source_record(dimension_record, image_path)

    def test_unexpected_page_set_fails_closed(self):
        logical = {page: {"source_hash":"x", "logical_regions":[]} for page in RUNNER.PAGES[:-1]}
        panels = {page: {"panels":[]} for page in RUNNER.PAGES}
        with self.assertRaisesRegex(RuntimeError, "unexpected candidate page set"):
            RUNNER.candidate("test", logical, panels, {})
        actual = json.loads(RUNNER.RUNTIME["logical_geometry"].read_text())
        actual["pages"] = [page for page in actual["pages"] if page["page_order"] != RUNNER.PAGES[-1]]
        mutated_logical = {page["page_order"]:page for page in actual["pages"] if page["page_order"] in RUNNER.PAGES}
        with self.assertRaisesRegex(RuntimeError, "unexpected benchmark page set"):
            RUNNER.validate_page_set(mutated_logical, panels, panels)

    def test_candidate_freeze_precedes_human_artifact_open(self):
        source = (ROOT / "scripts/panel_aware_reading_order_12_5.py").read_text()
        freeze = source.index('write(OUT["candidate-freeze"],freeze)')
        human = source.index('human_doc=json.loads(EVAL["human_order"].read_text())')
        baseline = source.index('base=json.loads(EVAL["baseline"].read_text())')
        self.assertLess(freeze, human)
        self.assertLess(freeze, baseline)

    def test_mock_human_order_cannot_mutate_candidate_bytes(self):
        logical_doc = json.loads(RUNNER.RUNTIME["logical_geometry"].read_text())
        logical = {p["page_order"]:p for p in logical_doc["pages"] if p["page_order"] in RUNNER.PAGES}
        audit = json.loads((ROOT / "benchmarks/day12/panel-order-input-gt-audit-12.5.json").read_text())
        oracle = {p["page_order"]:{"panels":p["oracle_panels"]} for p in audit["runtime_phase"]["pages"]}
        realistic = {p["page_order"]:{"panels":p["realistic_selected_panels"]} for p in audit["runtime_phase"]["pages"]}
        before = [RUNNER.candidate("ORACLE", logical, oracle, {"test":True}), RUNNER.candidate("REALISTIC", logical, realistic, {"test":True})]
        human = json.loads((ROOT / "benchmarks/day11/reader-order-control-11.16.json").read_text())
        for page in human["pages"]:
            page["human"] = list(reversed(page["human"]))
        after = [RUNNER.candidate("ORACLE", logical, oracle, {"test":True}), RUNNER.candidate("REALISTIC", logical, realistic, {"test":True})]
        self.assertEqual(RUNNER.rendered(before), RUNNER.rendered(after))
        self.assertEqual([x["semantic_sha256"] for x in before], [x["semantic_sha256"] for x in after])

    def test_two_run_artifact_byte_and_semantic_equality_is_persisted(self):
        summary = json.loads((ROOT / "benchmarks/day12/panel-order-summary-12.5.json").read_text())
        self.assertEqual(len(summary["two_independent_builds"]), 8)
        for result in summary["two_independent_builds"].values():
            self.assertTrue(result["byte_equal"])
            self.assertEqual(result["semantic_hash_a"], result["semantic_hash_b"])

    def test_internal_semantic_hashes_recompute(self):
        directory = ROOT / "benchmarks/day12"
        for name in ("input-gt-audit", "protocol", "synthetic", "oracle-candidates",
                     "realistic-candidates", "candidate-freeze", "evaluation", "summary"):
            value = json.loads((directory / f"panel-order-{name}-12.5.json").read_text())
            key = next(key for key in ("semantic_sha256", "protocol_sha256", "freeze_sha256") if key in value)
            expected = value.pop(key)
            self.assertEqual(RUNNER.digest(value), expected, name)

    def test_artifact_metrics_reconcile_from_page_records(self):
        summary = json.loads((ROOT / "benchmarks/day12/panel-order-summary-12.5.json").read_text())
        for track in ("oracle", "realistic"):
            result = summary[track]; pages = result["pages"]
            self.assertEqual(result["resolved_pages"], sum(row["resolved"] for row in pages))
            self.assertEqual(result["resolved_regions"][0], sum(len(row["prediction"]) for row in pages))
            self.assertEqual(result["exact_pages"][0], sum(row["exact"] for row in pages))
            self.assertEqual(result["exact_positions"][0], sum(row["exact_positions"] for row in pages))
            self.assertEqual(result["resolved_comparable_pairwise"][0], sum(row["resolved_correct_pairs"] for row in pages))
            self.assertEqual(result["resolved_comparable_pairwise"][1], sum(row["resolved_total_pairs"] for row in pages))
            self.assertEqual(result["confident_inversions"], sum(row["confident_inversions"] for row in pages))

    def test_track_sources_and_gt_runtime_features(self):
        oracle = json.loads((ROOT / "benchmarks/day12/panel-order-oracle-candidates-12.5.json").read_text())
        realistic = json.loads((ROOT / "benchmarks/day12/panel-order-realistic-candidates-12.5.json").read_text())
        self.assertEqual(oracle["gt_runtime_features"], [])
        self.assertEqual(realistic["gt_runtime_features"], [])
        self.assertIn("ORACLE_HUMAN_PANEL_GEOMETRY", oracle["track"])
        self.assertIn("NO_ORACLE_FALLBACK", realistic["track"])
        self.assertNotEqual([p["panel_nodes"] for p in oracle["pages"]], [p["panel_nodes"] for p in realistic["pages"]])


if __name__ == "__main__":
    unittest.main()
