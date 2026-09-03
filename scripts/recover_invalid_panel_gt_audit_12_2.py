"""Recover invalid Panel GT audit evidence from a persisted pre-reset session log."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks/day12/panel-human-gt-invalid-coordinate-audit-12.2.json"
INPUT_AUDIT = ROOT / "benchmarks/day12/panel-extraction-input-audit-12.2.json"
PREDICTIONS = ROOT / "benchmarks/day12/panel-predictions-12.2.json"
OLD_SNAPSHOT = "d49cc0aab140a743317bbb36a3f53a74ecf1c2305f279ccb75d306855e9e3b1c"
PAGES = (1, 2, 15, 17)


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def logged_output(path: Path, call_id: str) -> tuple[str, int]:
    for line_number, line in enumerate(path.open(encoding="utf-8"), 1):
        event = json.loads(line)
        payload = event.get("payload", {})
        if payload.get("type") != "custom_tool_call_output" or payload.get("call_id") != call_id:
            continue
        chunks = payload.get("output", [])
        return "".join(chunk.get("text", "") for chunk in chunks), line_number
    raise RuntimeError(f"Direct database output {call_id} not found")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_log", type=Path)
    parser.add_argument("--call-id", default="call_IEj8hODYlCmDDCIfnblRzba4")
    args = parser.parse_args()
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to overwrite {OUTPUT}")
    raw, line_number = logged_output(args.session_log, args.call_id)
    recovered: dict[int, list[dict]] = {}
    for match in re.finditer(r"^PAGE (1|2|15|17) human (\[.*\])$", raw, re.MULTILINE):
        recovered[int(match.group(1))] = ast.literal_eval(match.group(2))
    if tuple(sorted(recovered)) != PAGES or [len(recovered[p]) for p in PAGES] != [3, 2, 3, 5]:
        raise SystemExit("Persisted log does not contain the exact expected 13 annotations")

    inputs = {int(item["page_order"]): item for item in
              json.loads(INPUT_AUDIT.read_text(encoding="utf-8"))["inputs"]}
    pages, snapshot_material = [], []
    for page_order in PAGES:
        source = inputs[page_order]
        review_id = f"panel-gt-12.2:{source['asset_id']}"
        panels = recovered[page_order]
        snapshot_material.append({"id": review_id, "state": "VERIFIED", "revision": 1,
                                  "panels": panels, "hash": source["source_hash"]})
        pages.append({"page_order": page_order, "review_id": review_id,
                      "benchmark_asset_id": source["asset_id"], "source_image_hash": source["source_hash"],
                      "image_dimensions": source["image_dimensions"], "original_panel_count": len(panels),
                      "original_state": "VERIFIED", "original_revision": 1, "original_boxes": panels})
    reproduced = canonical_hash(snapshot_material)
    if reproduced != OLD_SNAPSHOT:
        raise SystemExit(f"Recovered annotations do not reproduce old snapshot: {reproduced}")

    audit = {
        "schema_version": "panel-human-gt-invalid-coordinate-audit.v1",
        "checkpoint": "12.2",
        "status": "INVALID_COORDINATE_SYSTEM",
        "authority": "NOT AUTHORITATIVE GT",
        "affected_pages": list(PAGES),
        "original_panel_counts": {str(page): len(recovered[page]) for page in PAGES},
        "original_annotation_count": sum(map(len, recovered.values())),
        "invalidity_reason": "All boxes were captured against the full UI surface instead of the object-contained image.",
        "coordinate_system_bug": "Horizontal letterbox offset/padding was treated as source-image coordinates, compressing annotations to about 37% of source width.",
        "pages": pages,
        "original_gt_snapshot_sha256": OLD_SNAPSHOT,
        "reproduced_gt_snapshot_sha256": reproduced,
        "snapshot_verification": "EXACT_MATCH",
        "recovery_provenance": {
            "kind": "PERSISTED_PRE_RESET_DIRECT_DATABASE_QUERY_LOG",
            "session_log": str(args.session_log),
            "session_log_sha256": hashlib.sha256(args.session_log.read_bytes()).hexdigest(),
            "jsonl_line": line_number,
            "tool_call_id": args.call_id,
            "method": "Parsed the literal Human panel arrays from the recorded SQLAlchemy query output; no bbox was inferred or transformed. Source identity came from the frozen 12.2 input audit."
        },
        "old_gt_active": False,
        "new_gt_used_for_recovery": False,
        "frozen_prediction_file_sha256": hashlib.sha256(PREDICTIONS.read_bytes()).hexdigest(),
        "frozen_predictions_modified": False,
    }
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": audit["status"], "annotations": 13,
                      "snapshot": reproduced, "output": str(OUTPUT.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
