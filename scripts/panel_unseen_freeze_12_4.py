"""Freeze Checkpoint 12.4 unseen panel predictions before Human GT exists."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.deterministic_panel_extractor import PanelConfig, REVISION, extract_panels  # noqa: E402
from app.services.panel_conflict_resolver import VERSION, resolve_candidates, semantic_hash  # noqa: E402
from app.services.resource_safety import ResourceThresholds, sample_resources  # noqa: E402

DAY12 = ROOT / "benchmarks/day12"
SOURCE_AUDIT = DAY12 / "panel-extraction-input-audit-12.2.json"
EXTRACTION_PROTOCOL = DAY12 / "panel-extraction-protocol-12.2.json"
FROZEN_12_2 = DAY12 / "panel-predictions-12.2.json"
RESOLUTION_PROTOCOL = DAY12 / "panel-conflict-resolution-protocol-12.3.json"
SELECTION_PATH = DAY12 / "panel-unseen-selection-12.4.json"
PROTOCOL_PATH = DAY12 / "panel-unseen-protocol-12.4.json"
RAW_PATH = DAY12 / "panel-unseen-raw-candidates-12.4.json"
GRAPH_PATH = DAY12 / "panel-unseen-conflict-graph-12.4.json"
OUTPUT_PATH = DAY12 / "panel-unseen-resolution-output-12.4.json"
FREEZE_PATH = DAY12 / "panel-unseen-prediction-freeze-12.4.json"

PAGES = (3, 4, 5, 7, 18, 38)
EXCLUDED = (1, 2, 15, 17)
EXTRACTOR_SHA = "681968c45afd1db8947ff66d436c84db9e72425256d68b407dc55197553ff311"
RESOLVER_SHA = "88a0de382bc5241153b0899bb2b023c9761a9cd3426801ad376ee6367b7477b3"
SOURCE_AUDIT_SHA = "ec456284c30b6aea909fc75957147d839ca293e9fb0ac5389228ffaba338a75c"
FROZEN_12_2_SHA = "80e46d5c6216e3d18e9686af149a0012911795a246d1323ae4bb74d516b4b735"
EXPECTED = {
    3: ("58ac011e-7a3a-44ba-a8c5-ba7977a78b95", "ecc4798a1fd62c36af8e401b80a0ef67e36dfafbb69ac809f1f41e88f6b9676d"),
    4: ("dab0676a-07e3-4195-b20c-511f57e3ddc6", "95cb90cb0c70a19b2f40401799a0ae5648e177fdde66690a580c80a831a824b4"),
    5: ("69f9acdd-e51f-4be2-90dd-cbc7e5882aa7", "8a44656d3dc2eef04c0bb3c9daf758373a2b0d12cc1669c63937ebdb4c333067"),
    7: ("b2b89e05-fb47-4b90-877c-6ced851bc7de", "05f78f1eba0068e0c787185864a7764a3c8d20c265c94344ee897e26a7dc8309"),
    18: ("23ab72f6-0910-49d0-a167-3bd170ea3b23", "8cac650842de985ede0be45715eed9ebb48f842e7a5def7bc5203b8ceff2c240"),
    38: ("522c50f5-5934-40be-9cc2-f452deeeff35", "969152a0288a5680d74205f90226a0164523fc82fb66cdc145eba0f25ab07e30"),
}
STRUCTURAL_COVERAGE = [
    "ORDINARY_ADJACENT_PANELS", "HORIZONTAL_VERTICAL_DIVISIONS", "SPANNING_ROW_OPPORTUNITIES",
    "TALL_BESIDE_STACKED", "NESTED_INTERNAL_CONTOUR_OPPORTUNITIES", "PAGE_EDGE_STRUCTURE",
    "DIFFICULT_IRREGULAR_OR_UNRESOLVED",
]


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def semantic_artifact(payload: dict) -> dict:
    result = dict(payload)
    result["semantic_sha256"] = semantic_hash(result)
    return result


def verified_selection() -> tuple[list[dict], dict[int, np.ndarray]]:
    if file_sha(SOURCE_AUDIT) != SOURCE_AUDIT_SHA:
        raise SystemExit("Frozen source audit changed")
    audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    audit_by_page = {int(item["page_order"]): item for item in audit["inputs"]}
    if set(audit_by_page) != set(PAGES + EXCLUDED) or set(PAGES) != set(audit_by_page) - set(EXCLUDED):
        raise SystemExit("Unseen cohort is not the exhaustive frozen complement")
    selected, pixels = [], {}
    for page_order in PAGES:
        item = audit_by_page[page_order]
        asset_id, source_hash = EXPECTED[page_order]
        source_path = ROOT / item["resolved_path"]
        if (item["asset_id"], item["source_hash"], item["image_dimensions"]) != (asset_id, source_hash, [900, 1280]):
            raise SystemExit(f"Frozen identity mismatch for Page {page_order}")
        if not source_path.is_file() or file_sha(source_path) != source_hash:
            raise SystemExit(f"Source bytes mismatch for Page {page_order}")
        with Image.open(source_path) as image:
            rgb = np.asarray(image.convert("RGB"))
        if [rgb.shape[1], rgb.shape[0]] != [900, 1280]:
            raise SystemExit(f"Source dimensions mismatch for Page {page_order}")
        selected.append({"page_order": page_order, "asset_id": asset_id, "source_path": item["resolved_path"],
                         "source_sha256": source_hash, "image_dimensions": [900, 1280]})
        pixels[page_order] = rgb
    return selected, pixels


def main() -> None:
    resources_before = sample_resources(ResourceThresholds.from_environment())
    if resources_before["safety_state"] != "NORMAL":
        raise SystemExit("Resource Guard is not NORMAL")
    extractor_path = ROOT / "backend/app/services/deterministic_panel_extractor.py"
    resolver_path = ROOT / "backend/app/services/panel_conflict_resolver.py"
    if file_sha(extractor_path) != EXTRACTOR_SHA or file_sha(resolver_path) != RESOLVER_SHA:
        raise SystemExit("Approved extractor/resolver code changed")
    selected, pixels = verified_selection()
    selection = semantic_artifact({
        "schema_version": "panel-unseen-selection.v1", "checkpoint": "12.4",
        "selection_rule": "EXHAUSTIVE_ASCENDING_COMPLEMENT_OF_FROZEN_TEN_PAGE_SET",
        "correctness_blind": True, "selected_pages": list(PAGES), "excluded_pages": list(EXCLUDED),
        "source_audit_file_sha256": SOURCE_AUDIT_SHA, "structural_coverage": STRUCTURAL_COVERAGE,
        "pages": selected, "gt_runtime_features": [],
    })
    write(SELECTION_PATH, selection)

    extraction_protocol = json.loads(EXTRACTION_PROTOCOL.read_text(encoding="utf-8"))
    resolution_protocol = json.loads(RESOLUTION_PROTOCOL.read_text(encoding="utf-8"))
    config = PanelConfig(**extraction_protocol["configuration"])
    resolver_config = resolution_protocol["configuration"]
    protocol = semantic_artifact({
        "schema_version": "panel-unseen-protocol.v1", "checkpoint": "12.4",
        "mode": "PRE_HUMAN_GENERALIZATION_FREEZE_NO_CALIBRATION",
        "phase_order": ["FREEZE_SELECTION", "FREEZE_PROTOCOL", "EXTRACT_TWICE", "RESOLVE_TWICE",
                        "FREEZE_RAW_GRAPH_OUTPUT", "FREEZE_MANIFEST", "CREATE_HUMAN_QUEUE"],
        "extractor_revision": REVISION, "extractor_sha256": EXTRACTOR_SHA,
        "extractor_configuration": config.payload(), "resolver_version": VERSION,
        "resolver_sha256": RESOLVER_SHA, "resolver_configuration": resolver_config,
        "matching_protocol_post_human_only": "UNCHANGED_ONE_TO_ONE_IOU_0.50",
        "outcome_gates": {
            "A": {"false_promoted": 0, "precision": 1.0, "min_recall": 0.60,
                  "min_f1": 0.75, "max_unresolved_pages": 2},
            "B": {"min_precision": 0.90, "max_false_promoted": 1, "min_recall": 0.35},
        },
        "failure_taxonomy": ["MISSING_CANDIDATE_GENERATION", "CONFLICT_RESOLUTION", "UNDER_SPLITTING",
                             "OVER_SPLITTING", "CONTOUR_NOISE", "BORDERLESS_PANEL", "PAGE_EDGE_STRUCTURE",
                             "IRREGULAR_GEOMETRY", "AMBIGUITY_POLICY", "OTHER_EVIDENCE_SUPPORTED"],
        "gt_runtime_features": [], "human_gt_access": False, "reading_order_run": False,
        "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0},
    })
    write(PROTOCOL_PATH, protocol)

    def extract_once() -> list[dict]:
        return [{"page_order": page_order,
                 "asset_id": next(item["asset_id"] for item in selected if item["page_order"] == page_order),
                 "source_hash": EXPECTED[page_order][1], **extract_panels(pixels[page_order], config)}
                for page_order in PAGES]

    first_raw, second_raw = extract_once(), extract_once()
    if first_raw != second_raw:
        raise SystemExit("Extractor nondeterminism")
    frozen = json.loads(FROZEN_12_2.read_text(encoding="utf-8"))
    frozen_subset = [page for page in frozen["pages"] if page["page_order"] in PAGES]
    if first_raw != frozen_subset or file_sha(FROZEN_12_2) != FROZEN_12_2_SHA:
        raise SystemExit("12.4 candidates do not reproduce frozen 12.2 subset")
    raw = semantic_artifact({"schema_version": "panel-unseen-raw-candidates.v1", "checkpoint": "12.4",
                             "pages": first_raw, "gt_runtime_features": []})

    def resolve_once() -> tuple[list[dict], list[dict]]:
        graph_pages, output_pages = [], []
        for page in first_raw:
            graph, output = resolve_candidates(page["panels"], resolver_config)
            graph_pages.append({"page_order": page["page_order"], "source_hash": page["source_hash"], **graph})
            output_pages.append({"page_order": page["page_order"], "source_hash": page["source_hash"], **output})
        return graph_pages, output_pages

    first_graph, first_output = resolve_once()
    second_graph, second_output = resolve_once()
    if (first_graph, first_output) != (second_graph, second_output):
        raise SystemExit("Resolver nondeterminism")
    for raw_page, output_page in zip(first_raw, first_output, strict=True):
        source_boxes = {panel["panel_id"]: panel["bbox"] for panel in raw_page["panels"]}
        emitted_boxes = {item["panel_id"]: item["bbox"] for item in output_page["candidates"]}
        if source_boxes != emitted_boxes or output_page["geometry_mutated"]:
            raise SystemExit("Resolver output geometry changed")
    graph = semantic_artifact({"schema_version": "panel-unseen-conflict-graph.v1", "checkpoint": "12.4",
                               "pages": first_graph, "gt_runtime_features": []})
    output = semantic_artifact({"schema_version": "panel-unseen-resolution-output.v1", "checkpoint": "12.4",
                                "pages": first_output, "gt_runtime_features": []})
    write(RAW_PATH, raw); write(GRAPH_PATH, graph); write(OUTPUT_PATH, output)
    freeze = semantic_artifact({
        "schema_version": "panel-unseen-prediction-freeze.v1", "checkpoint": "12.4",
        "status": "FROZEN_BEFORE_HUMAN_GT", "selected_pages": list(PAGES),
        "selection_file_sha256": file_sha(SELECTION_PATH), "selection_semantic_sha256": selection["semantic_sha256"],
        "protocol_file_sha256": file_sha(PROTOCOL_PATH), "protocol_semantic_sha256": protocol["semantic_sha256"],
        "raw_file_sha256": file_sha(RAW_PATH), "raw_semantic_sha256": raw["semantic_sha256"],
        "graph_file_sha256": file_sha(GRAPH_PATH), "graph_semantic_sha256": graph["semantic_sha256"],
        "output_file_sha256": file_sha(OUTPUT_PATH), "output_semantic_sha256": output["semantic_sha256"],
        "extractor_two_run_identical": True, "resolver_two_run_identical": True,
        "frozen_12_2_subset_identical": True, "bbox_subset_and_identity": True,
        "human_gt_imported_or_queried": False, "human_queue_created": False,
        "gt_runtime_features": [], "reading_order_run": False,
        "model_calls": {"ocr": 0, "vlm": 0, "ollama": 0}, "resource_guard": "NORMAL",
    })
    write(FREEZE_PATH, freeze)
    if sample_resources(ResourceThresholds.from_environment())["safety_state"] != "NORMAL":
        raise SystemExit("Resource Guard changed")
    print(json.dumps({"status": freeze["status"], "pages": list(PAGES),
                      "prediction_fingerprint": freeze["semantic_sha256"], "resource_guard": "NORMAL"}))


if __name__ == "__main__":
    main()
