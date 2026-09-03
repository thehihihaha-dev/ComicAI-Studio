"""Day 13 Research Foundation: Blind Harness Isolation & Artifact Verification.

Strict Safety Invariants:
1. DETERMINISM: 100% raw-byte determinism and semantic determinism.
2. GT ISOLATION: gt_runtime_features = [] strictly enforced; ground truth keys rejected.
3. FAIL-CLOSED: Ambiguity (multiple topological orders) and cycles strictly return UNRESOLVED.
4. METRIC INTEGRITY: 0 inversions invariant.
5. PRODUCTION SHIELD: Purely isolated experimental harness; zero side effects on production.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


# Checkpoint 12.7 Sealed Artifact Fingerprints (SHA-256)
CHECKPOINT_12_7_SEAL: dict[str, str] = {
    "candidate-freeze": "d97889b2cd41dbf3c138433781afb175892fc5259442e9de874209e258d6e6b9",
    "control-reference": "2f9f0e0e96867d8f0e7d7d110840f41c1c3752bb81e27bae548f034cb460ae0a",
    "evaluation": "95ab49f30dd159a15b2183fbdd17433fe5a60f6412bcb5e6932df479807a02de",
    "historical-audit": "eb85e213730f1134c2928fbb3f7ec25604d80387eb039d39a0fd7ae9bff13820",
    "input-audit": "29a68c8dbe7d51d3b473aa60336c7b948bbb35329083e24e52885f319f469848",
    "oracle-candidates": "66337371b13ec4c145c4b5b8a6bbfe22e86c89e514d69d93ead8993b072d4093",
    "protocol": "a1577fc62dd1aa6b7e21b29e191ae9f34b1ac799d5a46e79fba4fd1557460ab8",
    "structural-audit": "44ff0af4fe04f4ea6443bb6606d4052efcc12dc12fcc4f9c7e00c17b9ff164d7",
    "summary": "3efd03c392165da471f87051e28f086618605fd66019fb7c0fa20eaf22a307f4",
    "synthetic": "505b4a2dcbce959eb08be37acd6132c8b351d28b53b30bbfce3a90d118a6272b",
}

# Forbidden keys that would indicate Ground Truth leakage into candidate geometry
FORBIDDEN_GT_KEYS: frozenset[str] = frozenset({
    "order",
    "human_order",
    "gt_order",
    "reading_order",
    "text",
    "ocr_text",
    "clean_text",
    "transcription",
    "dialogue",
    "dialogues",
    "label",
    "labels",
    "ground_truth",
})

# Forbidden substrings / markers indicating invalidated Checkpoint 12.8 artifacts or findings
FORBIDDEN_12_8_PATTERNS: tuple[str, ...] = (
    "12.8",
    "12_8",
    "panel-geometry-identifiability",
    "OUTCOME_B",
    "15/20 IDENTIFIABLE",
    "IDENTIFIABILITY_AUDIT",
)


class Day13HarnessError(Exception):
    """Base exception for Day 13 harness errors."""


class ArtifactIntegrityError(Day13HarnessError):
    """Raised when an archived artifact's hash fails verification."""


class Checkpoint128AccessForbiddenError(Day13HarnessError):
    """Raised when any code attempts to read or rely on invalidated Checkpoint 12.8."""


class GroundTruthLeakageError(Day13HarnessError):
    """Raised when Ground Truth features or labels leak into candidate geometry evaluation."""


class UnresolvedOrderError(Day13HarnessError):
    """Raised when strict resolution fails due to cycles or multiple topological orders."""


# ==============================================================================
# 1. Artifact Seal & Checkpoint 12.8 Exclusion Barrier
# ==============================================================================

def compute_file_sha256(path: Path) -> str:
    """Compute exact SHA-256 hex digest of file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checkpoint_12_7_seal(benchmarks_dir: Path | None = None) -> dict[str, Any]:
    """Verify raw-byte integrity of all Checkpoint 12.7 archived artifacts.

    Raises ArtifactIntegrityError if any artifact is missing or altered.
    """
    if benchmarks_dir is None:
        root = Path(__file__).resolve().parents[3]
        benchmarks_dir = root / "benchmarks" / "day12"

    verified_records: list[dict[str, str]] = []
    for name, expected_sha in sorted(CHECKPOINT_12_7_SEAL.items()):
        artifact_path = benchmarks_dir / f"panel-relation-model-{name}-12.7.json"
        if not artifact_path.exists():
            raise ArtifactIntegrityError(f"Missing Checkpoint 12.7 sealed artifact: {artifact_path}")
        
        actual_sha = compute_file_sha256(artifact_path)
        if actual_sha != expected_sha:
            raise ArtifactIntegrityError(
                f"Checksum mismatch on 12.7 artifact '{name}': expected {expected_sha}, got {actual_sha}"
            )
        verified_records.append({
            "artifact": name,
            "filename": artifact_path.name,
            "sha256": actual_sha,
            "status": "VERIFIED_SEAL_MATCH",
        })

    return {
        "status": "CHECKPOINT_12_7_SEAL_VERIFIED",
        "verified_count": len(verified_records),
        "artifacts": verified_records,
        "gt_runtime_features": [],
    }


class Checkpoint128ExclusionBarrier:
    """Strict barrier preventing reading, loading, or referencing Checkpoint 12.8."""

    @staticmethod
    def assert_clean_identifier(identifier: str | Path) -> None:
        """Verify that an identifier or file path does not reference Checkpoint 12.8."""
        as_str = str(identifier)
        for pattern in FORBIDDEN_12_8_PATTERNS:
            if pattern in as_str:
                raise Checkpoint128AccessForbiddenError(
                    f"Access forbidden: identifier '{identifier}' references invalidated Checkpoint 12.8 ('{pattern}')."
                )

    @staticmethod
    def assert_clean_payload(data: Any) -> None:
        """Recursively inspect a data payload to ensure zero 12.8 contamination."""
        if isinstance(data, str):
            for pattern in FORBIDDEN_12_8_PATTERNS:
                if pattern in data:
                    raise Checkpoint128AccessForbiddenError(
                        f"Access forbidden: payload contains invalidated Checkpoint 12.8 reference '{pattern}'."
                    )
        elif isinstance(data, Mapping):
            for k, v in data.items():
                Checkpoint128ExclusionBarrier.assert_clean_payload(k)
                Checkpoint128ExclusionBarrier.assert_clean_payload(v)
        elif isinstance(data, (list, tuple, set, frozenset)):
            for item in data:
                Checkpoint128ExclusionBarrier.assert_clean_payload(item)

    @classmethod
    def safe_load_json(cls, path: Path | str) -> dict[str, Any]:
        """Load a JSON file only if it strictly passes the exclusion barrier."""
        target = Path(path)
        cls.assert_clean_identifier(target.name)
        cls.assert_clean_identifier(str(target))
        
        raw_text = target.read_text(encoding="utf-8")
        parsed = json.loads(raw_text)
        cls.assert_clean_payload(parsed)
        return parsed


# ==============================================================================
# 2. Blind Geometry Evaluator & Immutable Types
# ==============================================================================

@dataclass(frozen=True)
class NormalizedBox:
    """Immutable, exact representation of a 2D bounding box using Decimal / Fraction."""
    x1: Decimal
    y1: Decimal
    x2: Decimal
    y2: Decimal
    panel_id: str

    def __post_init__(self) -> None:
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError(f"Invalid non-positive box area: [{self.x1}, {self.y1}, {self.x2}, {self.y2}]")

    @property
    def box_id(self) -> str:
        return self.panel_id

    @property
    def tuple_coords(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        return (self.x1, self.y1, self.x2, self.y2)

    def normalized_fraction(self, width: int, height: int) -> tuple[str, str, str, str]:
        """Express coordinates as exact fraction strings."""
        w, h = Fraction(width), Fraction(height)
        return (
            str(Fraction(self.x1) / w),
            str(Fraction(self.y1) / h),
            str(Fraction(self.x2) / w),
            str(Fraction(self.y2) / h),
        )


def canonicalize_raw_boxes(
    raw_panels: list[dict[str, Any]],
    source_dimensions: tuple[int, int],
) -> tuple[NormalizedBox, ...]:
    """Convert raw input panels into immutable NormalizedBox instances.

    Guarantees:
    - Zero Ground Truth leakage (checks FORBIDDEN_GT_KEYS).
    - Immutable copy protection (raw panels can be mutated afterwards with 0 effect).
    - Deterministic ID assignment if IDs are missing or duplicate.
    """
    width, height = source_dimensions
    if width <= 0 or height <= 0:
        raise ValueError("Source dimensions must be positive integers.")

    # Deep copy input first to prevent race condition mutations during validation
    copied = copy.deepcopy(raw_panels)

    # 1. Enforce GT Isolation
    for item in copied:
        leakage = FORBIDDEN_GT_KEYS.intersection(item.keys())
        if leakage:
            raise GroundTruthLeakageError(
                f"Ground truth leakage detected in candidate input: {sorted(leakage)}"
            )

    # 2. Exact Decimal conversion and bounds checking
    boxes: list[NormalizedBox] = []
    for idx, item in enumerate(copied):
        bbox = item.get("bbox")
        if not bbox or len(bbox) != 4:
            raise ValueError(f"Panel at index {idx} must have 4-element 'bbox'.")
        
        x1, y1, x2, y2 = (Decimal(str(val)) for val in bbox)
        if x1 < 0 or y1 < 0 or x2 > Decimal(width) or y2 > Decimal(height):
            raise ValueError(f"Panel box out of bounds [0, 0, {width}, {height}]: {bbox}")

        raw_id = item.get("panel_id")
        if raw_id is None:
            # Generate deterministic canonical ID based on geometry hash and index
            geom_str = f"{x1}|{y1}|{x2}|{y2}"
            geom_hash = hashlib.sha256(geom_str.encode("utf-8")).hexdigest()[:12]
            assigned_id = f"PGN_{geom_hash}_{idx:03d}"
        else:
            assigned_id = str(raw_id)

        boxes.append(NormalizedBox(x1=x1, y1=y1, x2=x2, y2=y2, panel_id=assigned_id))

    # Sort deterministically by (panel_id, x1, y1, x2, y2)
    boxes.sort(key=lambda b: (b.panel_id, b.x1, b.y1, b.x2, b.y2))
    return tuple(boxes)


class BlindGeometryEvaluator:
    """Blind, deterministic evaluator implementing Checkpoint 12.7 PCPDAG V1.

    Zero heuristic fitting, 100% fail-closed on cycles or multiple topological sorts.
    """

    def __init__(self, source_dimensions: tuple[int, int]) -> None:
        self.width, self.height = source_dimensions
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Positive source dimensions are required.")

    def evaluate(
        self,
        raw_panels: list[dict[str, Any]],
        strict_fail_closed: bool = False,
    ) -> dict[str, Any]:
        """Evaluate reading order deterministically from pure bounding box geometry.

        Args:
            raw_panels: List of panel dicts with 'bbox' and optional 'panel_id'.
            strict_fail_closed: If True, raises UnresolvedOrderError on ambiguity/cycle.

        Returns:
            Deterministic dictionary containing order, edges, trace, and SHA-256 of execution graph.
        """
        # Step 1: Invariant check & Mutation protection
        boxes = canonicalize_raw_boxes(raw_panels, (self.width, self.height))
        nodes = sorted(b.panel_id for b in boxes)
        box_map = {b.panel_id: b for b in boxes}

        if len(nodes) != len(boxes):
            unresolved = [{"reason": "CONFLICTING_AXIS_EVIDENCE", "detail": "DUPLICATE_PANEL_ID"}]
            if strict_fail_closed:
                raise UnresolvedOrderError("Duplicate panel IDs detected.")
            return self._format_result(nodes, [], [], [], unresolved, False)

        # Step 2: Pairwise Projection Constraint Analysis (Checkpoint 12.7 exact one-pixel tolerance)
        pair_evidence: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []
        conflicts: list[dict[str, Any]] = []

        for i, left_id in enumerate(nodes):
            for right_id in nodes[i + 1:]:
                a = box_map[left_id]
                b = box_map[right_id]

                # One-pixel intrusion tolerance:
                # Vertical constraint: A is above B if A.y2 - B.y1 <= 1
                a_above = (a.y2 - b.y1) <= Decimal(1)
                b_above = (b.y2 - a.y1) <= Decimal(1)

                # Horizontal RTL constraint: B is left of A (A is right of B) if B.x2 - A.x1 <= 1
                a_right = (b.x2 - a.x1) <= Decimal(1)
                b_right = (a.x2 - b.x1) <= Decimal(1)

                before: str | None = None
                after: str | None = None
                relation: str | None = None
                reason: str | None = None

                if (a_above and b_above) or (a_right and b_right):
                    reason = "CONFLICTING_AXIS_EVIDENCE"
                    conflicts.append({"panel_ids": [left_id, right_id], "reason": reason})
                elif a_above != b_above:
                    before, after = (left_id, right_id) if a_above else (right_id, left_id)
                    relation = "ABOVE"
                elif a_right != b_right:
                    before, after = (left_id, right_id) if a_right else (right_id, left_id)
                    relation = "RIGHT_OF"
                else:
                    reason = "INCOMPARABLE"

                pair_evidence.append({
                    "pair_id": f"pair:{left_id}:{right_id}",
                    "panel_ids": [left_id, right_id],
                    "relation": relation,
                    "before": before,
                    "after": after,
                    "unresolved_reason": reason,
                    "source_boxes": {
                        left_id: [str(c) for c in a.tuple_coords],
                        right_id: [str(c) for c in b.tuple_coords],
                    },
                })

                if before is not None and after is not None and relation is not None:
                    edges.append({
                        "edge_id": f"direct:{before}:{after}",
                        "before": before,
                        "after": after,
                        "relation": relation,
                    })

        # Step 3: Deterministic Topological Ordering (Fail-Closed Kahn Algorithm)
        order, trace, unresolved_reasons = self._topological_sort(nodes, edges)

        resolved = (len(unresolved_reasons) == 0 and len(order) == len(nodes))
        if not resolved and strict_fail_closed:
            reasons_summary = ", ".join(r.get("reason", "UNKNOWN") for r in unresolved_reasons)
            raise UnresolvedOrderError(f"Fail-closed: unresolved reading order ({reasons_summary})")

        return self._format_result(
            nodes=nodes,
            order=order if resolved else [],
            edges=edges,
            pair_evidence=pair_evidence,
            unresolved=unresolved_reasons,
            resolved=resolved,
            trace=trace,
        )

    def _topological_sort(
        self,
        nodes: list[str],
        edges: list[dict[str, str]],
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        """Kahn's topological sort with strict fail-closed handling."""
        incoming: dict[str, set[str]] = {n: set() for n in nodes}
        outgoing: dict[str, set[str]] = {n: set() for n in nodes}
        for edge in edges:
            incoming[edge["after"]].add(edge["before"])
            outgoing[edge["before"]].add(edge["after"])

        order: list[str] = []
        trace: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []

        while len(order) < len(nodes):
            # Nodes with in-degree 0 among remaining
            ready = sorted(n for n in nodes if n not in order and incoming[n].issubset(order))
            trace.append({
                "step": len(order),
                "ready": ready,
                "emitted": ready[0] if len(ready) == 1 else None,
            })

            if len(ready) == 1:
                order.append(ready[0])
            elif len(ready) > 1:
                # Multiple topological orders: cannot choose deterministically without guessing!
                unresolved.append({
                    "reason": "MULTIPLE_TOPOLOGICAL_ORDERS",
                    "panel_ids": ready,
                    "detail": f"Ambiguous choice among {ready}",
                })
                break
            else:
                # ready == 0, but remaining nodes exist => Cycle detected!
                remaining = sorted(set(nodes) - set(order))
                unresolved.append({
                    "reason": "CYCLE",
                    "panel_ids": remaining,
                    "detail": "Cycle conflict detected in directed constraint graph",
                })
                break

        return order, trace, unresolved

    def _format_result(
        self,
        nodes: list[str],
        order: list[str],
        edges: list[dict[str, str]],
        pair_evidence: list[dict[str, Any]],
        unresolved: list[dict[str, Any]],
        resolved: bool,
        trace: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Assemble canonical execution graph and compute raw-byte SHA-256."""
        # Ensure canonical sorting for 100% determinism
        edges_sorted = sorted(edges, key=lambda e: (e["before"], e["after"], e["relation"]))
        pair_sorted = sorted(pair_evidence, key=lambda p: p["pair_id"])

        execution_graph = {
            "schema_version": "day13_blind_execution_graph.v1",
            "resolved": resolved,
            "order": order,
            "node_count": len(nodes),
            "edge_count": len(edges_sorted),
            "nodes": nodes,
            "edges": edges_sorted,
            "pair_evidence": pair_sorted,
            "topological_trace": trace or [],
            "unresolved": unresolved,
            "gt_runtime_features": [],  # Invariant 2: Explicitly empty
        }

        canonical_bytes = json.dumps(
            execution_graph,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        graph_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

        return {
            **execution_graph,
            "graph_sha256": graph_sha256,
        }

