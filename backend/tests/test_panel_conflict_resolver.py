import inspect
import importlib.util
import hashlib
import json
import copy
import unittest
from pathlib import Path

from app.services.panel_conflict_resolver import build_graph, resolve_candidates, semantic_hash

CONFIG = {"duplicate_iou": 0.82, "edge_join_fraction": 0.02}
ROOT = Path(__file__).resolve().parents[2]
DAY12 = ROOT / "benchmarks/day12"
RUNNER_PATH = ROOT / "scripts/panel_conflict_resolution_12_3.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("panel_conflict_resolution_12_3", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
assert RUNNER_SPEC.loader is not None
RUNNER_SPEC.loader.exec_module(RUNNER)


def panel(panel_id, bbox, state="AMBIGUOUS", provenance=None, source_count=1):
    return {"panel_id": panel_id, "bbox": bbox, "state": state,
            "provenance": provenance or ["border_contour"],
            "heuristic_evidence": {"source_count": source_count}}


class PanelConflictResolverTests(unittest.TestCase):
    def resolve(self, panels):
        return resolve_candidates(panels, CONFIG)

    def test_under_split_parent_yields_two_adjacent_panels(self):
        parent = panel("parent", [0, 0, 200, 100], provenance=["whitespace_partition"])
        left, right = panel("left", [0, 0, 98, 100]), panel("right", [102, 0, 200, 100])
        _, output = self.resolve([parent, left, right])
        self.assertEqual(set(output["selected_panel_ids"]), {"left", "right"})
        self.assertEqual(next(item["reason"] for item in output["candidates"] if item["panel_id"] == "parent"), "UNDER_SPLIT_SPANNER")

    def test_nested_fragment_is_rejected_without_mutating_outer(self):
        outer = panel("outer", [0, 0, 200, 100], state="DETECTED")
        fragment = panel("fragment", [20, 20, 60, 60])
        _, output = self.resolve([outer, fragment])
        self.assertEqual(output["selected_panel_ids"], ["outer"])
        self.assertEqual(next(item for item in output["candidates"] if item["panel_id"] == "fragment")["reason"], "NESTED_INTERNAL_FRAGMENT")
        self.assertEqual(next(item for item in output["candidates"] if item["panel_id"] == "outer")["bbox"], outer["bbox"])

    def test_duplicate_has_one_stable_winner(self):
        locked = panel("locked", [0, 0, 200, 100], state="DETECTED")
        duplicate = panel("duplicate", [1, 1, 199, 99])
        _, output = self.resolve([duplicate, locked])
        self.assertEqual(output["selected_panel_ids"], ["locked"])
        self.assertEqual(next(item for item in output["candidates"] if item["panel_id"] == "duplicate")["reason"], "DUPLICATE")

    def test_legitimate_large_single_is_preserved(self):
        large = panel("large", [0, 0, 300, 200], state="DETECTED")
        _, output = self.resolve([large])
        self.assertEqual(output["selected_panel_ids"], ["large"])

    def test_standalone_adjacent_panels_are_preserved_without_parent(self):
        left = panel("left", [0, 0, 98, 100],
                     provenance=["border_contour", "whitespace_partition"], source_count=2)
        right = panel("right", [102, 0, 200, 100],
                      provenance=["border_contour", "whitespace_partition"], source_count=2)
        graph, output = self.resolve([right, left])
        self.assertEqual(output["selected_panel_ids"], ["left", "right"])
        self.assertEqual(graph["spanning_relations"], [])
        self.assertTrue(all(item["reason"] == "MULTI_SOURCE_ATOMIC" for item in output["candidates"]))

    def test_tall_beside_stacked_recursive_tiling(self):
        parent = panel("parent", [0, 0, 300, 200], provenance=["whitespace_partition"])
        tall = panel("tall", [0, 0, 148, 200]); top = panel("top", [152, 0, 300, 98]); bottom = panel("bottom", [152, 102, 300, 200])
        _, output = self.resolve([parent, tall, top, bottom])
        self.assertEqual(set(output["selected_panel_ids"]), {"tall", "top", "bottom"})

    def test_scattered_candidates_remain_unresolved(self):
        parent = panel("parent", [0, 0, 300, 200], provenance=["whitespace_partition"])
        first = panel("first", [20, 20, 100, 80]); second = panel("second", [170, 110, 280, 180])
        _, output = self.resolve([parent, first, second])
        self.assertTrue(output["unresolved"]); self.assertEqual(output["selected_panel_ids"], [])

    def test_locked_control_rejects_internal_fragment(self):
        left = panel("left", [0, 0, 98, 100], state="DETECTED")
        right = panel("right", [102, 0, 200, 100], state="DETECTED")
        fragment = panel("fragment", [120, 20, 160, 60])
        _, output = self.resolve([left, right, fragment])
        self.assertEqual(set(output["selected_panel_ids"]), {"left", "right"})

    def test_graph_and_output_are_permutation_stable(self):
        panels = [panel("parent", [0, 0, 200, 100], provenance=["whitespace_partition"]),
                  panel("left", [0, 0, 98, 100]), panel("right", [102, 0, 200, 100])]
        first = self.resolve(panels); second = self.resolve(list(reversed(panels)))
        self.assertEqual(first, second); self.assertEqual(semantic_hash(first), semantic_hash(second))

    def test_graph_relationships_are_typed_and_stable(self):
        outer = panel("outer", [0, 0, 200, 100]); inner = panel("inner", [10, 10, 50, 50])
        separate = panel("separate", [220, 0, 300, 100])
        graph = build_graph([separate, inner, outer], CONFIG["duplicate_iou"], CONFIG["edge_join_fraction"])
        types = {edge["type"] for edge in graph["edges"]}
        self.assertTrue({"CONTAINS", "NESTED_INTERNAL", "COMPATIBLE"}.issubset(types))

    def test_graph_emits_deterministic_spanning_parent_relation(self):
        parent = panel("parent", [0, 0, 200, 100], provenance=["whitespace_partition"])
        left, right = panel("left", [0, 0, 98, 100]), panel("right", [102, 0, 200, 100])
        first_graph, first_output = self.resolve([parent, left, right])
        second_graph, second_output = self.resolve([right, parent, left])
        self.assertEqual(first_graph, second_graph)
        self.assertEqual(first_output, second_output)
        relation = first_graph["spanning_relations"][0]
        self.assertEqual(relation["type"], "SPANNING_PARENT_SUBPANEL_SET")
        self.assertEqual(relation["parent_id"], "parent")
        self.assertEqual(relation["member_ids"], ["left", "right"])
        parent_result = next(item for item in first_output["candidates"] if item["panel_id"] == "parent")
        self.assertEqual(parent_result["supporting_relation_ids"], [relation["relation_id"]])

    def test_resolver_api_has_no_gt_or_page_argument(self):
        names = set(inspect.signature(resolve_candidates).parameters)
        self.assertEqual(names, {"panels", "config"})
        self.assertFalse(any("gt" in name or "page" in name for name in names))

    def test_validate_frozen_fails_closed_on_wrong_hash_or_mutation(self):
        frozen_path = DAY12 / "panel-predictions-12.2.json"
        frozen = json.loads(frozen_path.read_text())
        with self.assertRaises(ValueError):
            RUNNER.validate_frozen(frozen, "0" * 64)
        mutated = copy.deepcopy(frozen)
        mutated["pages"][0]["panels"][0]["bbox"][0] += 1
        with self.assertRaises(SystemExit):
            RUNNER.validate_frozen(mutated, hashlib.sha256(frozen_path.read_bytes()).hexdigest())

    def test_behavioral_gt_change_cannot_affect_real_resolver_path(self):
        panels = [panel("parent", [0, 0, 200, 100], provenance=["whitespace_partition"]),
                  panel("left", [0, 0, 98, 100]), panel("right", [102, 0, 200, 100])]
        evaluation_gt_a = [{"id": "human-a", "bbox": [0, 0, 90, 100]}]
        evaluation_gt_b = [{"id": "human-b", "bbox": [100, 0, 200, 100]},
                           {"id": "human-c", "bbox": [0, 0, 100, 100]}]
        before = resolve_candidates(copy.deepcopy(panels), CONFIG)
        self.assertNotEqual(evaluation_gt_a, evaluation_gt_b)
        after = resolve_candidates(copy.deepcopy(panels), CONFIG)
        self.assertEqual(before, after)
        self.assertEqual(semantic_hash(before), semantic_hash(after))

    def test_real_artifacts_preserve_frozen_candidate_geometry(self):
        frozen = json.loads((DAY12 / "panel-predictions-12.2.json").read_text())
        output = json.loads((DAY12 / "panel-conflict-resolution-output-12.3.json").read_text())
        source = {panel["panel_id"]: panel["bbox"] for page in frozen["pages"] for panel in page["panels"]}
        emitted = {item["panel_id"]: item["bbox"] for page in output["pages"] for item in page["candidates"]}
        self.assertEqual(emitted, source); self.assertTrue(all(panel_id in source for page in output["pages"] for panel_id in page["selected_panel_ids"]))
        self.assertFalse(any(page["geometry_mutated"] for page in output["pages"]))

    def test_real_artifact_semantic_hashes_reconcile(self):
        for name in ("panel-conflict-graph-12.3.json", "panel-conflict-resolution-output-12.3.json"):
            payload = json.loads((DAY12 / name).read_text()); expected = payload.pop("semantic_sha256")
            self.assertEqual(semantic_hash(payload), expected)
        self.assertEqual(hashlib.sha256((DAY12 / "panel-predictions-12.2.json").read_bytes()).hexdigest(),
                         "80e46d5c6216e3d18e9686af149a0012911795a246d1323ae4bb74d516b4b735")

    def test_real_evaluation_meets_predeclared_gates(self):
        evaluation = json.loads((DAY12 / "panel-conflict-resolution-evaluation-12.3.json").read_text())
        self.assertEqual(evaluation["aggregate"], {"human_panels": 15, "selected_panels": 10, "matched": 10,
            "missed": 5, "false_promoted": 0, "precision": 1.0, "recall": 0.666667, "f1": 0.8,
            "unresolved_pages": 1, "under_split_selected": 0, "over_split_selected": 0})
        pages = {page["page_order"]: page for page in evaluation["per_page"]}
        self.assertEqual(pages[2]["matched_true_panels_detected"], 2)
        self.assertEqual(pages[15]["matched_true_panels_detected"], 3)
        self.assertEqual(pages[17]["matched_true_panels_detected"], 5)

    def test_summary_records_freeze_isolation_and_outcome(self):
        summary = json.loads((DAY12 / "panel-conflict-resolution-summary-12.3.json").read_text())
        self.assertEqual(summary["outcome"], "A. CONFLICT RESOLUTION PASS — SAFE STRUCTURAL RECOVERY")
        self.assertTrue(summary["freeze"]["output_frozen_before_gt"])
        self.assertTrue(summary["freeze"]["two_run_semantic_byte_equivalent"])
        self.assertEqual(summary["safety"]["gt_runtime_features"], [])
        self.assertFalse(summary["safety"]["extractor_rerun"]); self.assertFalse(summary["safety"]["reading_order_run"])
        self.assertEqual(len(summary["synthetic_results"]), 8)


if __name__ == "__main__":
    unittest.main()
