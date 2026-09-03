#!/usr/bin/env python3
"""Finite Checkpoint 12.6 relation-tolerance experiment.

Human Reading Order is opened only by ``build_post_freeze`` after both
independent candidate freezes have been materialized in memory.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.panel_aware_reading_order import assign_regions, order_panels, panel_aware_order, topological_order
from app.services.resource_safety import ResourceThresholds, sample_resources

SPEC = importlib.util.spec_from_file_location("panel_order_control_12_5", ROOT / "scripts/panel_aware_reading_order_12_5.py")
BASE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)

DAY12 = ROOT / "benchmarks/day12"
NAMES = ("input-audit", "control-reference", "protocol", "synthetic", "oracle-candidates",
         "realistic-candidates", "candidate-freeze", "evaluation", "summary")
OUT = {name: DAY12 / f"panel-relation-tolerance-{name}-12.6.json" for name in NAMES}
CONTROL_FILES = {
    "candidate-freeze": "25b9a26db8f03a7afd07e6136c3b57fbacc65d84aae9c1406cda618f9a251db4",
    "evaluation": "4c804595981b89bfc7661d8a87f307b76fa19f756edd64e1e951c15b769ac376",
    "input-gt-audit": "591dbe0654689f673f98e6959b5e414c529e5daab382017c434cc49f19c496f5",
    "oracle-candidates": "a7ed2e1747ff13f7cde57dbd149cd4b9d5ab12203c0ce48525336833bd4cf2fd",
    "protocol": "0f72c9ecad51a779bf22059b586527b2ab71abd7341304782880331f186450c7",
    "realistic-candidates": "dc9d60f0007ecd19154c57509b917c3c28675a0ff69709f07518870e4c4e0e58",
    "summary": "41e559d621445f7c8c44a1a282e364784d27bd283b3de9de32ebfbfa8b695db1",
    "synthetic": "b50ae7ec226a34455a0bcc6964a5a2705a384c3201c4b8f83237d2ea5aa01f40",
}
TOLERANCE_LABEL = "EXPERIMENT_PREDECLARED_SOURCE_PIXEL_QUANTIZATION_V1"
HUMAN_DERIVED_CONTROL = {"input-gt-audit", "evaluation", "summary"}
FORBIDDEN_PROVENANCE_KEYS = {
    "human", "human_order", "human_sequence", "ordered_region_ids", "inversions",
    "confident_inversions", "resolved_pages", "resolved_regions", "resolved_pairs",
    "resolved_comparable_pairwise", "population_pair_coverage", "correct_positions",
    "exact_pages", "exact_positions", "correctness", "evaluation_outcome", "outcome",
    "expected_post_freeze_metric_region_count",
}


@dataclass
class FreezeBarrier:
    frozen_runs: set[str] = field(default_factory=set)
    active: bool = False
    human_order_opened: bool = False
    events: list[str] = field(default_factory=list)

    def assert_candidate_generation_allowed(self, run_name: str) -> None:
        if self.human_order_opened:
            raise RuntimeError("candidate generation forbidden after Human-order access")
        if run_name in self.frozen_runs:
            raise RuntimeError(f"candidate run already frozen: {run_name}")
        self.events.append(f"{run_name}_CANDIDATE_GENERATION_ALLOWED")

    def freeze(self, run_name: str) -> None:
        if self.human_order_opened:
            raise RuntimeError("candidate freeze forbidden after Human-order access")
        self.frozen_runs.add(run_name)
        self.events.append(f"{run_name}_FROZEN")

    def activate(self) -> None:
        if self.frozen_runs != {"RUN_A", "RUN_B"}:
            raise RuntimeError("global freeze barrier requires RUN_A and RUN_B frozen")
        self.active = True
        self.events.append("GLOBAL_FREEZE_BARRIER_ACTIVE")

    def open_json(self, path: Path, label: str) -> Any:
        if not self.active or self.frozen_runs != {"RUN_A", "RUN_B"}:
            raise RuntimeError("Human-order access forbidden before global freeze barrier")
        self.human_order_opened = True
        self.events.append(f"POST_FREEZE_OPEN:{label}")
        return json.loads(path.read_text())

    def assert_evaluation_allowed(self) -> None:
        if not self.active or self.frozen_runs != {"RUN_A", "RUN_B"}:
            raise RuntimeError("evaluation forbidden before global freeze barrier")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def rendered(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(value: dict[str, Any], key: str = "semantic_sha256") -> dict[str, Any]:
    value[key] = digest(value)
    return value


def verify_internal_hash(value: dict[str, Any]) -> bool:
    key = next((name for name in ("semantic_sha256", "protocol_sha256", "freeze_sha256") if name in value), None)
    if not key:
        return False
    expected = value[key]
    material = dict(value)
    material.pop(key)
    return expected == digest(material)


def verify_control(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {name: DAY12 / f"panel-order-{name}-12.5.json" for name in CONTROL_FILES}
    if set(paths) != set(CONTROL_FILES):
        raise RuntimeError("12.5 control artifact set mismatch")
    rows = []
    for name in sorted(paths):
        path = paths[name]
        actual = file_hash(path)
        if actual != CONTROL_FILES[name]:
            raise RuntimeError(f"12.5 control fingerprint mismatch: {name}")
        rows.append({"artifact": name, "path": str(path.relative_to(ROOT)), "file_sha256": actual,
                     "pre_freeze_verification": "RAW_BYTES_SHA256_ONLY",
                     "internal_hash_verified": "DEFERRED_UNTIL_GLOBAL_FREEZE"})
    return stamp({"schema_version": "panel-relation-tolerance-control-reference.v1", "checkpoint": "12.6",
                  "status": "FROZEN_12_5_ZERO_TOLERANCE_CONTROL_VERIFIED", "artifacts": rows,
                  "human_reading_order_parsed": False, "human_derived_json_deserialized": False,
                  "human_order_derived_provenance_dependencies": [],
                  "gt_runtime_features": []})


def audit_provenance_dependency(value: Any, path: str = "root") -> list[str]:
    violations = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_PROVENANCE_KEYS:
                violations.append(child_path)
            violations.extend(audit_provenance_dependency(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(audit_provenance_dependency(child, f"{path}[{index}]"))
    return violations


def build_provenance(audit: dict[str, Any], control: dict[str, Any], proto: dict[str, Any]) -> dict[str, Any]:
    dependencies = {"pre_freeze_input_audit": audit, "opaque_approved_raw_byte_control_integrity": control,
                    "frozen_tolerance_protocol": proto}
    violations = audit_provenance_dependency(dependencies)
    if violations:
        raise RuntimeError("Human-order-derived provenance dependency: " + ", ".join(violations))
    return {"input_audit_semantic_sha256": audit["semantic_sha256"],
            "control_reference_semantic_sha256": control["semantic_sha256"],
            "protocol_sha256": proto["protocol_sha256"],
            "dependency_closure": [{"name": name, "semantic_sha256":
                                    value.get("semantic_sha256", value.get("protocol_sha256")),
                                    "human_order_derived": False} for name, value in dependencies.items()],
            "human_order_derived_provenance_dependencies": [], "gt_runtime_features": []}


def load_post_freeze_evidence(barrier: FreezeBarrier) -> dict[str, Any]:
    barrier.assert_evaluation_allowed()
    control_docs = {}
    for name in sorted(CONTROL_FILES):
        path = DAY12 / f"panel-order-{name}-12.5.json"
        value = barrier.open_json(path, f"CONTROL_12_5:{name}")
        if not verify_internal_hash(value):
            raise RuntimeError(f"12.5 post-freeze internal hash mismatch: {name}")
        control_docs[name] = value
    return {"human_doc": barrier.open_json(BASE.EVAL["human_order"], "HUMAN_READING_ORDER"),
            "baseline": barrier.open_json(BASE.EVAL["baseline"], "DAY11_BASELINE"),
            "control_docs": control_docs,
            "post_freeze_control_internal_hashes_verified": sorted(control_docs)}


def protocol() -> dict[str, Any]:
    return stamp({"schema_version": "panel-relation-tolerance-protocol.v1", "checkpoint": "12.6",
                  "status": "FROZEN_BEFORE_HUMAN_READING_ORDER_ACCESS", "label": TOLERANCE_LABEL,
                  "candidate_count": 1, "formula": {"normalized_bbox": ["x1/W", "y1/H", "x2/W", "y2/H"],
                  "tau_x": "1/W", "tau_y": "1/H", "source_pixel_intrusion": 1,
                  "comparison": "intrusion_axis <= tau_axis", "boundary_equality": "ACCEPTED",
                  "numeric_representation": "EXACT_DECIMAL_FROM_SERIALIZED_COORDINATES"},
                  "scope": "RECURSIVE_GUILLOTINE_CLEAN_SEPARATION_ONLY", "bbox_expansion": False,
                  "assignment": ["UNIQUE_CONTAINMENT", "UNIQUE_CENTER_AND_STRICT_AREA_MAJORITY_GT_0.50", "AMBIGUOUS", "UNASSIGNED"],
                  "intra_panel_rule": "ANY_PEER_NORMALIZED_VERTICAL_OVERLAP_GTE_0.50",
                  "gt_runtime_features": []}, "protocol_sha256")


def validate_protocol(value: dict[str, Any]) -> None:
    if not verify_internal_hash(value) or value.get("label") != TOLERANCE_LABEL:
        raise RuntimeError("tolerance protocol fingerprint mismatch")
    formula = value.get("formula", {})
    if value.get("candidate_count") != 1 or formula.get("source_pixel_intrusion") != 1 or formula.get("tau_x") != "1/W" or formula.get("tau_y") != "1/H":
        raise RuntimeError("tolerance protocol mutation or multiple candidates")


def input_audit(inputs: dict[str, Any]) -> dict[str, Any]:
    runtime = copy.deepcopy(BASE.runtime_audit(inputs))
    runtime.pop("expected_post_freeze_metric_region_count", None)
    runtime.pop("semantic_sha256", None)
    runtime["semantic_sha256"] = digest(runtime)
    return stamp({"schema_version": "panel-relation-tolerance-input-audit.v1", "checkpoint": "12.6",
                  "status": "PRE_CANDIDATE_NON_ORDER_INPUTS_VERIFIED", "runtime_phase": runtime,
                  "human_reading_order_loaded": False, "gt_runtime_features": []})


def candidate(track: str, inputs: dict[str, Any], panel_pages: dict[int, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    if sorted(panel_pages) != BASE.PAGES:
        raise RuntimeError("unexpected candidate page set")
    dimensions = {row["page_order"]: tuple(row["image_dimensions"]) for row in inputs["records"]}
    pages = []
    for page in BASE.PAGES:
        regions = [{"id": row["logical_region_id"], "bbox": row["bbox"]} for row in inputs["logical"][page]["logical_regions"]]
        panels = [{"panel_id": BASE.gid(row["bbox"]), "bbox": row["bbox"]} for row in panel_pages[page]["panels"]]
        result = panel_aware_order(regions, panels, dimensions[page], 1)
        pages.append({"page_order": page, "source_hash": inputs["logical"][page]["source_hash"], "source_dimensions": list(dimensions[page]),
                      "panel_source": track, "panel_nodes": panels,
                      "upstream_structure_status": "UNRESOLVED" if panel_pages[page].get("source_unresolved") else "RESOLVED", **result})
    return stamp({"schema_version": "panel-relation-tolerance-candidates.v1", "checkpoint": "12.6", "track": track,
                  "tolerance_label": TOLERANCE_LABEL, "provenance": provenance, "pages": pages,
                  "gt_runtime_features": [], "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0}})


def synthetic_suite() -> dict[str, Any]:
    def panels(boxes: list[list[float]]) -> list[dict[str, Any]]:
        return [{"panel_id": f"p{i}", "bbox": box} for i, box in enumerate(boxes)]
    cases: list[tuple[str, list[list[float]], Any]] = [
        ("clean_horizontal", [[0, 0, 40, 100], [60, 0, 100, 100]], ["p1", "p0"]),
        ("clean_vertical", [[0, 0, 100, 40], [0, 60, 100, 100]], ["p0", "p1"]),
        ("horizontal_below_tolerance", [[0, 0, 50.4, 100], [50, 0, 100, 100]], ["p1", "p0"]),
        ("vertical_below_tolerance", [[0, 0, 100, 50.4], [0, 50, 100, 100]], ["p0", "p1"]),
        ("boundary_equality", [[0, 0, 100, 51], [0, 50, 100, 100]], ["p0", "p1"]),
        ("beyond_tolerance", [[0, 0, 100, 51.0001], [0, 50, 100, 100]], "UNRESOLVED"),
        ("manga_rtl", [[0, 0, 40, 100], [60, 0, 100, 100]], ["p1", "p0"]),
        ("upper_lower", [[0, 0, 100, 40], [0, 60, 100, 100]], ["p0", "p1"]),
        ("2x2_rtl", [[0, 0, 40, 40], [60, 0, 100, 40], [0, 60, 40, 100], [60, 60, 100, 100]], ["p1", "p0", "p3", "p2"]),
        ("tall_right_stacked_left", [[60, 0, 100, 100], [0, 0, 40, 40], [0, 60, 40, 100]], ["p0", "p1", "p2"]),
        ("tall_left_stacked_right", [[0, 0, 40, 100], [60, 0, 100, 40], [60, 60, 100, 100]], ["p1", "p2", "p0"]),
        ("offset_panels", [[0, 0, 42, 35], [58, 5, 100, 40], [5, 60, 45, 100], [55, 55, 95, 95]], ["p1", "p0", "p3", "p2"]),
        ("spanning_top_bottom", [[0, 0, 100, 30], [0, 40, 40, 70], [60, 40, 100, 70], [0, 80, 100, 100]], ["p0", "p2", "p1", "p3"]),
        ("genuine_overlap", [[0, 0, 70, 70], [30, 30, 100, 100]], "UNRESOLVED"),
        ("ambiguous_relation", [[0, 0, 60, 60], [40, 40, 100, 100]], "UNRESOLVED"),
        ("bridge_non_transitivity", [[0, 0, 30, 30], [40, 0, 70, 70], [80, 40, 110, 70]], ["p2", "p1", "p0"]),
        ("outside_valid_partition", [[0, 0, 70, 40], [30, 30, 100, 70], [0, 60, 70, 100]], "UNRESOLVED"),
    ]
    rows = []
    for name, boxes, expected in cases:
        trace = order_panels(panels(boxes), (100, 100), 1)
        observed = trace["order"] if trace["resolved"] else "UNRESOLVED"
        rows.append({"fixture": name, "path": "order_panels", "expected": expected, "observed": observed,
                     "pass": observed == expected, "trace": trace})
    cycle = topological_order(["a", "b"], [{"before": "a", "after": "b"}, {"before": "b", "after": "a"}])
    rows.append({"fixture": "cycle_conflict", "path": "topological_order", "expected": "UNRESOLVED",
                 "observed": "UNRESOLVED" if not cycle["resolved"] else cycle["order"], "pass": not cycle["resolved"], "trace": cycle})
    perm = panels([[0, 0, 40, 100], [60, 0, 100, 100]])
    a, b = order_panels(perm, (100, 100), 1), order_panels(list(reversed(perm)), (100, 100), 1)
    rows.append({"fixture": "permutation_determinism", "path": "order_panels", "expected": a["order"], "observed": b["order"],
                 "pass": rendered(a) == rendered(b), "trace": a})
    assignment_panels = panels([[0, 0, 40, 100], [60, 0, 100, 100]])
    regions = [{"id": "contained", "bbox": [5, 5, 10, 10]}, {"id": "majority", "bbox": [35, 10, 42, 20]},
               {"id": "tie", "bbox": [45, 10, 55, 20]}, {"id": "outside", "bbox": [110, 0, 120, 10]}]
    assignment = assign_regions(regions, assignment_panels)
    passed = ([r["region_id"] for r in assignment["assignments"]] == ["contained", "majority"] and
              [r["region_id"] for r in assignment["unassigned"]] == ["tie", "outside"])
    rows.append({"fixture": "assignment_regression_group", "path": "assign_regions", "expected": "FROZEN_POLICY",
                 "observed": assignment, "pass": passed, "trace": assignment})
    if len(rows) != 20:
        raise RuntimeError("synthetic fixture group count mismatch")
    return stamp({"schema_version": "panel-relation-tolerance-synthetic.v1", "checkpoint": "12.6",
                  "fixture_group_count": len(rows), "results": rows, "all_pass": all(row["pass"] for row in rows),
                  "gt_runtime_features": []})


def make_freeze(audit: dict[str, Any], control: dict[str, Any], proto: dict[str, Any], synthetic: dict[str, Any],
                oracle: dict[str, Any], realistic: dict[str, Any]) -> dict[str, Any]:
    return stamp({"schema_version": "panel-relation-tolerance-candidate-freeze.v1", "checkpoint": "12.6",
                  "chronology": ["NON_ORDER_INPUTS_VERIFIED", "ZERO_TOLERANCE_CONTROL_VERIFIED", "ONE_TOLERANCE_CONFIG_FROZEN",
                                 "ORACLE_REALISTIC_CANDIDATES_BUILT", "CANDIDATES_FROZEN_BEFORE_HUMAN_ORDER"],
                  "artifact_semantic_sha256": {"input-audit": audit["semantic_sha256"], "control-reference": control["semantic_sha256"],
                  "protocol": proto["protocol_sha256"], "synthetic": synthetic["semantic_sha256"],
                  "oracle-candidates": oracle["semantic_sha256"], "realistic-candidates": realistic["semantic_sha256"]},
                  "human_reading_order_artifacts_opened_before_freeze": [], "candidate_count": 1,
                  "gt_runtime_features": []}, "freeze_sha256")


def delta(candidate_result: dict[str, Any], control_result: dict[str, Any]) -> dict[str, int]:
    return {"resolved_pages": candidate_result["resolved_pages"] - control_result["resolved_pages"],
            "resolved_regions": candidate_result["resolved_regions"][0] - control_result["resolved_regions"][0],
            "resolved_pairs": candidate_result["resolved_comparable_pairwise"][1] - control_result["resolved_comparable_pairwise"][1],
            "exact_pages": candidate_result["exact_pages"][0] - control_result["exact_pages"][0],
            "confident_inversions": candidate_result["confident_inversions"] - control_result["confident_inversions"],
            "unresolved_pages": candidate_result["unresolved_pages"] - control_result["unresolved_pages"]}


def build_post_freeze(audit: dict[str, Any], control_ref: dict[str, Any], proto: dict[str, Any], synthetic: dict[str, Any],
                      oracle: dict[str, Any], realistic: dict[str, Any], freeze: dict[str, Any], resource: str,
                      barrier: FreezeBarrier, evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    barrier.assert_evaluation_allowed()
    human_doc, baseline = evidence["human_doc"], evidence["baseline"]
    control_eval = evidence["control_docs"]["evaluation"]
    built = BASE.build_final(audit["runtime_phase"], oracle, realistic, human_doc, baseline, freeze, synthetic, resource)
    oracle_result, realistic_result = built["evaluation"]["oracle"], built["evaluation"]["realistic"]
    control_oracle, control_realistic = control_eval["oracle"], control_eval["realistic"]
    oracle_delta, realistic_delta = delta(oracle_result, control_oracle), delta(realistic_result, control_realistic)
    control_candidates = {"oracle": evidence["control_docs"]["oracle-candidates"],
                          "realistic": evidence["control_docs"]["realistic-candidates"]}
    assignment_unchanged = all(canonical(cp["assignment"]) == canonical(bp["assignment"]) and canonical(cp["intra_panel"]) == canonical(bp["intra_panel"])
                               for track, candidate_doc in (("oracle", oracle), ("realistic", realistic))
                               for cp, bp in zip(candidate_doc["pages"], control_candidates[track]["pages"]))
    regressions = [row for result in (oracle_result, realistic_result) for row in result["seven_control_page_audit"] if row["status"] == "REGRESSED"]
    hard_failures = []
    if oracle_result["confident_inversions"] or realistic_result["confident_inversions"]: hard_failures.append("NEW_CONFIDENT_INVERSION")
    if regressions: hard_failures.append("PREVIOUSLY_EXACT_PAGE_REGRESSION")
    if not assignment_unchanged: hard_failures.append("ASSIGNMENT_OR_INTRA_PANEL_MUTATION")
    if not synthetic["all_pass"]: hard_failures.append("SYNTHETIC_SAFETY_FAILURE")
    nondecreasing = all(value >= 0 for values in (oracle_delta, realistic_delta) for key, value in values.items()
                        if key not in ("unresolved_pages", "confident_inversions"))
    both_pages = oracle_delta["resolved_pages"] > 0 and realistic_delta["resolved_pages"] > 0
    any_useful = any(values[key] > 0 for values in (oracle_delta, realistic_delta)
                     for key in ("resolved_pages", "resolved_regions", "resolved_pairs"))
    if hard_failures: outcome = "D. TOLERANCE CAUSES UNSAFE ORDERING"
    elif both_pages and nondecreasing: outcome = "A. SAFE TOLERANCE IMPROVEMENT"
    elif any_useful and nondecreasing: outcome = "B. TOLERANCE HELPS BUT REMAINS INCOMPLETE"
    else: outcome = "C. TOLERANCE DOES NOT SOLVE THE BOTTLENECK"
    evaluation = stamp({"schema_version": "panel-relation-tolerance-evaluation.v1", "checkpoint": "12.6",
                        "chronology": "POST_CANDIDATE_FREEZE_ONLY", "freeze_sha256": freeze["freeze_sha256"],
                        "control": {"oracle": control_oracle, "realistic": control_realistic},
                        "candidate": {"oracle": oracle_result, "realistic": realistic_result},
                        "delta": {"oracle": oracle_delta, "realistic": realistic_delta},
                        "hard_safety_failures": hard_failures, "assignment_and_intra_panel_unchanged": assignment_unchanged,
                        "post_freeze_control_internal_hashes_verified": evidence["post_freeze_control_internal_hashes_verified"],
                        "day11_inversion_audit": {"oracle": oracle_result["known_inversions"], "realistic": realistic_result["known_inversions"]},
                        "outcome": outcome, "gt_runtime_features": []})
    summary = stamp({"schema_version": "panel-relation-tolerance-summary.v1", "checkpoint": "12.6", "outcome": outcome,
                     "formula": {"tau_x": "1/W", "tau_y": "1/H", "source_pixels": 1},
                     "control_verified": True, "candidate": {"oracle": oracle_result, "realistic": realistic_result},
                     "delta": {"oracle": oracle_delta, "realistic": realistic_delta}, "hard_safety_failures": hard_failures,
                     "synthetic": {"fixture_groups": synthetic["fixture_group_count"], "all_pass": synthetic["all_pass"]},
                     "resource_guard": resource, "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
                     "production_changed": False, "human_testing_justified": False, "gt_runtime_features": []})
    return {"evaluation": evaluation, "summary": summary}


def pre_freeze_build(barrier: FreezeBarrier, run_name: str) -> dict[str, dict[str, Any]]:
    barrier.assert_candidate_generation_allowed(run_name)
    inputs = BASE.load_runtime_inputs()
    audit, control, proto, synthetic = input_audit(inputs), verify_control(), protocol(), synthetic_suite()
    validate_protocol(proto)
    provenance = build_provenance(audit, control, proto)
    provenance.update({"service_code_sha256": file_hash(ROOT / "backend/app/services/panel_aware_reading_order.py"),
                       "runner_code_sha256": file_hash(Path(__file__))})
    oracle = candidate("ORACLE_HUMAN_PANEL_GEOMETRY_IDS_STRIPPED", inputs, inputs["oracle"], provenance)
    realistic = candidate("FROZEN_SELECTED_RESOLVER_PANELS_NO_ORACLE_FALLBACK", inputs, inputs["realistic"], provenance)
    freeze = make_freeze(audit, control, proto, synthetic, oracle, realistic)
    artifacts = {"input-audit": audit, "control-reference": control, "protocol": proto, "synthetic": synthetic,
                 "oracle-candidates": oracle, "realistic-candidates": realistic, "candidate-freeze": freeze}
    barrier.freeze(run_name)
    return artifacts


def post_freeze_build(pre: dict[str, dict[str, Any]], barrier: FreezeBarrier,
                      evidence: dict[str, Any], resource: str) -> dict[str, dict[str, Any]]:
    barrier.assert_evaluation_allowed()
    artifacts = copy.deepcopy(pre)
    artifacts.update(build_post_freeze(artifacts["input-audit"], artifacts["control-reference"], artifacts["protocol"],
                     artifacts["synthetic"], artifacts["oracle-candidates"], artifacts["realistic-candidates"],
                     artifacts["candidate-freeze"], resource, barrier, evidence))
    return artifacts


def run() -> dict[str, Any]:
    before = sample_resources(ResourceThresholds.from_environment())
    if before["safety_state"] != "NORMAL":
        raise RuntimeError("Resource Guard is not NORMAL")
    barrier = FreezeBarrier()
    pre_a = pre_freeze_build(barrier, "RUN_A")
    pre_b = pre_freeze_build(barrier, "RUN_B")
    for name in NAMES[:7]:
        if rendered(pre_a[name]) != rendered(pre_b[name]) or digest(pre_a[name]) != digest(pre_b[name]):
            raise RuntimeError(f"pre-freeze RUN_A/RUN_B nondeterminism: {name}")
    barrier.activate()
    evidence_a = load_post_freeze_evidence(barrier)
    evidence_b = load_post_freeze_evidence(barrier)
    resource = sample_resources(ResourceThresholds.from_environment())["safety_state"]
    run_a = post_freeze_build(pre_a, barrier, evidence_a, resource)
    run_b = post_freeze_build(pre_b, barrier, evidence_b, resource)
    comparisons = {name: {"byte_equal": rendered(run_a[name]) == rendered(run_b[name]),
                          "semantic_hash_a": digest(run_a[name]), "semantic_hash_b": digest(run_b[name])} for name in NAMES}
    if not all(row["byte_equal"] and row["semantic_hash_a"] == row["semantic_hash_b"] for row in comparisons.values()):
        raise RuntimeError("RUN_A/RUN_B artifact nondeterminism")
    for artifact_set in (run_a, run_b):
        artifact_set["summary"]["global_freeze_chronology"] = barrier.events
        artifact_set["summary"]["both_candidates_frozen_before_first_human_open"] = (
            barrier.events.index("RUN_B_FROZEN") < next(index for index, event in enumerate(barrier.events) if event.startswith("POST_FREEZE_OPEN:")))
        artifact_set["summary"]["two_independent_builds"] = comparisons
        artifact_set["summary"].pop("semantic_sha256", None)
        artifact_set["summary"]["semantic_sha256"] = digest(artifact_set["summary"])
    if rendered(run_a["summary"]) != rendered(run_b["summary"]):
        raise RuntimeError("final summary nondeterminism")
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        for name in NAMES:
            (Path(first) / f"{name}.json").write_bytes(rendered(run_a[name]))
            (Path(second) / f"{name}.json").write_bytes(rendered(run_b[name]))
            if (Path(first) / f"{name}.json").read_bytes() != (Path(second) / f"{name}.json").read_bytes():
                raise RuntimeError(f"isolated output mismatch: {name}")
    for name in NAMES:
        OUT[name].write_bytes(rendered(run_a[name]))
    return run_a["summary"]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False))
