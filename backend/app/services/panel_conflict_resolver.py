"""Deterministic conflict resolution over an immutable panel-candidate set."""
from __future__ import annotations

import hashlib
import json
from typing import Any

VERSION = "containment-guillotine-resolver.v1"


def _area(box: list[float]) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def _intersection(a: list[float], b: list[float]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _iou(a: list[float], b: list[float]) -> float:
    intersection = _intersection(a, b)
    return intersection / (_area(a) + _area(b) - intersection) if intersection else 0.0


def _contains(outer: list[float], inner: list[float], tolerance: float = 0.0) -> bool:
    return (outer[0] - tolerance <= inner[0] and outer[1] - tolerance <= inner[1]
            and outer[2] + tolerance >= inner[2] and outer[3] + tolerance >= inner[3])


def _contour(panel: dict[str, Any]) -> bool:
    return "border_contour" in panel.get("provenance", []) or "page_edge_completion" in panel.get("provenance", [])


def _whitespace(panel: dict[str, Any]) -> bool:
    return "whitespace_partition" in panel.get("provenance", [])


def _node_order(panel: dict[str, Any]) -> tuple:
    box = panel["bbox"]
    return box[1], box[0], box[3], box[2], panel["panel_id"]


def semantic_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_graph(panels: list[dict[str, Any]], duplicate_iou: float,
                edge_join_fraction: float) -> dict[str, Any]:
    nodes = sorted(({"panel_id": panel["panel_id"], "bbox": list(panel["bbox"]),
                     "state": panel["state"], "provenance": sorted(panel.get("provenance", [])),
                     "source_count": int(panel.get("heuristic_evidence", {}).get("source_count", 1))}
                    for panel in panels), key=_node_order)
    edges: list[dict[str, Any]] = []
    for index, first in enumerate(nodes):
        for second in nodes[index + 1:]:
            score = _iou(first["bbox"], second["bbox"])
            if score >= duplicate_iou:
                edges.append({"type": "DUPLICATE", "from": first["panel_id"], "to": second["panel_id"],
                              "iou": round(score, 6)})
                continue
            first_contains = _contains(first["bbox"], second["bbox"])
            second_contains = _contains(second["bbox"], first["bbox"])
            if first_contains or second_contains:
                outer, inner = (first, second) if first_contains else (second, first)
                edges.append({"type": "CONTAINS", "from": outer["panel_id"], "to": inner["panel_id"]})
                if _contour(outer) and _contour(inner):
                    edges.append({"type": "NESTED_INTERNAL", "from": outer["panel_id"], "to": inner["panel_id"]})
            elif _intersection(first["bbox"], second["bbox"]) > 0:
                edges.append({"type": "OVERLAPS", "from": first["panel_id"], "to": second["panel_id"],
                              "iou": round(score, 6)})
            else:
                edges.append({"type": "COMPATIBLE", "from": first["panel_id"], "to": second["panel_id"]})
    edges.sort(key=lambda edge: (edge["type"], edge["from"], edge["to"]))
    nested_children = {edge["to"] for edge in edges if edge["type"] == "NESTED_INTERNAL"}
    outer_contours = [node for node in nodes if _contour(node) and node["panel_id"] not in nested_children]
    spanning_relations = []
    for parent in nodes:
        if not _whitespace(parent):
            continue
        tolerance = max(parent["bbox"][2] - parent["bbox"][0],
                        parent["bbox"][3] - parent["bbox"][1]) * edge_join_fraction
        children = [node for node in outer_contours if node["panel_id"] != parent["panel_id"]
                    and _contains(parent["bbox"], node["bbox"], tolerance)]
        if len(children) < 2 or not _guillotine_tiles(parent["bbox"], children, tolerance):
            continue
        member_ids = sorted(node["panel_id"] for node in children)
        relation_material = {"parent_id": parent["panel_id"], "member_ids": member_ids}
        spanning_relations.append({
            "relation_id": f"SP_{semantic_hash(relation_material)[:12]}",
            "type": "SPANNING_PARENT_SUBPANEL_SET",
            "parent_id": parent["panel_id"],
            "member_ids": member_ids,
            "structural_reason": "RECURSIVE_GUILLOTINE_COMPATIBLE_SUBDIVISION",
            "evidence": {
                "parent_provenance": sorted(parent.get("provenance", [])),
                "member_provenance": {
                    node["panel_id"]: sorted(node.get("provenance", [])) for node in children
                },
                "edge_join_fraction": edge_join_fraction,
                "tolerance": tolerance,
            },
        })
    spanning_relations.sort(key=lambda relation: (relation["parent_id"], relation["member_ids"],
                                                   relation["relation_id"]))
    return {"nodes": nodes, "edges": edges, "spanning_relations": spanning_relations}


def _aligns(box: list[float], region: list[float], tolerance: float) -> bool:
    return all(abs(box[index] - region[index]) <= tolerance for index in range(4))


def _guillotine_tiles(region: list[float], panels: list[dict[str, Any]], tolerance: float) -> bool:
    if not panels:
        return False
    if len(panels) == 1:
        return _aligns(panels[0]["bbox"], region, tolerance)
    for axis in (0, 1):
        start, end = axis, axis + 2
        ordered = sorted(panels, key=lambda panel: (panel["bbox"][start], panel["bbox"][end], panel["panel_id"]))
        for split_index in range(1, len(ordered)):
            left, right = ordered[:split_index], ordered[split_index:]
            left_end = max(panel["bbox"][end] for panel in left)
            right_start = min(panel["bbox"][start] for panel in right)
            if left_end > right_start + tolerance:
                continue
            boundary = (left_end + right_start) / 2
            first_region, second_region = list(region), list(region)
            first_region[end], second_region[start] = boundary, boundary
            if _guillotine_tiles(first_region, left, tolerance) and _guillotine_tiles(second_region, right, tolerance):
                return True
    return False


def _preference(panel: dict[str, Any]) -> tuple:
    return (panel["state"] == "DETECTED", panel.get("heuristic_evidence", {}).get("source_count", 1),
            _contour(panel), _area(panel["bbox"]), tuple(panel.get("provenance", [])), panel["panel_id"])


def resolve_candidates(panels: list[dict[str, Any]], config: dict[str, float]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select an immutable subset; this function has no page/GT/pixel argument."""
    candidates = sorted((dict(panel) for panel in panels), key=_node_order)
    graph = build_graph(candidates, config["duplicate_iou"], config["edge_join_fraction"])
    by_id = {panel["panel_id"]: panel for panel in candidates}
    terminal: dict[str, dict[str, Any]] = {}

    for edge in graph["edges"]:
        if edge["type"] != "DUPLICATE":
            continue
        first, second = by_id[edge["from"]], by_id[edge["to"]]
        winner, loser = max((first, second), key=_preference), min((first, second), key=_preference)
        terminal[loser["panel_id"]] = {"status": "REJECTED", "reason": "DUPLICATE",
                                       "supporting_ids": [winner["panel_id"]]}

    active = [panel for panel in candidates if panel["panel_id"] not in terminal]
    nested = {(edge["from"], edge["to"]) for edge in graph["edges"] if edge["type"] == "NESTED_INTERNAL"}
    nested_children = {inner for _, inner in nested}
    selected_by_tiling: set[str] = set()
    spanners: dict[str, list[str]] = {}
    spanning_relation_ids: dict[str, str] = {}
    for relation in graph["spanning_relations"]:
        parent_id, ids = relation["parent_id"], relation["member_ids"]
        if parent_id in terminal or any(member_id in terminal for member_id in ids):
            continue
        spanners[parent_id] = ids
        spanning_relation_ids[parent_id] = relation["relation_id"]
        selected_by_tiling.update(ids)
        terminal[parent_id] = {"status": "REJECTED", "reason": "UNDER_SPLIT_SPANNER",
                               "supporting_ids": ids,
                               "supporting_relation_ids": [relation["relation_id"]]}

    selected: set[str] = set()
    for panel in active:
        panel_id = panel["panel_id"]
        if panel_id in terminal:
            continue
        if panel["state"] == "DETECTED":
            selected.add(panel_id)
            terminal[panel_id] = {"status": "SELECTED", "reason": "LOCKED_DETECTED", "supporting_ids": [],
                                  "supporting_relation_ids": []}
        elif panel_id in selected_by_tiling:
            selected.add(panel_id)
            terminal[panel_id] = {"status": "SELECTED", "reason": "GUILLOTINE_TILING_CHILD",
                                  "supporting_ids": sorted(parent for parent, children in spanners.items() if panel_id in children),
                                  "supporting_relation_ids": sorted(spanning_relation_ids[parent] for parent, children in spanners.items()
                                                                    if panel_id in children)}
        elif _contour(panel) and _whitespace(panel) and panel.get("heuristic_evidence", {}).get("source_count", 1) >= 2:
            selected.add(panel_id)
            terminal[panel_id] = {"status": "SELECTED", "reason": "MULTI_SOURCE_ATOMIC", "supporting_ids": [],
                                  "supporting_relation_ids": []}

    for outer, inner in sorted(nested):
        if inner not in terminal and outer in selected:
            terminal[inner] = {"status": "REJECTED", "reason": "NESTED_INTERNAL_FRAGMENT",
                               "supporting_ids": [outer], "supporting_relation_ids": []}
    for panel in active:
        if panel["panel_id"] not in terminal:
            terminal[panel["panel_id"]] = {"status": "UNRESOLVED", "reason": "CONFLICT_NOT_RESOLVED",
                                            "supporting_ids": [], "supporting_relation_ids": []}

    results = []
    for panel in candidates:
        result = terminal[panel["panel_id"]]
        results.append({"panel_id": panel["panel_id"], "bbox": list(panel["bbox"]),
                        "input_state": panel["state"], "resolution_status": result["status"],
                        "reason": result["reason"], "supporting_ids": result["supporting_ids"],
                        "supporting_relation_ids": result.get("supporting_relation_ids", []),
                        "provenance": list(panel.get("provenance", []))})
    output = {"resolver_version": VERSION, "gt_runtime_features": [], "candidates": results,
              "selected_panel_ids": sorted(selected),
              "unresolved": not bool(selected), "geometry_mutated": False}
    return graph, output
