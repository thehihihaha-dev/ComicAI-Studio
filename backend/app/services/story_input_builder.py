import json
import re
from typing import Any

from app.database import SessionLocal
from app.models.asset import Asset
from app.models.project import Project
from app.services.asset_processor import (
    ASSET_STATUS_EXCLUDED,
    ASSET_STATUS_READY,
)


CONTRACT_VERSION = "story_input.v1"
SUPPORTED_DIALOGUE_DECISIONS = {
    "auto_accepted",
    "auto_recovered",
    "verified",
}
def get_authoritative_dialogue_text(
    dialogue: dict[str, Any],
) -> tuple[str | None, str | None]:
    decision = dialogue.get("decision")
    human_verified = dialogue.get("human_verified") is True

    if decision == "verified" or human_verified:
        verified_text = _non_empty_text(dialogue.get("verified_text"))
        return (
            (verified_text, "verified")
            if verified_text is not None
            else (None, None)
        )

    recovered_text = _non_empty_text(dialogue.get("recovered_text"))
    if recovered_text is not None:
        return recovered_text, "recovered"

    clean_text = _non_empty_text(dialogue.get("clean_text"))
    if clean_text is not None:
        return clean_text, "clean"

    return None, None


def build_story_input_from_assets(
    project_id: str,
    assets: list[Asset],
) -> dict[str, Any]:
    ordered_assets = sorted(
        assets,
        key=lambda asset: (asset.page_order, str(asset.id)),
    )
    issues: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    prepared_pages: list[dict[str, Any]] = []

    if not ordered_assets:
        return _empty_story_input(
            project_id=project_id,
            status="empty",
            issues=[
                {
                    "code": "project_has_no_assets",
                    "message": "Project has no source assets.",
                }
            ],
            total_assets=0,
        )

    page_orders: set[int] = set()

    for asset in ordered_assets:
        if asset.status == ASSET_STATUS_EXCLUDED:
            issues.append(
                _asset_issue(
                    asset,
                    code="asset_excluded",
                    message="Asset is intentionally excluded from story input.",
                    severity="warning",
                )
            )
            continue

        if asset.page_order in page_orders:
            blockers.append(
                _asset_issue(
                    asset,
                    code="duplicate_page_order",
                    message="More than one asset uses this page order.",
                )
            )
        else:
            page_orders.add(asset.page_order)

        if asset.status != ASSET_STATUS_READY:
            blockers.append(
                _asset_issue(
                    asset,
                    code="asset_not_ready",
                    message=f"Asset OCR status is {asset.status!r}.",
                )
            )
            continue

        if asset.vision_status == "no_dialogue":
            prepared_pages.append(
                {
                    "asset_id": str(asset.id),
                    "page_order": asset.page_order,
                    "page_type": "no_dialogue",
                    "dialogues": [],
                }
            )
            continue

        if asset.vision_status != "completed":
            blockers.append(
                _asset_issue(
                    asset,
                    code="vision_not_ready",
                    message=f"Vision status is {asset.vision_status!r}.",
                )
            )
            continue

        if asset.dialogue_status != "completed":
            code = (
                "dialogue_review_required"
                if asset.dialogue_status == "needs_review"
                else "dialogue_not_ready"
            )
            blockers.append(
                _asset_issue(
                    asset,
                    code=code,
                    message=f"Dialogue status is {asset.dialogue_status!r}.",
                )
            )
            continue

        dialogues = _parse_dialogues(asset, blockers)
        if dialogues is None:
            continue

        prepared_dialogues = _prepare_dialogues(
            asset=asset,
            dialogues=dialogues,
            vision_region_types=_vision_region_types(asset),
            blockers=blockers,
        )
        if prepared_dialogues is None:
            continue

        prepared_pages.append(
            {
                "asset_id": str(asset.id),
                "page_order": asset.page_order,
                "page_type": "dialogue",
                "dialogues": prepared_dialogues,
            }
        )

    if blockers:
        return _empty_story_input(
            project_id=project_id,
            status="blocked",
            issues=sorted(
                [*issues, *blockers],
                key=_issue_sort_key,
            ),
            total_assets=len(ordered_assets),
        )

    prepared_pages.sort(
        key=lambda page: (page["page_order"], page["asset_id"]),
    )
    dialogue_count = sum(
        len(page["dialogues"])
        for page in prepared_pages
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "project_id": project_id,
        "status": "ready",
        "pages": prepared_pages,
        "issues": sorted(issues, key=_issue_sort_key),
        "summary": {
            "total_assets": len(ordered_assets),
            "source_pages": len(prepared_pages),
            "dialogue_pages": sum(
                page["page_type"] == "dialogue"
                for page in prepared_pages
            ),
            "no_dialogue_pages": sum(
                page["page_type"] == "no_dialogue"
                for page in prepared_pages
            ),
            "dialogue_count": dialogue_count,
        },
    }


def build_story_input(project_id: str) -> dict[str, Any]:
    db = SessionLocal()

    try:
        project_exists = (
            db.query(Project.id)
            .filter(Project.id == project_id)
            .first()
            is not None
        )

        if not project_exists:
            return _empty_story_input(
                project_id=project_id,
                status="blocked",
                issues=[
                    {
                        "code": "project_not_found",
                        "message": "Project does not exist.",
                    }
                ],
                total_assets=0,
            )

        assets = (
            db.query(Asset)
            .filter(Asset.project_id == project_id)
            .order_by(Asset.page_order.asc(), Asset.id.asc())
            .all()
        )
        return build_story_input_from_assets(project_id, assets)
    finally:
        db.close()


def _parse_dialogues(
    asset: Asset,
    blockers: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    try:
        dialogues = json.loads(asset.dialogues) if asset.dialogues else None
    except (json.JSONDecodeError, TypeError):
        dialogues = None

    if not isinstance(dialogues, list) or not dialogues:
        blockers.append(
            _asset_issue(
                asset,
                code="invalid_dialogues",
                message="Completed dialogue data must be a non-empty JSON list.",
            )
        )
        return None

    if not all(isinstance(dialogue, dict) for dialogue in dialogues):
        blockers.append(
            _asset_issue(
                asset,
                code="invalid_dialogues",
                message="Every dialogue entry must be an object.",
            )
        )
        return None

    return dialogues


def _prepare_dialogues(
    asset: Asset,
    dialogues: list[dict[str, Any]],
    vision_region_types: dict[int, str],
    blockers: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    prepared: list[dict[str, Any]] = []
    region_ids: set[int] = set()
    orders: set[int] = set()
    asset_has_error = False

    for dialogue in dialogues:
        region_id = dialogue.get("region_id")
        order = dialogue.get("order")
        decision = dialogue.get("decision")

        if not _is_positive_int(region_id) or not _is_positive_int(order):
            blockers.append(
                _asset_issue(
                    asset,
                    code="invalid_dialogue_reference",
                    message="Dialogue region_id and order must be positive integers.",
                )
            )
            asset_has_error = True
            continue

        if region_id in region_ids or order in orders:
            blockers.append(
                _asset_issue(
                    asset,
                    code="duplicate_dialogue_reference",
                    message="Dialogue region_id and order must be unique per page.",
                )
            )
            asset_has_error = True
            continue

        region_ids.add(region_id)
        orders.add(order)

        if decision not in SUPPORTED_DIALOGUE_DECISIONS:
            blockers.append(
                _asset_issue(
                    asset,
                    code="unsupported_dialogue_decision",
                    message=f"Dialogue decision {decision!r} is not authoritative.",
                    region_id=region_id,
                )
            )
            asset_has_error = True
            continue

        final_text, text_source = get_authoritative_dialogue_text(dialogue)
        if final_text is None:
            blockers.append(
                _asset_issue(
                    asset,
                    code="missing_authoritative_text",
                    message="Dialogue has no authoritative final text.",
                    region_id=region_id,
                )
            )
            asset_has_error = True
            continue

        text_role = classify_story_text_role(
            final_text,
            vision_region_types.get(region_id),
        )
        evidence_text, excluded_text = split_story_evidence(final_text)
        prepared_dialogue = {
                "region_id": region_id,
                "order": order,
                "final_text": final_text,
                "evidence_text": evidence_text,
                "text_role": text_role,
                "text_source": text_source,
                "decision": decision,
        }
        if excluded_text:
            prepared_dialogue["excluded_text"] = excluded_text
        prepared.append(prepared_dialogue)

    if asset_has_error:
        return None

    prepared.sort(
        key=lambda dialogue: (dialogue["order"], dialogue["region_id"]),
    )
    return prepared


def split_story_evidence(text: str) -> tuple[str, str | None]:
    """Remove explicit translator-note suffixes from factual evidence."""
    match = re.search(r"(?i)(?:\*|\b)TRANS\s*NOTE\s*:", text)
    if match is None:
        return text.strip(), None

    evidence_text = text[: match.start()].rstrip(" *'\"")
    excluded_text = text[match.start():].strip()
    return evidence_text, excluded_text or None


def classify_story_text_role(text: str, vision_type: str | None) -> str:
    """Map Day 8 region metadata to the smaller Story-layer role vocabulary."""
    normalized_type = (vision_type or "").strip().lower()
    role_by_vision_type = {
        "speech_bubble": "dialogue",
        "dialogue": "dialogue",
        "narration": "narration",
        "thought": "thought",
        "game_ui": "game_ui",
        "translator_note": "translator_note",
        "note": "other",
        "sfx": "sfx",
    }
    role = role_by_vision_type.get(normalized_type, "other")

    upper_text = text.upper()
    ui_markers = (
        "THÀNH TỰU",
        "ĐẶC QUYỀN",
        "ACHIEVEMENT",
        "UNLOCKED",
        "SYSTEM",
    )
    if any(marker in upper_text for marker in ui_markers):
        return "game_ui"
    if re.match(r"(?i)^\s*\*?TRANS\s*NOTE\s*:", text):
        return "translator_note"
    return role


def _vision_region_types(asset: Asset) -> dict[int, str]:
    try:
        regions = json.loads(asset.vision_regions) if asset.vision_regions else []
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(regions, list):
        return {}

    result: dict[int, str] = {}
    for region in regions:
        if not isinstance(region, dict):
            continue
        region_id = region.get("id")
        region_type = region.get("type")
        if _is_positive_int(region_id) and isinstance(region_type, str):
            result[region_id] = region_type
    return result


def _non_empty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    return text or None


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _asset_issue(
    asset: Asset,
    code: str,
    message: str,
    severity: str = "error",
    region_id: int | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "asset_id": str(asset.id),
        "page_order": asset.page_order,
        "message": message,
    }
    if region_id is not None:
        issue["region_id"] = region_id
    return issue


def _empty_story_input(
    project_id: str,
    status: str,
    issues: list[dict[str, Any]],
    total_assets: int,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "project_id": project_id,
        "status": status,
        "pages": [],
        "issues": issues,
        "summary": {
            "total_assets": total_assets,
            "source_pages": 0,
            "dialogue_pages": 0,
            "no_dialogue_pages": 0,
            "dialogue_count": 0,
        },
    }


def _issue_sort_key(issue: dict[str, Any]) -> tuple[int, str, int]:
    return (
        int(issue.get("page_order", 0)),
        str(issue.get("asset_id", "")),
        int(issue.get("region_id", 0)),
    )
