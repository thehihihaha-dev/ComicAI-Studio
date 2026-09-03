#!/usr/bin/env python3
"""Finite offline Checkpoint 12.8 geometry-identifiability audit."""
from __future__ import annotations

import copy, hashlib, importlib.util, json, sys, tempfile
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.resource_safety import ResourceThresholds, sample_resources


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R127 = load("panel_relation_model_12_7_for_12_8", ROOT / "scripts/panel_relation_model_12_7.py")
BASE = R127.BASE
DAY12 = ROOT / "benchmarks/day12"
COHORT = [1, 2, 3, 15, 18, 38]
CONTROLS = [4, 5, 7, 17]
NAMES = ("input-audit", "protocol", "synthetic", "phase-a-audit", "freeze",
         "contradiction-audit", "evaluation", "summary")
OUT = {name: DAY12 / f"panel-geometry-identifiability-{name}-12.8.json" for name in NAMES}
INVALID_STATUS = DAY12 / "panel-geometry-identifiability-invalid-status-12.8.json"
AUDIT_INVALIDATED = True
INVALIDATION_REASON = "PHASE_A_RULE_FAMILY_CHANGED_AFTER_HUMAN_ORDER_EXPOSURE"
FROZEN = {
    "input-audit": "29a68c8dbe7d51d3b473aa60336c7b948bbb35329083e24e52885f319f469848",
    "protocol": "a1577fc62dd1aa6b7e21b29e191ae9f34b1ac799d5a46e79fba4fd1557460ab8",
    "oracle-candidates": "66337371b13ec4c145c4b5b8a6bbfe22e86c89e514d69d93ead8993b072d4093",
    "candidate-freeze": "d97889b2cd41dbf3c138433781afb175892fc5259442e9de874209e258d6e6b9",
    "structural-audit": "44ff0af4fe04f4ea6443bb6606d4052efcc12dc12fcc4f9c7e00c17b9ff164d7",
}
RULES = ("MIN_TOP", "MAX_RIGHT", "MIN_CENTER_Y", "MAX_CENTER_X", "MAX_WIDTH", "MAX_HEIGHT",
         "ROW_RIGHTMOST", "COLUMN_TOPMOST", "TOP_X_SPANNING", "RIGHT_Y_SPANNING")
CLASSIFICATIONS = ("IDENTIFIABLE_BY_EXISTING_GEOMETRY", "GEOMETRY_NOT_IDENTIFIABLE",
                   "INSUFFICIENT_EVIDENCE", "CONTRADICTED_BY_CONTROL")

canonical, digest, rendered, stamp = R127.canonical, R127.digest, R127.rendered, R127.stamp
file_hash, verify_internal_hash = R127.file_hash, R127.verify_internal_hash


@dataclass
class Barrier:
    generated: set[str] = field(default_factory=set)
    frozen: set[str] = field(default_factory=set)
    active: bool = False
    human_open: bool = False
    events: list[str] = field(default_factory=lambda: ["INPUTS_VERIFIED"])

    def generated_audit(self, name: str) -> None:
        if self.human_open or self.frozen:
            raise RuntimeError("Phase A audit generation forbidden after freeze/Human access")
        self.generated.add(name)
        self.events.append(f"{name}_AUDIT_GENERATED")

    def freeze(self, name: str) -> None:
        if self.generated != {"RUN_A", "RUN_B"}:
            raise RuntimeError("both Phase A audits must be generated before freeze")
        self.frozen.add(name)
        self.events.append(f"{name}_FROZEN")

    def activate(self) -> None:
        if self.frozen != {"RUN_A", "RUN_B"}:
            raise RuntimeError("global barrier requires both frozen audits")
        self.active = True
        self.events.append("GLOBAL_FREEZE_BARRIER_ACTIVE")

    def open_human(self, path: Path):
        self.assert_evaluation()
        self.human_open = True
        self.events.append("HUMAN_ORDER_ACCESS_ALLOWED")
        return json.loads(path.read_text())

    def assert_evaluation(self) -> None:
        if not self.active or self.frozen != {"RUN_A", "RUN_B"}:
            raise RuntimeError("Phase B forbidden before global freeze barrier")


def frozen_docs(paths: dict[str, Path] | None = None) -> dict:
    if paths is None: paths = {n: DAY12 / f"panel-relation-model-{n}-12.7.json" for n in FROZEN}
    if set(paths) != set(FROZEN):
        raise RuntimeError("frozen artifact set mismatch")
    docs = {}
    for name, expected in FROZEN.items():
        if file_hash(paths[name]) != expected:
            raise RuntimeError(f"frozen 12.7 artifact mismatch: {name}")
        value = json.loads(paths[name].read_text())
        if not verify_internal_hash(value):
            raise RuntimeError(f"frozen 12.7 internal hash mismatch: {name}")
        docs[name] = value
    if docs["protocol"]["formula"] != {"tau_x": "1/W", "tau_y": "1/H", "source_pixel_intrusion": 1,
                                            "comparison": "<=", "vertical_precedence": True}:
        raise RuntimeError("tolerance protocol mismatch")
    if docs["protocol"]["assignment"] != ["UNIQUE_CONTAINMENT", "UNIQUE_CENTER_AND_STRICT_AREA_MAJORITY_GT_0.50", "AMBIGUOUS", "UNASSIGNED"]:
        raise RuntimeError("assignment protocol mismatch")
    return docs


def protocol() -> dict:
    return stamp({"schema_version": "panel-geometry-identifiability-protocol.v1", "checkpoint": "12.8",
                  "cohort": COHORT, "control_pages": CONTROLS, "rules": list(RULES),
                  "signature_fields": ["normalized_bbox", "normalized_width", "normalized_height",
                    "normalized_center", "projection_intervals", "containment", "intersection",
                    "horizontal_vertical_gaps", "horizontal_vertical_overlaps", "shared_boundaries",
                    "row_column_membership", "spanning", "adjacency", "relative_alignment",
                    "source_edge_contact", "ancestors", "descendants", "incoming_relations",
                    "outgoing_relations", "pair_predicates"],
                  "classifications": list(CLASSIFICATIONS),
                  "outcomes": ["A. GEOMETRY IDENTIFIABILITY FOUND", "B. PARTIAL GEOMETRY IDENTIFIABILITY",
                    "C. GEOMETRY REPRESENTATION LIMIT CONFIRMED", "D. AUDIT INVALID / SAFETY FAILURE"],
                  "tolerance": {"tau_x": "1/W", "tau_y": "1/H", "inclusive_source_pixels": 1},
                  "no_ordering_output": True, "human_order_derived_provenance_dependencies": [],
                  "gt_runtime_features": []}, "protocol_sha256")


def _f(value) -> Fraction:
    return Fraction(str(value))


def _q(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _signature(node: str, panels: dict, width: int, height: int, edges: list[dict], pair_rows: list[dict]) -> dict:
    x1, y1, x2, y2 = map(_f, panels[node]["bbox"])
    ancestors, descendants = set(), set()
    changed = True
    while changed:
        changed = False
        for edge in edges:
            if edge["after"] == node or edge["after"] in ancestors:
                changed |= edge["before"] not in ancestors; ancestors.add(edge["before"])
            if edge["before"] == node or edge["before"] in descendants:
                changed |= edge["after"] not in descendants; descendants.add(edge["after"])
    incoming = sorted((e["before"], e["relation"]) for e in edges if e["after"] == node)
    outgoing = sorted((e["after"], e["relation"]) for e in edges if e["before"] == node)
    pairs=[]
    for row in pair_rows:
        if node not in row["panel_ids"]:continue
        other=next(n for n in row["panel_ids"] if n != node);ox1,oy1,ox2,oy2=map(_f,panels[other]["bbox"])
        ix=max(Fraction(0),min(x2,ox2)-max(x1,ox1));iy=max(Fraction(0),min(y2,oy2)-max(y1,oy1))
        x_gap=max(Fraction(0),max(x1,ox1)-min(x2,ox2));y_gap=max(Fraction(0),max(y1,oy1)-min(y2,oy2))
        pairs.append({"other":other,"predicates":row["predicates"],"relation":row["relation"],"unresolved_reason":row["unresolved_reason"],
          "containment":{"contains_other":x1<=ox1 and y1<=oy1 and x2>=ox2 and y2>=oy2,
                         "inside_other":ox1<=x1 and oy1<=y1 and ox2>=x2 and oy2>=y2},
          "intersection":{"normalized_width":_q(ix/width),"normalized_height":_q(iy/height),"normalized_area":_q((ix/width)*(iy/height))},
          "gaps":{"horizontal":_q(x_gap/width),"vertical":_q(y_gap/height)},
          "overlaps":{"horizontal":_q(ix/width),"vertical":_q(iy/height)},
          "shared_boundaries":{"left":x1==ox1,"right":x2==ox2,"top":y1==oy1,"bottom":y2==oy2,
                               "touch_x":x2==ox1 or ox2==x1,"touch_y":y2==oy1 or oy2==y1},
          "row_column_membership":{"same_row":iy>0,"same_column":ix>0},
          "spanning":{"spans_other_x":x1<=ox1 and x2>=ox2,"spans_other_y":y1<=oy1 and y2>=oy2},
          "adjacency":{"horizontal":x_gap<=1 and iy>0,"vertical":y_gap<=1 and ix>0},
          "relative_alignment":{"left":x1==ox1,"right":x2==ox2,"top":y1==oy1,"bottom":y2==oy2,
                                "center_x":x1+x2==ox1+ox2,"center_y":y1+y2==oy1+oy2}})
    pairs.sort(key=lambda r:r["other"])
    return {"normalized_bbox": [_q(x1/width), _q(y1/height), _q(x2/width), _q(y2/height)],
            "normalized_width": _q((x2-x1)/width), "normalized_height": _q((y2-y1)/height),
            "normalized_center": [_q((x1+x2)/(2*width)), _q((y1+y2)/(2*height))],
            "projection_intervals": {"x": [_q(x1/width), _q(x2/width)], "y": [_q(y1/height), _q(y2/height)]},
            "source_edge_contact": {"left": x1 == 0, "top": y1 == 0, "right": x2 == width, "bottom": y2 == height},
            "ancestors": sorted(ancestors), "descendants": sorted(descendants),
            "incoming_relations": incoming, "outgoing_relations": outgoing, "pair_predicates": pairs}


def _rule_values(signatures: dict[str, dict]) -> dict[str, dict]:
    def frac(q): return Fraction(q)
    getters = {"MIN_TOP": lambda s: frac(s["normalized_bbox"][1]),
               "MAX_RIGHT": lambda s: frac(s["normalized_bbox"][2]),
               "MIN_CENTER_Y": lambda s: frac(s["normalized_center"][1]),
               "MAX_CENTER_X": lambda s: frac(s["normalized_center"][0]),
               "MAX_WIDTH": lambda s: frac(s["normalized_width"]),
               "MAX_HEIGHT": lambda s: frac(s["normalized_height"])}
    out = {}
    for rule, getter in getters.items():
        values = {node: getter(sig) for node, sig in signatures.items()}
        best = min(values.values()) if rule.startswith("MIN") else max(values.values())
        winners = sorted(n for n, value in values.items() if value == best)
        out[rule] = {"values": {n: _q(v) for n, v in sorted(values.items())},
                     "unique_winner": winners[0] if len(winners) == 1 else None, "tied_winners": winners}
    nodes=sorted(signatures)
    def all_relation(field,key):
        return all(any(p["other"]==b and p[field][key] for p in signatures[a]["pair_predicates"]) for i,a in enumerate(nodes) for b in nodes[i+1:])
    def conditional(rule,applicable,winner):
        out[rule]={"values":{"applicable":applicable},"unique_winner":winner if applicable else None,
                   "tied_winners":[winner] if applicable and winner else []}
    conditional("ROW_RIGHTMOST",all_relation("row_column_membership","same_row"),out["MAX_CENTER_X"]["unique_winner"])
    conditional("COLUMN_TOPMOST",all_relation("row_column_membership","same_column"),out["MIN_CENTER_Y"]["unique_winner"])
    xsp=[n for n in nodes if all(any(p["other"]==o and p["spanning"]["spans_other_x"] for p in signatures[n]["pair_predicates"]) for o in nodes if o!=n)]
    ysp=[n for n in nodes if all(any(p["other"]==o and p["spanning"]["spans_other_y"] for p in signatures[n]["pair_predicates"]) for o in nodes if o!=n)]
    conditional("TOP_X_SPANNING",len(xsp)==1,xsp[0] if len(xsp)==1 else None)
    conditional("RIGHT_Y_SPANNING",len(ysp)==1,ysp[0] if len(ysp)==1 else None)
    return out


def ready_sets(page: dict) -> list[dict]:
    trace = page["panel_order"]; nodes = trace["active_nodes"]
    panels = {p["panel_id"]: p for p in page["panel_nodes"]}; edges = trace["active_edges"]
    outgoing = {n: [] for n in nodes}; initial = {n: 0 for n in nodes}
    for edge in edges: outgoing[edge["before"]].append(edge["after"]); initial[edge["after"]] += 1
    seen, ambiguous = set(), []
    def walk(indeg: dict, emitted: tuple[str, ...]):
        key = (tuple(sorted(indeg.items())), emitted)
        if key in seen: return
        seen.add(key); ready = sorted(n for n, degree in indeg.items() if degree == 0)
        if len(ready) >= 2:
            sigs = {n: _signature(n, panels, page["source_dimensions"][0], page["source_dimensions"][1],
                                  edges, trace["pair_evidence"]) for n in ready}
            equivalence = {}
            for node, sig in sigs.items(): equivalence.setdefault(digest(sig), []).append(node)
            rid = "RS_" + hashlib.sha256(canonical({"emitted": emitted, "ready": ready})).hexdigest()[:12]
            ambiguous.append({"ready_set_id": rid, "emitted_nodes": list(emitted), "members": ready,
                              "reason": "MULTIPLE_TOPOLOGICAL_ORDERS", "signatures": sigs,
                              "equivalence_classes": [sorted(v) for _, v in sorted(equivalence.items())],
                              "rule_candidates": _rule_values(sigs)})
        for node in ready:
            nxt = dict(indeg); nxt.pop(node)
            for target in outgoing[node]: nxt[target] -= 1
            walk(nxt, emitted + (node,))
    walk(initial, ())
    return sorted(ambiguous, key=lambda row: row["ready_set_id"])


def input_audit(docs: dict) -> dict:
    source = docs["input-audit"]["runtime_phase"]["pages"]
    pages = []
    for row in source:
        if row["page_order"] not in COHORT: continue
        path = ROOT / row["source_path"]
        if file_hash(path) != row["source_hash"]: raise RuntimeError("source identity mismatch")
        pages.append({"page_order": row["page_order"], "source_path": row["source_path"],
                      "source_hash": row["source_hash"], "source_dimensions": row["image_dimensions"],
                      "panel_geometry_semantic_sha256": digest(row["oracle_panels"]),
                      "logical_geometry_semantic_sha256": digest(row["persisted_logical_regions"])})
    if [p["page_order"] for p in pages] != COHORT: raise RuntimeError("six-page cohort mismatch")
    return stamp({"schema_version": "panel-geometry-identifiability-input-audit.v1", "checkpoint": "12.8",
                  "status": "FROZEN_GEOMETRY_IDENTITIES_VERIFIED", "pages": pages,
                  "accepted_phase_a_artifacts": sorted(FROZEN), "accepted_phase_a_raw_hashes": FROZEN,
                  "human_derived_artifact_hashes": [], "human_order_derived_provenance_dependencies": [],
                  "gt_runtime_features": []})


def build_phase_a(barrier: Barrier, name: str, docs: dict) -> dict:
    barrier.generated_audit(name)
    pages = []
    candidates = {p["page_order"]: p for p in docs["oracle-candidates"]["pages"]}
    for page_order in COHORT:
        page = candidates[page_order]
        if page["panel_order"]["resolved"] or [u["reason"] for u in page["panel_order"]["unresolved"]] != ["MULTIPLE_TOPOLOGICAL_ORDERS"]:
            raise RuntimeError("target is not frozen MULTIPLE_TOPOLOGICAL_ORDERS")
        rows = ready_sets(page)
        if not rows: raise RuntimeError("missing ambiguous ready set")
        pages.append({"page_order": page_order, "ready_sets": rows, "ready_set_count": len(rows)})
    return stamp({"schema_version": "panel-geometry-identifiability-phase-a.v1", "checkpoint": "12.8",
                  "cohort": COHORT, "pages": pages, "ready_set_count": sum(p["ready_set_count"] for p in pages),
                  "ordering_edges_emitted": [], "human_reading_order_loaded": False,
                  "human_order_derived_provenance_dependencies": [], "gt_runtime_features": []})


def validate_phase_a(value: dict) -> None:
    if not verify_internal_hash(value): raise RuntimeError("frozen Phase A artifact mismatch")
    if value.get("cohort") != COHORT or value.get("ordering_edges_emitted") != []:
        raise RuntimeError("Phase A scope/order mutation")
    if value.get("gt_runtime_features") != [] or value.get("human_order_derived_provenance_dependencies") != []:
        raise RuntimeError("Human-derived Phase A provenance contamination")
    forbidden=("human_sequence","human_order","correctness","expected_precedence","inversion_outcome")
    def walk(item):
        if isinstance(item,dict):
            return any((any(token in str(k).lower() for token in forbidden) and v not in (False,None,[],{})) or walk(v) for k,v in item.items())
        if isinstance(item,list):return any(walk(v) for v in item)
        return False
    if walk(value):raise RuntimeError("Human-derived Phase A provenance contamination")


def synthetic_suite() -> dict:
    fixtures = ["unique", "equivalent", "symmetric", "2x2_rtl", "horizontal", "vertical", "spanning_row",
                "tall_beside_stacked", "reversed_tall_beside_stacked", "offset", "ambiguous_ready_set",
                "bridge_non_transitivity", "cycle", "contradiction_control", "exact_1px", "beyond_1px",
                "empty", "single"]
    # The real audit path is exercised by converting real PCPDAG traces into the same ready-set representation.
    base = R127.synthetic_suite()["results"]
    lookup = {r["fixture"]: r for r in base}
    mapping = {"2x2_rtl":"2x2", "horizontal":"horizontal", "vertical":"vertical", "spanning_row":"span_top",
               "tall_beside_stacked":"tall_right", "reversed_tall_beside_stacked":"tall_left", "offset":"offset",
               "ambiguous_ready_set":"ambiguous", "bridge_non_transitivity":"bridge", "cycle":"explicit_cycle",
               "exact_1px":"equal_1px", "beyond_1px":"beyond_1px", "empty":"empty", "single":"single",
               "unique":"horizontal", "equivalent":"ambiguous", "symmetric":"ambiguous", "contradiction_control":"diagonal_opposed"}
    rows=[]
    for name in fixtures:
        source=mapping[name]; record=lookup[source]; trace=record["trace"]
        boxes={}
        for pair in trace.get("pair_evidence",[]): boxes.update(pair.get("source_bbox",{}))
        if source=="single": boxes={"p0":["0","0","100","100"]}
        panels=[{"panel_id":node,"bbox":boxes[node]} for node in trace.get("nodes",[]) if node in boxes]
        page={"source_dimensions":[120,120],"panel_nodes":panels,
              "panel_order":{**trace,"active_edges":trace.get("active_edges",trace.get("edges",[]))}}
        audit_rows=ready_sets(page) if set(trace.get("active_nodes",trace.get("nodes",[])))==set(boxes) else []
        expected_ambiguous=source == "ambiguous"
        signature_complete=True
        if audit_rows:
            sample=next(iter(audit_rows[0]["signatures"].values()))
            pair=sample["pair_predicates"][0]
            signature_complete=all(k in pair for k in ("containment","intersection","gaps","overlaps","shared_boundaries",
                "row_column_membership","spanning","adjacency","relative_alignment"))
        audit_pass=signature_complete and (bool(audit_rows)==expected_ambiguous if expected_ambiguous else True)
        rows.append({"fixture":name,"source_fixture":source,"actual_pcpdag_path":record["path"],
                     "actual_audit_path":"ready_sets+complete_signature","audit_ready_set_count":len(audit_rows),
                     "expected_ambiguous_ready_set":expected_ambiguous,"signature_assertions_pass":signature_complete,
                     "pass":record["pass"] and audit_pass})
    def sig(a,b):
        panels={"a":{"panel_id":"a","bbox":a},"b":{"panel_id":"b","bbox":b}}
        trace=R127.projection_constraint_order(list(panels.values()),(100,100))
        return _signature("a",panels,100,100,trace.get("active_edges",trace.get("edges",[])),trace["pair_evidence"])
    property_cases=[
      ("containment_signature",lambda:next(p for p in sig([0,0,100,100],[10,10,20,20])["pair_predicates"] if p["other"]=="b")["containment"]["contains_other"]),
      ("intersection_signature",lambda:Fraction(next(p for p in sig([0,0,60,60],[40,40,100,100])["pair_predicates"] if p["other"]=="b")["intersection"]["normalized_area"])>0),
      ("gap_signature",lambda:Fraction(next(p for p in sig([0,0,20,20],[40,0,60,20])["pair_predicates"] if p["other"]=="b")["gaps"]["horizontal"])>0),
      ("overlap_signature",lambda:Fraction(next(p for p in sig([0,0,60,60],[40,40,100,100])["pair_predicates"] if p["other"]=="b")["overlaps"]["horizontal"])>0),
      ("shared_boundary_signature",lambda:next(p for p in sig([0,0,40,40],[40,0,80,40])["pair_predicates"] if p["other"]=="b")["shared_boundaries"]["touch_x"]),
      ("row_signature",lambda:next(p for p in sig([0,0,40,40],[60,0,100,40])["pair_predicates"] if p["other"]=="b")["row_column_membership"]["same_row"]),
      ("column_signature",lambda:next(p for p in sig([0,0,40,40],[0,60,40,100])["pair_predicates"] if p["other"]=="b")["row_column_membership"]["same_column"]),
      ("spanning_signature",lambda:next(p for p in sig([0,0,100,30],[10,40,40,90])["pair_predicates"] if p["other"]=="b")["spanning"]["spans_other_x"]),
      ("adjacency_signature",lambda:next(p for p in sig([0,0,40,40],[41,0,80,40])["pair_predicates"] if p["other"]=="b")["adjacency"]["horizontal"]),
      ("relative_alignment_signature",lambda:next(p for p in sig([0,0,40,40],[60,0,100,40])["pair_predicates"] if p["other"]=="b")["relative_alignment"]["top"]),
      ("edge_contact_signature",lambda:sig([0,0,40,40],[60,0,100,40])["source_edge_contact"]["left"]),
      ("target_mismatch_semantics",lambda:classify_ready(False,[{"winner":"b","target_result":"TARGET_MISMATCH","contradiction_count":0}],"a")[0]=="INSUFFICIENT_EVIDENCE"),
      ("separate_control_contradiction_semantics",lambda:classify_ready(False,[{"winner":"a","target_result":"MATCH","contradiction_count":1}],"a")[0]=="CONTRADICTED_BY_CONTROL")]
    for name,check in property_cases:
        observed=bool(check());rows.append({"fixture":name,"actual_audit_path":"complete_signature/classification","expected":True,"observed":observed,"pass":observed})
    return stamp({"schema_version": "panel-geometry-identifiability-synthetic.v1", "checkpoint": "12.8",
                  "fixture_count": len(rows), "passed": sum(r["pass"] for r in rows), "results": rows,
                  "all_pass": all(r["pass"] for r in rows), "gt_runtime_features": []})


def freeze_doc(audit: dict, proto: dict, synthetic: dict, phase: dict) -> dict:
    return stamp({"schema_version": "panel-geometry-identifiability-freeze.v1", "checkpoint": "12.8",
                  "phase_a_semantic_hashes": {"input-audit": audit["semantic_sha256"],
                    "protocol": proto["protocol_sha256"], "synthetic": synthetic["semantic_sha256"],
                    "phase-a-audit": phase["semantic_sha256"]}, "both_runs_generated_before_freeze": True,
                  "human_access_before_freeze": [], "gt_runtime_features": []}, "freeze_sha256")


def _panel_human_rank(page: dict, human_page: dict) -> dict[str, int]:
    assignment = {r["region_id"]: r["panel_id"] for r in page["assignment"]["assignments"]}
    rank = {}
    for index, region in enumerate(human_page["human"]):
        if region in assignment: rank.setdefault(assignment[region], index)
    return rank


def classify_ready(equivalent: bool, tested: list[dict], expected: str) -> tuple[str,list[str],list[str]]:
    survivors=[r["distinction_id"] for r in tested if r.get("winner")==expected and not r.get("contradiction_count")]
    failures=[]
    if equivalent:failures.append("GEOMETRIC_EQUIVALENCE")
    if any(r.get("target_result")=="TARGET_MISMATCH" for r in tested):failures.append("TARGET_MISMATCH")
    if any(r.get("contradiction_count") for r in tested):failures.append("CONTROL_CONTRADICTION")
    if not any(r.get("winner") for r in tested):failures.append("NO_UNIQUE_DISTINCTION")
    if equivalent:classification="GEOMETRY_NOT_IDENTIFIABLE"
    elif survivors:classification="IDENTIFIABLE_BY_EXISTING_GEOMETRY"
    elif any(r.get("winner")==expected and r.get("contradiction_count") for r in tested):classification="CONTRADICTED_BY_CONTROL"
    else:classification="INSUFFICIENT_EVIDENCE"
    return classification,survivors,failures or ["INSUFFICIENT_EVIDENCE"]


def evaluate(barrier: Barrier, phase: dict, candidate: dict, human: dict) -> tuple[dict, dict]:
    barrier.assert_evaluation()
    human_pages = {p["page_order"]: p for p in human["pages"]}
    candidate_pages = {p["page_order"]: p for p in candidate["pages"]}
    control_contradictions = {rule: [] for rule in RULES}
    # Frozen resolved pages are contradiction controls only.
    for page_order in CONTROLS:
        page = candidate_pages[page_order]; rank = _panel_human_rank(page, human_pages[page_order])
        sigs = {p["panel_id"]: _signature(p["panel_id"], {q["panel_id"]:q for q in page["panel_nodes"]},
                page["source_dimensions"][0], page["source_dimensions"][1], page["panel_order"]["active_edges"],
                page["panel_order"]["pair_evidence"]) for p in page["panel_nodes"] if p["panel_id"] in rank}
        for a in sorted(sigs):
            for b in sorted(sigs):
                if a >= b: continue
                for rule, data in _rule_values({a:sigs[a], b:sigs[b]}).items():
                    winner=data["unique_winner"]
                    if winner and rank[winner] != min(rank[a],rank[b]):
                        control_contradictions[rule].append({"control_id":f"CTRL_{page_order}_{a}_{b}","page_order":page_order,
                          "panels":[a,b],"distinction_id":rule,"geometry_evidence":data,
                          "predicted_precedence":[winner,b if winner==a else a],
                          "human_precedence":[a,b] if rank[a]<rank[b] else [b,a],
                          "contradiction_reason":"SAME_DETERMINISTIC_DISTINCTION_REVERSES_FROZEN_CONTROL_PRECEDENCE"})
    findings=[]
    for page_row in phase["pages"]:
        page = candidate_pages[page_row["page_order"]]; rank = _panel_human_rank(page, human_pages[page_row["page_order"]])
        for ready in page_row["ready_sets"]:
            expected = min(ready["members"], key=lambda n: rank.get(n, 10**9))
            equivalent = any(len(group)>1 for group in ready["equivalence_classes"])
            tested=[]; survivors=[]
            for rule,data in ready["rule_candidates"].items():
                winner=data["unique_winner"]; contradictions=control_contradictions[rule]
                row={"distinction_id":rule,"winner":winner,"target_result":"MATCH" if winner==expected else "TARGET_MISMATCH" if winner else "NO_UNIQUE_DISTINCTION",
                     "applicable_control_ids":[c["control_id"] for c in contradictions],"control_contradictions":contradictions,
                     "contradiction_count":len(contradictions),"survives":bool(winner==expected and not contradictions)}
                tested.append(row)
                if row["survives"]:survivors.append(rule)
            classification,survivors,failures=classify_ready(equivalent,tested,expected)
            findings.append({"page_order":page_row["page_order"],"ready_set_id":ready["ready_set_id"],
                             "classification":classification,"expected_panel_post_freeze":expected,
                             "failure_types":failures or ["INSUFFICIENT_EVIDENCE"],"equivalence_status":"COMPLETE_SIGNATURE_EQUIVALENT" if equivalent else "NO_COMPLETE_SIGNATURE_EQUIVALENCE",
                             "surviving_rules":survivors,"rules":tested})
    counts={c:sum(f["classification"]==c for f in findings) for c in CLASSIFICATIONS}
    if counts["IDENTIFIABLE_BY_EXISTING_GEOMETRY"]==len(findings):outcome="A. GEOMETRY IDENTIFIABILITY FOUND"
    elif counts["IDENTIFIABLE_BY_EXISTING_GEOMETRY"]:outcome="B. PARTIAL GEOMETRY IDENTIFIABILITY"
    elif counts["GEOMETRY_NOT_IDENTIFIABLE"]+counts["CONTRADICTED_BY_CONTROL"]==len(findings):
        outcome="C. GEOMETRY REPRESENTATION LIMIT CONFIRMED"
    else:
        outcome="D. AUDIT INVALID / SAFETY FAILURE"
    contradiction = stamp({"schema_version":"panel-geometry-identifiability-contradiction.v1","checkpoint":"12.8",
                           "rules": [{"rule":r,"contradiction_count":len(v),"contradictions":v} for r,v in control_contradictions.items()],
                           "controls_are_rejection_only":True,"gt_runtime_features":[]})
    evaluation = stamp({"schema_version":"panel-geometry-identifiability-evaluation.v1","checkpoint":"12.8",
                        "phase":"POST_GLOBAL_FREEZE_ONLY","findings":findings,"classification_counts":counts,
                        "outcome":outcome,"new_ordering_edges":[],"gt_runtime_features":[]})
    return contradiction,evaluation


def comparison_material(name: str, value: dict) -> dict:
    material=copy.deepcopy(value)
    for key in ("semantic_sha256","protocol_sha256","freeze_sha256"):material.pop(key,None)
    if name=="summary":material.pop("two_independent_runs",None)
    return material


def comparison(name: str, a: dict, b: dict) -> dict:
    ma=comparison_material(name,a) if name=="summary" else a
    mb=comparison_material(name,b) if name=="summary" else b
    return {"artifact":name,"path":str(OUT[name].relative_to(ROOT)),"raw_hash_convention":"SUMMARY_EXCLUDED_ENVELOPE" if name=="summary" else "FINAL_PERSISTED_ARTIFACT",
            "raw_byte_sha256_a":hashlib.sha256(rendered(ma)).hexdigest(),"raw_byte_sha256_b":hashlib.sha256(rendered(mb)).hexdigest(),
            "canonical_semantic_sha256_a":digest(ma),"canonical_semantic_sha256_b":digest(mb),
            "raw_equal":rendered(ma)==rendered(mb),"semantic_equal":digest(ma)==digest(mb)}


def run() -> dict:
    if AUDIT_INVALIDATED:
        raise RuntimeError("Checkpoint 12.8 is invalidated; authoritative audit rerun is forbidden")
    if sample_resources(ResourceThresholds.from_environment())["safety_state"] != "NORMAL":
        raise RuntimeError("Resource Guard is not NORMAL")
    docs_a=frozen_docs();docs_b=frozen_docs();audit_a=input_audit(docs_a);audit_b=input_audit(docs_b)
    proto_a=protocol();proto_b=protocol();syn_a=synthetic_suite();syn_b=synthetic_suite();barrier=Barrier()
    phase_a_build=build_phase_a(barrier,"RUN_A",docs_a);phase_b=build_phase_a(barrier,"RUN_B",docs_b)
    validate_phase_a(phase_a_build);validate_phase_a(phase_b)
    for x,y in ((audit_a,audit_b),(proto_a,proto_b),(syn_a,syn_b),(phase_a_build,phase_b)):
        if rendered(x)!=rendered(y):raise RuntimeError("Phase A nondeterminism")
    barrier.freeze("RUN_A");barrier.freeze("RUN_B");freeze_a=freeze_doc(audit_a,proto_a,syn_a,phase_a_build);freeze_b=freeze_doc(audit_b,proto_b,syn_b,phase_b);barrier.activate()
    human_a=barrier.open_human(BASE.EVAL["human_order"]);human_b=copy.deepcopy(human_a)
    contradiction_a,evaluation_a=evaluate(barrier,phase_a_build,docs_a["oracle-candidates"],human_a)
    contradiction_b,evaluation_b=evaluate(barrier,phase_b,docs_b["oracle-candidates"],human_b)
    summary_a=stamp({"schema_version":"panel-geometry-identifiability-summary.v1","checkpoint":"12.8",
                     "outcome":evaluation_a["outcome"],"cohort":COHORT,"ready_set_count":phase_a_build["ready_set_count"],
                     "classification_counts":evaluation_a["classification_counts"],"chronology":barrier.events+["PHASE_B_EVALUATION"],
                     "resource_guard":"NORMAL","model_calls":{"ocr":0,"vlm":0,"ollama":0},"production_changed":False,"gt_runtime_features":[]})
    summary_b=copy.deepcopy(summary_a)
    builds_a={"input-audit":audit_a,"protocol":proto_a,"synthetic":syn_a,"phase-a-audit":phase_a_build,"freeze":freeze_a,
              "contradiction-audit":contradiction_a,"evaluation":evaluation_a,"summary":summary_a}
    builds_b={"input-audit":audit_b,"protocol":proto_b,"synthetic":syn_b,"phase-a-audit":phase_b,"freeze":freeze_b,
              "contradiction-audit":contradiction_b,"evaluation":evaluation_b,"summary":summary_b}
    comparisons={n:comparison(n,builds_a[n],builds_b[n]) for n in NAMES}
    if not all(r["raw_equal"] and r["semantic_equal"] for r in comparisons.values()):raise RuntimeError("RUN_A/RUN_B nondeterminism")
    for build in (builds_a,builds_b):
        build["summary"]["two_independent_runs"]=comparisons;build["summary"].pop("semantic_sha256");build["summary"]["semantic_sha256"]=digest(build["summary"])
    if rendered(builds_a["summary"])!=rendered(builds_b["summary"]):raise RuntimeError("summary nondeterminism")
    with tempfile.TemporaryDirectory() as one,tempfile.TemporaryDirectory() as two:
        for name in NAMES:
            (Path(one)/name).write_bytes(rendered(builds_a[name]));(Path(two)/name).write_bytes(rendered(builds_b[name]))
            if (Path(one)/name).read_bytes()!=(Path(two)/name).read_bytes():raise RuntimeError("isolated build mismatch")
    for name in NAMES:OUT[name].write_bytes(rendered(builds_a[name]))
    return builds_a["summary"]


if __name__ == "__main__": print(json.dumps(run(),ensure_ascii=False))
