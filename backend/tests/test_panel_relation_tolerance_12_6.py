import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services.panel_aware_reading_order import assign_regions, order_panels, panel_aware_order

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("panel_relation_tolerance_12_6", ROOT / "scripts/panel_relation_tolerance_12_6.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class PanelRelationTolerance126Tests(unittest.TestCase):
    def test_exact_one_source_pixel_boundary_is_inclusive(self):
        panels = [{"panel_id": "top", "bbox": [0, 0, 100, 51]}, {"panel_id": "bottom", "bbox": [0, 50, 100, 100]}]
        result = order_panels(panels, (100, 100), 1)
        self.assertTrue(result["resolved"])
        self.assertEqual(result["order"], ["top", "bottom"])
        self.assertEqual(result["partitions"][0]["source_intrusion"], 1.0)

    def test_beyond_one_source_pixel_and_genuine_overlap_fail_closed(self):
        beyond = [{"panel_id": "top", "bbox": [0, 0, 100, 51.0001]}, {"panel_id": "bottom", "bbox": [0, 50, 100, 100]}]
        genuine = [{"panel_id": "a", "bbox": [0, 0, 70, 70]}, {"panel_id": "b", "bbox": [30, 30, 100, 100]}]
        self.assertFalse(order_panels(beyond, (100, 100), 1)["resolved"])
        self.assertFalse(order_panels(genuine, (100, 100), 1)["resolved"])

    def test_only_zero_or_frozen_one_pixel_configuration_is_accepted(self):
        panels = [{"panel_id": "a", "bbox": [0, 0, 10, 10]}]
        with self.assertRaisesRegex(ValueError, "zero or one"):
            order_panels(panels, (100, 100), 2)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            order_panels(panels, None, 1)

    def test_twenty_synthetic_fixture_groups_use_real_paths(self):
        result = RUNNER.synthetic_suite()
        self.assertEqual(result["fixture_group_count"], 20)
        self.assertTrue(result["all_pass"])
        self.assertTrue(all(row["path"] in {"order_panels", "topological_order", "assign_regions"} for row in result["results"]))

    def test_assignment_is_unchanged_by_relation_tolerance(self):
        panels = [{"panel_id": "a", "bbox": [0, 0, 50, 100]}, {"panel_id": "b", "bbox": [49.5, 0, 100, 100]}]
        regions = [{"id": "r", "bbox": [1, 1, 10, 10]}]
        zero = panel_aware_order(regions, panels, (100, 100), 0)
        one = panel_aware_order(regions, panels, (100, 100), 1)
        self.assertEqual(zero["assignment"], one["assignment"])
        self.assertEqual(zero["intra_panel"], one["intra_panel"])

    def test_control_artifact_actual_byte_mutation_fails(self):
        paths = {name: RUNNER.DAY12 / f"panel-order-{name}-12.5.json" for name in RUNNER.CONTROL_FILES}
        with tempfile.TemporaryDirectory() as directory:
            mutated = dict(paths)
            target = Path(directory) / "protocol.json"
            target.write_bytes(paths["protocol"].read_bytes() + b" ")
            mutated["protocol"] = target
            with self.assertRaisesRegex(RuntimeError, "control fingerprint mismatch"):
                RUNNER.verify_control(mutated)

    def test_pre_freeze_control_verification_never_deserializes_human_payload(self):
        with mock.patch.object(RUNNER.json, "loads", side_effect=AssertionError("JSON parse forbidden pre-freeze")) as parser:
            result = RUNNER.verify_control()
        parser.assert_not_called()
        self.assertFalse(result["human_derived_json_deserialized"])
        self.assertTrue(all(row["internal_hash_verified"] == "DEFERRED_UNTIL_GLOBAL_FREEZE" for row in result["artifacts"]))
        self.assertEqual(RUNNER.audit_provenance_dependency(result), [])
        self.assertNotIn("control_metrics", result)

    def test_transitive_provenance_closure_rejects_human_metrics(self):
        clean_audit = RUNNER.stamp({"schema_version": "test-audit", "gt_runtime_features": []})
        clean_control = RUNNER.stamp({"schema_version": "test-control", "artifacts": [], "gt_runtime_features": []})
        proto = RUNNER.protocol()
        contaminated = copy.deepcopy(clean_control)
        contaminated["nested"] = {"evaluation": {"resolved_pages": 2}}
        contaminated.pop("semantic_sha256"); contaminated["semantic_sha256"] = RUNNER.digest(contaminated)
        with self.assertRaisesRegex(RuntimeError, "Human-order-derived provenance dependency"):
            RUNNER.build_provenance(clean_audit, contaminated, proto)
        result = RUNNER.build_provenance(clean_audit, clean_control, proto)
        self.assertEqual(result["human_order_derived_provenance_dependencies"], [])
        self.assertTrue(all(not row["human_order_derived"] for row in result["dependency_closure"]))

    def test_human_metric_perturbation_cannot_change_real_candidate_path(self):
        audit = RUNNER.stamp({"schema_version": "test-audit", "gt_runtime_features": []})
        control = RUNNER.stamp({"schema_version": "test-control", "artifacts": [], "gt_runtime_features": []})
        proto = RUNNER.protocol()
        metrics = {"oracle": {"resolved_pages": 2, "confident_inversions": 0}}
        provenance_before = RUNNER.build_provenance(audit, control, proto)
        panels = [{"panel_id": "left", "bbox": [0, 0, 49.5, 100]}, {"panel_id": "right", "bbox": [50, 0, 100, 100]}]
        regions = [{"id": "l", "bbox": [10, 10, 20, 20]}, {"id": "r", "bbox": [70, 10, 80, 20]}]
        def build(track):
            return RUNNER.rendered({"track": track, "provenance": provenance_before,
                                    "candidate": panel_aware_order(regions, panels, (100, 100), 1)})
        before = {(run, track): build(track) for run in ("RUN_A", "RUN_B") for track in ("ORACLE", "REALISTIC")}
        metrics["oracle"]["resolved_pages"] = 999; metrics["oracle"]["confident_inversions"] = 999
        provenance_after = RUNNER.build_provenance(audit, control, proto)
        self.assertEqual(provenance_before, provenance_after)
        after = {(run, track): RUNNER.rendered({"track": track, "provenance": provenance_after,
                 "candidate": panel_aware_order(regions, panels, (100, 100), 1)})
                 for run in ("RUN_A", "RUN_B") for track in ("ORACLE", "REALISTIC")}
        self.assertEqual(before, after)

    def test_global_freeze_barrier_rejects_early_human_open_and_evaluation(self):
        barrier = RUNNER.FreezeBarrier()
        barrier.assert_candidate_generation_allowed("RUN_A"); barrier.freeze("RUN_A")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "human.json"; path.write_text('{"human": ["forbidden"]}')
            with self.assertRaisesRegex(RuntimeError, "Human-order access forbidden"):
                barrier.open_json(path, "HUMAN_READING_ORDER")
        with self.assertRaisesRegex(RuntimeError, "evaluation forbidden"):
            barrier.assert_evaluation_allowed()
        with self.assertRaisesRegex(RuntimeError, "requires RUN_A and RUN_B"):
            barrier.activate()

    def test_human_open_allowed_only_after_both_freezes_and_blocks_regeneration(self):
        barrier = RUNNER.FreezeBarrier()
        barrier.assert_candidate_generation_allowed("RUN_A"); barrier.freeze("RUN_A")
        barrier.assert_candidate_generation_allowed("RUN_B"); barrier.freeze("RUN_B"); barrier.activate()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "human.json"; path.write_text('{"human": ["allowed_post_freeze"]}')
            self.assertEqual(barrier.open_json(path, "HUMAN_READING_ORDER")["human"], ["allowed_post_freeze"])
        with self.assertRaisesRegex(RuntimeError, "candidate generation forbidden"):
            barrier.assert_candidate_generation_allowed("RUN_C")
        self.assertLess(barrier.events.index("RUN_B_FROZEN"), barrier.events.index("POST_FREEZE_OPEN:HUMAN_READING_ORDER"))

    def test_tolerance_configuration_mutation_and_second_candidate_fail(self):
        for mutation in ({"source_pixel_intrusion": 2}, {"tau_x": "2/W"}):
            value = RUNNER.protocol()
            value["formula"].update(mutation)
            value.pop("protocol_sha256")
            value["protocol_sha256"] = RUNNER.digest(value)
            with self.assertRaisesRegex(RuntimeError, "protocol mutation"):
                RUNNER.validate_protocol(value)
        value = RUNNER.protocol(); value["candidate_count"] = 2; value.pop("protocol_sha256"); value["protocol_sha256"] = RUNNER.digest(value)
        with self.assertRaisesRegex(RuntimeError, "multiple candidates"):
            RUNNER.validate_protocol(value)

    def test_human_order_perturbation_cannot_change_candidate_bytes(self):
        audit = json.loads(RUNNER.OUT["input-audit"].read_text())["runtime_phase"]
        human = json.loads(RUNNER.BASE.EVAL["human_order"].read_text())
        for track_name in ("oracle-candidates", "realistic-candidates"):
            artifact = json.loads(RUNNER.OUT[track_name].read_text())
            def rebuild():
                pages = []
                by_page = {p["page_order"]: p for p in audit["pages"]}
                for page in artifact["pages"]:
                    source = by_page[page["page_order"]]
                    regions = [{"id": row["id"], "bbox": row["bbox"]} for row in source["persisted_logical_regions"]]
                    pages.append(panel_aware_order(regions, page["panel_nodes"], tuple(page["source_dimensions"]), 1))
                return RUNNER.rendered(pages)
            before = rebuild()
            for page in human["pages"]: page["human"] = list(reversed(page["human"]))
            self.assertEqual(before, rebuild())

    def test_nine_artifacts_have_valid_hashes_and_determinism_evidence(self):
        docs = {name: json.loads(path.read_text()) for name, path in RUNNER.OUT.items()}
        self.assertEqual(set(docs), set(RUNNER.NAMES))
        self.assertTrue(all(RUNNER.verify_internal_hash(value) for value in docs.values()))
        comparisons = docs["summary"]["two_independent_builds"]
        self.assertEqual(len(comparisons), 9)
        self.assertTrue(all(row["byte_equal"] and row["semantic_hash_a"] == row["semantic_hash_b"] for row in comparisons.values()))

    def test_metrics_deltas_and_outcome_reconcile(self):
        value = json.loads(RUNNER.OUT["evaluation"].read_text())
        for track in ("oracle", "realistic"):
            candidate, control = value["candidate"][track], value["control"][track]
            expected = RUNNER.delta(candidate, control)
            self.assertEqual(value["delta"][track], expected)
            pages = candidate["pages"]
            self.assertEqual(candidate["resolved_pages"], sum(row["resolved"] for row in pages))
            self.assertEqual(candidate["resolved_regions"][0], sum(len(row["prediction"]) for row in pages))
            self.assertEqual(candidate["confident_inversions"], sum(row["confident_inversions"] for row in pages))
        self.assertEqual(value["outcome"], "B. TOLERANCE HELPS BUT REMAINS INCOMPLETE")
        self.assertEqual(value["hard_safety_failures"], [])

    def test_day11_inversion_audit_matches_frozen_contract(self):
        value = json.loads(RUNNER.OUT["evaluation"].read_text())["day11_inversion_audit"]
        self.assertEqual([(row["page_order"], row["status"]) for row in value["oracle"]],
                         [(15, "UNRESOLVED"), (15, "UNRESOLVED"), (17, "REPAIRED"), (38, "UNRESOLVED")])
        self.assertEqual([(row["page_order"], row["status"]) for row in value["realistic"]],
                         [(15, "UNRESOLVED"), (15, "UNRESOLVED"), (17, "REPAIRED"), (38, "REPAIRED")])

    def test_every_tolerance_enabled_partition_has_bounded_evidence(self):
        observed = []
        for track in ("oracle-candidates", "realistic-candidates"):
            value = json.loads(RUNNER.OUT[track].read_text())
            for page in value["pages"]:
                for partition in page["panel_order"]["partitions"]:
                    intrusion = partition["source_intrusion"]
                    self.assertLessEqual(intrusion, 1.0)
                    if intrusion > 0:
                        observed.append((track, page["page_order"], intrusion))
        self.assertEqual(observed, [("oracle-candidates", 5, 0.184), ("oracle-candidates", 38, 0.016)])


if __name__ == "__main__":
    unittest.main()
