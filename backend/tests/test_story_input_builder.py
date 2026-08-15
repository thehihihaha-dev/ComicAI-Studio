import json
import unittest
from datetime import datetime, timezone

from app.models.asset import Asset
from app.services.story_input_builder import (
    build_story_input_from_assets,
    get_authoritative_dialogue_text,
)


def make_asset(
    asset_id: str,
    page_order: int,
    *,
    status: str = "ready",
    vision_status: str = "completed",
    dialogue_status: str = "completed",
    dialogues: list[dict] | str | None = None,
) -> Asset:
    if dialogues is None and vision_status == "completed":
        dialogues = [
            {
                "region_id": 1,
                "order": 1,
                "raw_text": "RAW",
                "clean_text": "CLEAN",
                "decision": "auto_accepted",
            }
        ]

    return Asset(
        id=asset_id,
        project_id="project-1",
        filename=f"{page_order}.jpg",
        file_type="image",
        file_path=f"uploads/{page_order}.jpg",
        page_order=page_order,
        created_at=datetime.now(timezone.utc),
        status=status,
        vision_status=vision_status,
        dialogue_status=dialogue_status,
        dialogues=(
            json.dumps(dialogues, ensure_ascii=False)
            if isinstance(dialogues, list)
            else dialogues
        ),
    )


class AuthoritativeTextTests(unittest.TestCase):
    def test_verified_text_has_highest_priority(self):
        text, source = get_authoritative_dialogue_text(
            {
                "decision": "verified",
                "verified_text": "VERIFIED",
                "recovered_text": "RECOVERED",
                "clean_text": "CLEAN",
            }
        )
        self.assertEqual((text, source), ("VERIFIED", "verified"))

    def test_recovered_text_supports_legacy_day8_data(self):
        text, source = get_authoritative_dialogue_text(
            {
                "decision": "auto_recovered",
                "recovered_text": "RECOVERED",
                "clean_text": "OLD CLEAN",
            }
        )
        self.assertEqual((text, source), ("RECOVERED", "recovered"))

    def test_does_not_fallback_to_raw_ocr(self):
        self.assertEqual(
            get_authoritative_dialogue_text(
                {"decision": "auto_accepted", "raw_text": "RAW"}
            ),
            (None, None),
        )


class StoryInputBuilderTests(unittest.TestCase):
    def test_preserves_vision_role_and_excludes_translator_note(self):
        asset = make_asset(
            "asset-1",
            1,
            dialogues=[
                {
                    "region_id": 1,
                    "order": 1,
                    "clean_text": (
                        "Đã mở THÀNH TỰU. KAZU NÀY "
                        "*TRANS NOTE: chú thích"
                    ),
                    "decision": "auto_accepted",
                }
            ],
        )
        asset.vision_regions = json.dumps(
            [{"id": 1, "type": "speech_bubble", "block_ids": [1]}]
        )

        result = build_story_input_from_assets("project-1", [asset])
        dialogue = result["pages"][0]["dialogues"][0]

        self.assertEqual(dialogue["text_role"], "game_ui")
        self.assertEqual(dialogue["evidence_text"], "Đã mở THÀNH TỰU. KAZU NÀY")
        self.assertEqual(dialogue["excluded_text"], "*TRANS NOTE: chú thích")

    def test_sorts_pages_and_dialogues(self):
        page_two = make_asset("asset-2", 2)
        page_one = make_asset(
            "asset-1",
            1,
            dialogues=[
                {
                    "region_id": 8,
                    "order": 2,
                    "clean_text": "SECOND",
                    "decision": "auto_accepted",
                },
                {
                    "region_id": 3,
                    "order": 1,
                    "clean_text": "FIRST",
                    "decision": "auto_accepted",
                },
            ],
        )

        result = build_story_input_from_assets(
            "project-1",
            [page_two, page_one],
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            [page["page_order"] for page in result["pages"]],
            [1, 2],
        )
        self.assertEqual(
            [item["order"] for item in result["pages"][0]["dialogues"]],
            [1, 2],
        )

    def test_no_dialogue_page_has_no_fake_dialogue(self):
        result = build_story_input_from_assets(
            "project-1",
            [
                make_asset(
                    "asset-1",
                    1,
                    vision_status="no_dialogue",
                    dialogue_status="pending",
                )
            ],
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["pages"][0]["page_type"], "no_dialogue")
        self.assertEqual(result["pages"][0]["dialogues"], [])

    def test_processing_or_failed_assets_block_all_pages(self):
        for status in ("processing", "failed"):
            with self.subTest(status=status):
                result = build_story_input_from_assets(
                    "project-1",
                    [make_asset("asset-1", 1, status=status)],
                )
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["pages"], [])
                self.assertEqual(result["issues"][0]["code"], "asset_not_ready")

    def test_dialogue_review_blocks_story_input(self):
        result = build_story_input_from_assets(
            "project-1",
            [make_asset("asset-1", 1, dialogue_status="needs_review")],
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["issues"][0]["code"], "dialogue_review_required")

    def test_invalid_json_blocks_story_input(self):
        result = build_story_input_from_assets(
            "project-1",
            [make_asset("asset-1", 1, dialogues="not json")],
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["issues"][0]["code"], "invalid_dialogues")

    def test_missing_final_text_blocks_story_input(self):
        result = build_story_input_from_assets(
            "project-1",
            [
                make_asset(
                    "asset-1",
                    1,
                    dialogues=[
                        {
                            "region_id": 1,
                            "order": 1,
                            "raw_text": "RAW ONLY",
                            "decision": "auto_accepted",
                        }
                    ],
                )
            ],
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["issues"][0]["code"], "missing_authoritative_text")

    def test_excluded_asset_is_a_non_blocking_warning(self):
        result = build_story_input_from_assets(
            "project-1",
            [
                make_asset("excluded", 1, status="excluded"),
                make_asset("included", 2),
            ],
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["pages"]), 1)
        self.assertEqual(result["issues"][0]["severity"], "warning")

    def test_empty_project_has_explicit_status(self):
        result = build_story_input_from_assets("project-1", [])
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["issues"][0]["code"], "project_has_no_assets")


if __name__ == "__main__":
    unittest.main()
