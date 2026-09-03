"""Offline geometry primitives for Checkpoint 12.5.

This module deliberately accepts only identifiers and bounding boxes.  It has
no access to Human reading-order labels, OCR text, or detector state.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Any


BBox = tuple[float, float, float, float]


def _box(item: dict[str, Any]) -> BBox:
    value = item["bbox"]
    if len(value) != 4:
        raise ValueError("bbox must contain four coordinates")
    box = tuple(float(number) for number in value)
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("bbox must have positive area")
    return box  # type: ignore[return-value]


def _intersection(a: BBox, b: BBox) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _contains(outer: BBox, inner: BBox) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def assign_regions(regions: list[dict[str, Any]], panels: list[dict[str, Any]]) -> dict[str, Any]:
    """Assign regions without guessing when more than one panel competes."""
    assignments, ambiguous, unassigned = [], [], []
    for region in regions:
        rb = _box(region)
        area = (rb[2] - rb[0]) * (rb[3] - rb[1])
        cx, cy = (rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2
        candidates = []
        for panel in panels:
            pb = _box(panel)
            coverage = _intersection(rb, pb) / area
            candidates.append({"panel_id": panel["panel_id"], "coverage": coverage,
                               "contains": _contains(pb, rb),
                               "center_inside": pb[0] <= cx <= pb[2] and pb[1] <= cy <= pb[3]})
        exact = [row for row in candidates if row["contains"]]
        majority = [row for row in candidates if row["center_inside"] and row["coverage"] > 0.5]
        eligible, method = (exact, "UNIQUE_CONTAINMENT") if exact else (majority, "UNIQUE_CENTER_STRICT_MAJORITY")
        record = {"region_id": region["id"], "competing_panels": candidates}
        if len(eligible) == 1:
            state = "ASSIGNED_CONTAINED" if method == "UNIQUE_CONTAINMENT" else "ASSIGNED_INTERSECTION"
            assignments.append({**record, "panel_id": eligible[0]["panel_id"], "method": method, "state": state})
        elif len(eligible) > 1:
            ambiguous.append({**record, "reason": "MULTIPLE_ELIGIBLE_PANELS"})
        else:
            unassigned.append({**record, "reason": "NO_ELIGIBLE_PANEL"})
    return {"assignments": assignments, "ambiguous": ambiguous, "unassigned": unassigned}


@dataclass
class _Order:
    ids: list[str]
    edges: list[dict[str, str]]
    partitions: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _exact_box(item: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    value = item["bbox"]
    if len(value) != 4:
        raise ValueError("bbox must contain four coordinates")
    box = tuple(Decimal(str(number)) for number in value)
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("bbox must have positive area")
    return box  # type: ignore[return-value]


def canonical_projection_panels(panels: list[dict[str, Any]],
                                source_dimensions: tuple[int, int]) -> list[dict[str, Any]]:
    """Strip opaque IDs and assign normalized-geometry identities."""
    width, height = (Decimal(value) for value in source_dimensions)
    if width <= 0 or height <= 0:
        raise ValueError("positive source dimensions are required")
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for panel in panels:
        box = _exact_box(panel)
        normalized = (Fraction(box[0]) / int(width), Fraction(box[1]) / int(height),
                      Fraction(box[2]) / int(width), Fraction(box[3]) / int(height))
        key = tuple(f"{value.numerator}/{value.denominator}" for value in normalized)
        grouped.setdefault(key, []).append(panel)
    result = []
    for key in sorted(grouped):
        geometry_hash = __import__("hashlib").sha256("|".join(key).encode()).hexdigest()[:12]
        for ordinal, panel in enumerate(grouped[key]):
            result.append({"panel_id": f"PGN_{geometry_hash}_{ordinal:03d}",
                           "bbox": list(panel["bbox"]), "normalized_bbox": list(key),
                           "duplicate_ordinal": ordinal})
    return result


def _axis_partitions(items: list[dict[str, Any]], axis: int, tolerance: Decimal) -> list[tuple[Decimal, Decimal, list[dict[str, Any]], list[dict[str, Any]]]]:
    """Return ordered guillotine partitions whose envelope intrusion is tolerated."""
    ordered = sorted(items, key=lambda item: (
        (_decimal(_box(item)[axis]) + _decimal(_box(item)[axis + 2])) / 2,
        str(item["panel_id"]),
    ))
    choices = []
    for index in range(1, len(ordered)):
        first, second = ordered[:index], ordered[index:]
        first_end = max(_decimal(_box(item)[axis + 2]) for item in first)
        second_start = min(_decimal(_box(item)[axis]) for item in second)
        signed_gap = second_start - first_end
        intrusion = max(Decimal(0), -signed_gap)
        if intrusion <= tolerance:
            cut = (first_end + second_start) / 2
            choices.append((signed_gap, cut, first, second))
    return choices


def _partition(items: list[dict[str, Any]], tolerance_x: Decimal, tolerance_y: Decimal) -> _Order:
    if len(items) <= 1:
        return _Order([str(items[0]["panel_id"])] if items else [], [], [], [])
    # Horizontal whitespace is preferred. This represents manga rows before
    # applying right-to-left order within each recursively isolated row.
    choices = _axis_partitions(items, 1, tolerance_y)
    relation = "ABOVE"
    if choices:
        signed_gap, cut, first, second = max(choices, key=lambda row: (row[0], -row[1]))
    else:
        vertical = _axis_partitions(items, 0, tolerance_x)
        if not vertical:
            ids = sorted(str(item["panel_id"]) for item in items)
            return _Order([], [], [], [{"panel_ids": ids, "reason": "NO_STRICT_GUILLOTINE_PARTITION"}])
        signed_gap, cut, left, right = max(vertical, key=lambda row: (row[0], row[1]))
        first, second = right, left
        relation = "RIGHT_OF"
    one, two = _partition(first, tolerance_x, tolerance_y), _partition(second, tolerance_x, tolerance_y)
    edges = one.edges + two.edges + [
        {"before": left, "after": right, "relation": relation}
        for left in one.ids for right in two.ids
    ]
    partition = {"relation": relation, "cut": float(cut),
                 "source_intrusion": float(max(Decimal(0), -signed_gap)),
                 "before_panel_ids": one.ids, "after_panel_ids": two.ids}
    return _Order(one.ids + two.ids, edges, [partition] + one.partitions + two.partitions,
                  one.unresolved + two.unresolved)


def topological_order(nodes: list[str], edges: list[dict[str, str]]) -> dict[str, Any]:
    nodes = sorted(nodes)
    incoming = {node: set() for node in nodes}
    outgoing = {node: set() for node in nodes}
    for edge in edges:
        incoming[edge["after"]].add(edge["before"])
        outgoing[edge["before"]].add(edge["after"])
    order, trace, unresolved = [], [], []
    while len(order) < len(nodes) and not unresolved:
        ready = sorted(node for node in nodes if node not in order and incoming[node].issubset(order))
        trace.append({"ready": ready, "emitted": ready[0] if len(ready) == 1 else None})
        if len(ready) != 1:
            unresolved.append({"panel_ids": ready or sorted(set(nodes) - set(order)),
                               "reason": "MULTIPLE_TOPOLOGICAL_ORDERS" if ready else "CYCLE"})
            break
        order.append(ready[0])
    closure = []
    for source in nodes:
        pending, seen = list(outgoing[source]), set()
        while pending:
            target = pending.pop()
            if target in seen:
                continue
            seen.add(target); pending.extend(outgoing[target])
        closure.extend({"before": source, "after": target} for target in sorted(seen))
    return {"order": order if not unresolved else [], "transitive_closure": closure,
            "topological_trace": trace, "unresolved": unresolved, "resolved": not unresolved}


def projection_constraint_order(panels: list[dict[str, Any]], source_dimensions: tuple[int, int],
                                active_panel_ids: set[str] | None = None) -> dict[str, Any]:
    """Build the frozen 12.7 pairwise projection-constraint DAG.

    The one-pixel comparisons are performed in source coordinates; this is
    algebraically identical to comparing normalized intrusion with 1/W or 1/H.
    """
    width, height = source_dimensions
    if width <= 0 or height <= 0:
        raise ValueError("positive source dimensions are required")
    by_id = {str(panel["panel_id"]): panel for panel in panels}
    if len(by_id) != len(panels):
        return {"nodes": sorted(by_id), "active_nodes": [], "order": [], "edges": [],
                "pair_evidence": [], "transitive_closure": [], "topological_trace": [],
                "cycles": [], "unresolved": [{"reason": "CONFLICTING_AXIS_EVIDENCE",
                                                "detail": "DUPLICATE_PANEL_ID"}], "resolved": False}
    nodes = sorted(by_id)
    active = sorted(active_panel_ids if active_panel_ids is not None else set(nodes))
    if not set(active).issubset(nodes):
        raise ValueError("active panel is absent from graph")
    boxes = {node: _exact_box(by_id[node]) for node in nodes}
    for node, box in boxes.items():
        if box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height:
            raise ValueError(f"panel outside source bounds: {node}")
    evidence, edges, conflicts = [], [], []
    for index, left_id in enumerate(nodes):
        for right_id in nodes[index + 1:]:
            a, b = boxes[left_id], boxes[right_id]
            a_above = a[3] - b[1] <= 1
            b_above = b[3] - a[1] <= 1
            a_right = b[2] - a[0] <= 1
            b_right = a[2] - b[0] <= 1
            relation = before = after = None
            reason = None
            labels: list[str] = []
            if a_above and b_above or a_right and b_right:
                reason = "CONFLICTING_AXIS_EVIDENCE"
            elif a_above != b_above:
                before, after = (left_id, right_id) if a_above else (right_id, left_id)
                relation = "ABOVE"; labels.append("ABOVE")
                same_right = (a_right and before == left_id) or (b_right and before == right_id)
                if same_right:
                    labels.append("RIGHT_OF")
            elif a_right != b_right:
                before, after = (left_id, right_id) if a_right else (right_id, left_id)
                relation = "RIGHT_OF"; labels.append("RIGHT_OF")
            else:
                reason = "INCOMPARABLE"
            row = {"pair_id": f"pair:{left_id}:{right_id}", "panel_ids": [left_id, right_id],
                   "source_bbox": {left_id: [str(v) for v in a], right_id: [str(v) for v in b]},
                   "normalized_bbox": {left_id: [f"{v.numerator}/{v.denominator}" for v in
                                                  (Fraction(a[0])/width, Fraction(a[1])/height, Fraction(a[2])/width, Fraction(a[3])/height)],
                                       right_id: [f"{v.numerator}/{v.denominator}" for v in
                                                   (Fraction(b[0])/width, Fraction(b[1])/height, Fraction(b[2])/width, Fraction(b[3])/height)]},
                   "predicates": {"left_above_right": a_above, "right_above_left": b_above,
                                  "left_right_of_right": a_right, "right_right_of_left": b_right},
                   "tolerance": {"tau_x": "1/W", "tau_y": "1/H", "source_pixels": 1},
                   "active_pair": left_id in active and right_id in active,
                   "relation": relation, "evidence_labels": labels, "before": before, "after": after,
                   "unresolved_reason": reason}
            evidence.append(row)
            if before is not None:
                edges.append({"edge_id": f"direct:{before}:{after}", "before": before, "after": after,
                              "relation": relation, "provenance": "DIRECT", "pair_id": row["pair_id"]})
            if reason == "CONFLICTING_AXIS_EVIDENCE" and row["active_pair"]:
                conflicts.append({"panel_ids": [left_id, right_id], "reason": reason})
    active_edges = [edge for edge in edges if edge["before"] in active and edge["after"] in active]
    topo = topological_order(active, active_edges) if not conflicts else {
        "order": [], "transitive_closure": [], "topological_trace": [], "unresolved": conflicts, "resolved": False}
    direct_pairs = {(edge["before"], edge["after"]) for edge in active_edges}
    transitive = [{**row, "relation_id": f"transitive:{row['before']}:{row['after']}", "provenance": "TRANSITIVE"}
                  for row in topo["transitive_closure"] if (row["before"], row["after"]) not in direct_pairs]
    closure_pairs = direct_pairs | {(row["before"], row["after"]) for row in topo["transitive_closure"]}
    incomparable = [{"panel_ids": [a, b], "reason": "INCOMPARABLE_ACTIVE_PAIR"}
                    for i, a in enumerate(active) for b in active[i + 1:]
                    if (a, b) not in closure_pairs and (b, a) not in closure_pairs]
    unresolved = conflicts + topo["unresolved"]
    if not unresolved and incomparable:
        unresolved = incomparable
    return {"nodes": nodes, "active_nodes": active, "order": topo["order"] if not unresolved else [],
            "edges": edges, "active_edges": active_edges, "pair_evidence": evidence,
            "transitive_closure": topo["transitive_closure"], "transitive_relations": transitive,
            "topological_trace": topo["topological_trace"],
            "cycles": [row for row in unresolved if row.get("reason") == "CYCLE"],
            "unresolved": unresolved, "resolved": not unresolved,
            "representation": "EXPERIMENT_PREDECLARED_PROJECTION_CONSTRAINT_DAG_V1"}


def order_panels(panels: list[dict[str, Any]], source_dimensions: tuple[int, int] | None = None,
                 source_pixel_tolerance: int = 0) -> dict[str, Any]:
    if source_pixel_tolerance not in (0, 1):
        raise ValueError("source_pixel_tolerance must be frozen at zero or one")
    if source_pixel_tolerance and (not source_dimensions or min(source_dimensions) <= 0):
        raise ValueError("positive source dimensions are required for normalized tolerance")
    # Exact normalized comparison Ix <= 1/W and Iy <= 1/H is algebraically
    # equivalent to a one-source-pixel comparison on each source axis.
    tolerance = Decimal(source_pixel_tolerance)
    result = _partition(panels, tolerance, tolerance)
    nodes = sorted(str(panel["panel_id"]) for panel in panels)
    topo = topological_order(nodes, result.edges) if not result.unresolved else {
        "order": [], "transitive_closure": [], "topological_trace": [], "unresolved": [], "resolved": False}
    unresolved = result.unresolved + topo["unresolved"]
    return {"nodes": nodes, "order": topo["order"] if not unresolved else [], "edges": result.edges,
            "transitive_closure": topo["transitive_closure"], "topological_trace": topo["topological_trace"],
            "partitions": result.partitions, "components": result.partitions,
            "cycles": [row for row in unresolved if row.get("reason") == "CYCLE"],
            "unresolved": unresolved, "resolved": not unresolved}


def order_regions_in_panel(regions: list[dict[str, Any]]) -> dict[str, Any]:
    """Frozen Day-11 ANY-link vertical-overlap rule, RTL inside each tier."""
    def overlap(a: BBox, b: BBox) -> float:
        common = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
        return common / min(a[3] - a[1], b[3] - b[1])
    tiers: list[list[dict[str, Any]]] = []
    for item in sorted(regions, key=lambda value: (_box(value)[1], _box(value)[0], str(value["id"]))):
        eligible = [index for index, tier in enumerate(tiers) if any(overlap(_box(item), _box(peer)) >= 0.5 for peer in tier)]
        if eligible:
            tiers[eligible[0]].append(item)
        else:
            tiers.append([item])
    tiers.sort(key=lambda tier: (min(_box(item)[1] for item in tier), min(str(item["id"]) for item in tier)))
    for tier in tiers:
        tier.sort(key=lambda item: (-_box(item)[0], _box(item)[1], str(item["id"])))
    return {"order": [str(item["id"]) for tier in tiers for item in tier],
            "tiers": [[str(item["id"]) for item in tier] for tier in tiers],
            "rule": "ANY_PEER_NORMALIZED_VERTICAL_OVERLAP_GTE_0.50",
            "parameter_status": "BENCHMARK_FITTED"}


def panel_aware_order(regions: list[dict[str, Any]], panels: list[dict[str, Any]],
                      source_dimensions: tuple[int, int] | None = None,
                      source_pixel_tolerance: int = 0) -> dict[str, Any]:
    panel_result = order_panels(panels, source_dimensions, source_pixel_tolerance)
    assignment = assign_regions(regions, panels)
    unresolved = list(panel_result["unresolved"])
    unresolved += assignment["ambiguous"] + assignment["unassigned"]
    grouped = {panel["panel_id"]: [] for panel in panels}
    region_by_id = {region["id"]: region for region in regions}
    for row in assignment["assignments"]:
        grouped[row["panel_id"]].append(region_by_id[row["region_id"]])
    local = {panel_id: order_regions_in_panel(items) for panel_id, items in grouped.items()}
    sequence = [] if unresolved else [region for panel_id in panel_result["order"] for region in local[panel_id]["order"]]
    return {"status": "RESOLVED" if not unresolved else "UNRESOLVED", "sequence": sequence,
            "panel_order": panel_result, "assignment": assignment, "intra_panel": local,
            "unresolved_reasons": unresolved, "gt_runtime_features": []}


def panel_aware_projection_order(regions: list[dict[str, Any]], panels: list[dict[str, Any]],
                                 source_dimensions: tuple[int, int]) -> dict[str, Any]:
    """Offline-only 12.7 strategy; production callers retain ``panel_aware_order``."""
    assignment = assign_regions(regions, panels)
    active = {str(row["panel_id"]) for row in assignment["assignments"]}
    panel_result = projection_constraint_order(panels, source_dimensions, active)
    unresolved = list(panel_result["unresolved"]) + assignment["ambiguous"] + assignment["unassigned"]
    grouped = {str(panel["panel_id"]): [] for panel in panels}
    region_by_id = {str(region["id"]): region for region in regions}
    for row in assignment["assignments"]:
        grouped[str(row["panel_id"])].append(region_by_id[str(row["region_id"])])
    local = {panel_id: order_regions_in_panel(items) for panel_id, items in grouped.items()}
    sequence = [] if unresolved else [region for panel_id in panel_result["order"] for region in local[panel_id]["order"]]
    return {"status": "RESOLVED" if not unresolved else "UNRESOLVED", "sequence": sequence,
            "panel_order": panel_result, "assignment": assignment, "intra_panel": local,
            "unresolved_reasons": unresolved, "gt_runtime_features": []}
