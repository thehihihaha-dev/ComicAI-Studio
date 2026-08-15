import unittest

from app.services.story_grounding import (
    build_story_source_index,
    ground_story_result,
)


def story_input():
    return {
        "contract_version": "story_input.v1",
        "project_id": "project-1",
        "status": "ready",
        "pages": [
            {
                "asset_id": "asset-1",
                "page_order": 1,
                "page_type": "dialogue",
                "dialogues": [
                    {
                        "region_id": 1,
                        "order": 1,
                        "final_text": "Name One says marriage",
                        "text_role": "dialogue",
                    },
                    {
                        "region_id": 2,
                        "order": 2,
                        "final_text": "in the game",
                        "text_role": "dialogue",
                    },
                ],
            },
            {
                "asset_id": "asset-2",
                "page_order": 2,
                "page_type": "dialogue",
                "dialogues": [
                    {
                        "region_id": 5,
                        "order": 1,
                        "final_text": "Name Five because permission was granted",
                        "text_role": "dialogue",
                    }
                ],
            },
        ],
    }


def source(asset_id="asset-1", page_order=1, region_ids=None):
    return {
        "asset_id": asset_id,
        "page_order": page_order,
        "region_ids": region_ids if region_ids is not None else [1],
    }


def claim(claim_id, sources, claim_type="fact", subject=None):
    result = {
        "id": claim_id,
        "text": f"Claim {claim_id}",
        "claim_type": claim_type,
        "sources": sources,
    }
    if subject is not None:
        result["subject"] = subject
    return result


def event(event_id, sources, claims=None):
    return {
        "id": event_id,
        "summary": f"Summary {event_id}",
        "importance": 0.8,
        "emotion": "neutral",
        "story_role": "main_story",
        "claims": claims or [claim(f"{event_id}-claim-1", sources)],
    }


def character(character_id, sources):
    return {
        "id": character_id,
        "name": "Name One",
        "sources": sources,
    }


def story_result(*, characters=None, events=None, progression=None):
    return {
        "analyzer_version": "story_analyzer.v1",
        "project_id": "project-1",
        "characters": characters or [],
        "events": events or [],
        "main_progression": progression or [],
    }


class SourceIndexTests(unittest.TestCase):
    def test_builds_asset_page_region_index(self):
        index = build_story_source_index(story_input())
        self.assertEqual(index["asset-1"]["page_order"], 1)
        self.assertEqual(index["asset-1"]["region_ids"], frozenset({1, 2}))


class StoryGroundingTests(unittest.TestCase):
    def test_multi_claim_event_with_complete_evidence_is_script_ready(self):
        result = ground_story_result(
            story_input(),
            story_result(
                events=[
                    event(
                        "event-1",
                        [],
                        claims=[
                            claim("claim-1", [source(region_ids=[1])]),
                            claim("claim-2", [source(region_ids=[2])]),
                        ],
                    )
                ],
                progression=["event-1"],
            ),
        )
        grounded = result["events"][0]
        self.assertTrue(grounded["script_ready"])
        self.assertEqual(grounded["sources"][0]["region_ids"], [1, 2])
        self.assertEqual(result["main_progression"], ["event-1"])

    def test_missing_evidence_for_one_claim_is_not_script_ready(self):
        result = ground_story_result(
            story_input(),
            story_result(
                events=[
                    event(
                        "event-1",
                        [],
                        claims=[
                            claim("claim-1", [source()]),
                            claim("claim-2", [source(region_ids=[999])]),
                        ],
                    )
                ]
            ),
        )
        grounded = result["events"][0]
        self.assertFalse(grounded["script_ready"])
        self.assertEqual(grounded["unsupported_claims"][0]["id"], "claim-2")

    def test_unsupported_speaker_is_not_script_ready(self):
        result = ground_story_result(
            story_input(),
            story_result(
                events=[
                    event(
                        "event-1",
                        [],
                        claims=[
                            claim(
                                "claim-1",
                                [source(region_ids=[2])],
                                "speaker_attribution",
                                "RIN",
                            )
                        ],
                    )
                ]
            ),
        )
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["issues"][-1]["code"], "unsupported_speaker_attribution")

    def test_speaker_without_subject_is_not_script_ready(self):
        attributed = claim(
            "claim-1", [source()], "speaker_attribution"
        )
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [], claims=[attributed])]),
        )
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["issues"][-1]["code"], "unsupported_speaker_attribution")

    def test_unsupported_actor_is_not_script_ready(self):
        attributed = claim(
            "claim-1", [source(region_ids=[2])], "actor_attribution", "KAZU"
        )
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [], claims=[attributed])]),
        )
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["issues"][-1]["code"], "unsupported_actor_attribution")

    def test_unsupported_causal_inference_is_not_script_ready(self):
        causal = claim(
            "claim-1", [source(region_ids=[1, 2])], "causal_relation"
        )
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [], claims=[causal])]),
        )
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["issues"][-1]["code"], "unsupported_causal_inference")

    def test_causality_hidden_in_fact_claim_is_rejected(self):
        hidden = claim("claim-1", [source(region_ids=[1, 2])])
        hidden["text"] = "The achievement grants marriage permission."
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [], claims=[hidden])]),
        )
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["issues"][-1]["code"], "unsupported_causal_inference")

    def test_named_attribution_is_safely_deattributed(self):
        hidden = claim("claim-1", [source(region_ids=[2])])
        hidden["text"] = "Name One takes the oath."
        result = ground_story_result(
            story_input(),
            story_result(
                characters=[character("character-1", [source()])],
                events=[event("event-1", [], claims=[hidden])],
            ),
        )
        grounded_claim = result["events"][0]["claims"][0]
        self.assertTrue(result["events"][0]["script_ready"])
        self.assertEqual(grounded_claim["text"], "A character takes the oath.")
        self.assertEqual(
            grounded_claim["repair_type"], "remove_unsupported_attribution"
        )
        self.assertEqual(grounded_claim["original_text"], "Name One takes the oath.")

    def test_standalone_name_can_be_safely_deattributed(self):
        data = story_input()
        data["pages"][0]["dialogues"].append(
            {"region_id": 3, "order": 3, "final_text": "RIN"}
        )
        hidden = claim("claim-1", [source(region_ids=[2])])
        hidden["text"] = "RIN takes the oath."
        result = ground_story_result(
            data,
            story_result(events=[event("event-1", [], claims=[hidden])]),
        )
        grounded_claim = result["events"][0]["claims"][0]
        self.assertTrue(result["events"][0]["script_ready"])
        self.assertEqual(grounded_claim["text"], "A character takes the oath.")
        self.assertEqual(grounded_claim["removed_attribution"], "RIN")

    def test_deattribution_is_impossible_with_multiple_unsupported_names(self):
        hidden = claim("claim-1", [source("asset-2", 2, [5])])
        hidden["text"] = "Name One marries Name Two."
        result = ground_story_result(
            story_input(),
            story_result(
                characters=[
                    {"id": "character-1", "name": "Name One", "sources": [source()]},
                    {
                        "id": "character-2",
                        "name": "Name Two",
                        "sources": [source(region_ids=[2])],
                    },
                ],
                events=[event("event-1", [], claims=[hidden])],
            ),
        )
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["issues"][-1]["code"], "unsupported_named_attribution")

    def test_repeated_salient_name_requires_its_own_evidence(self):
        data = story_input()
        data["pages"][0]["dialogues"][0]["final_text"] = "KAZU appears"
        data["pages"][1]["dialogues"][0]["final_text"] = "KAZU returns"
        hidden = claim("claim-1", [source(region_ids=[2])])
        hidden["text"] = "KAZU takes the oath."
        result = ground_story_result(
            data,
            story_result(events=[event("event-1", [], claims=[hidden])]),
        )
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["issues"][-1]["code"], "unsupported_named_attribution")

    def test_explicit_causal_evidence_is_script_ready(self):
        causal = claim(
            "claim-1",
            [source("asset-2", 2, [5])],
            "causal_relation",
        )
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [], claims=[causal])]),
        )
        self.assertTrue(result["events"][0]["script_ready"])

    def test_character_name_source_mismatch_is_unsupported(self):
        result = ground_story_result(
            story_input(),
            story_result(
                characters=[
                    {
                        "id": "character-1",
                        "name": "KAZU",
                        "sources": [source()],
                    }
                ]
            ),
        )
        self.assertEqual(result["characters"], [])
        self.assertEqual(
            result["issues"][0]["code"],
            "character_name_not_in_source",
        )

    def test_character_name_matching_is_case_and_diacritic_insensitive(self):
        data = story_input()
        data["pages"][0]["dialogues"][0]["final_text"] = "Kazu gặp Rín"
        result = ground_story_result(
            data,
            story_result(
                characters=[
                    {"id": "character-1", "name": "RIN", "sources": [source()]}
                ]
            ),
        )
        self.assertEqual(len(result["characters"]), 1)

    def test_contextual_event_is_excluded_from_progression(self):
        contextual = event("event-1", [source()])
        contextual["story_role"] = "supporting_context"
        result = ground_story_result(
            story_input(),
            story_result(events=[contextual], progression=["event-1"]),
        )
        self.assertEqual(result["main_progression"], [])
        self.assertEqual(result["issues"][0]["code"], "contextual_progression_event")

    def test_game_ui_claim_is_context_only_and_not_script_ready(self):
        data = story_input()
        data["pages"][0]["dialogues"][0]["text_role"] = "game_ui"
        contextual = event("event-1", [source()])
        contextual["story_role"] = "supporting_context"
        result = ground_story_result(
            data,
            story_result(events=[contextual]),
        )
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(
            result["issues"][-1]["code"],
            "game_ui_claim_requires_review",
        )

    def test_valid_asset_page_region_source_is_accepted(self):
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [source()])]),
        )
        self.assertEqual([item["id"] for item in result["events"]], ["event-1"])
        self.assertEqual(result["issues"], [])

    def test_invalid_asset_is_unsupported(self):
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [source("invented")])]),
        )
        self.assertEqual(result["events"][0]["claims"], [])
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["unsupported_events"][0]["id"], "event-1")
        self.assertEqual(result["issues"][0]["code"], "invalid_asset_reference")

    def test_wrong_page_order_is_rejected(self):
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [source(page_order=9)])]),
        )
        self.assertEqual(result["events"][0]["claims"], [])
        self.assertEqual(result["issues"][0]["code"], "wrong_page_order")

    def test_invalid_region_is_rejected(self):
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [source(region_ids=[999])])]),
        )
        self.assertEqual(result["events"][0]["claims"], [])
        self.assertFalse(result["events"][0]["script_ready"])
        self.assertEqual(result["issues"][0]["code"], "invalid_region_reference")
        self.assertEqual(result["issues"][0]["region_id"], 999)

    def test_mixed_valid_and_invalid_sources_keeps_valid_source(self):
        result = ground_story_result(
            story_input(),
            story_result(
                events=[
                    event(
                        "event-1",
                        [source("invented"), source("asset-2", 2, [5])],
                    )
                ]
            ),
        )
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["sources"], [source("asset-2", 2, [5])])
        self.assertEqual(result["issues"][0]["code"], "invalid_asset_reference")

    def test_character_without_valid_sources_is_unsupported(self):
        result = ground_story_result(
            story_input(),
            story_result(
                characters=[character("character-1", [source("invented")])]
            ),
        )
        self.assertEqual(result["characters"], [])
        self.assertEqual(
            result["unsupported_characters"][0]["id"],
            "character-1",
        )

    def test_duplicate_sources_and_regions_are_deduplicated(self):
        repeated = source(region_ids=[2, 1, 2])
        result = ground_story_result(
            story_input(),
            story_result(events=[event("event-1", [repeated, repeated])]),
        )
        self.assertEqual(
            result["events"][0]["sources"],
            [source(region_ids=[1, 2])],
        )
        self.assertEqual(
            [issue["code"] for issue in result["issues"]],
            [
                "duplicate_region_reference",
                "duplicate_region_reference",
                "duplicate_source_reference",
            ],
        )

    def test_progression_removes_nonexistent_event(self):
        result = ground_story_result(
            story_input(),
            story_result(
                events=[event("event-1", [source()])],
                progression=["event-1", "invented"],
            ),
        )
        self.assertEqual(result["main_progression"], ["event-1"])
        self.assertEqual(result["issues"][0]["code"], "nonexistent_progression_event")

    def test_progression_removes_unsupported_event(self):
        result = ground_story_result(
            story_input(),
            story_result(
                events=[event("event-1", [source("invented")])],
                progression=["event-1"],
            ),
        )
        self.assertEqual(result["main_progression"], [])
        self.assertEqual(result["issues"][-1]["code"], "unsupported_progression_event")

    def test_grounded_event_and_progression_order_is_preserved(self):
        result = ground_story_result(
            story_input(),
            story_result(
                events=[
                    event("event-2", [source("asset-2", 2, [5])]),
                    event("event-1", [source()]),
                ],
                progression=["event-1", "event-2", "event-1"],
            ),
        )
        self.assertEqual(
            [item["id"] for item in result["events"]],
            ["event-2", "event-1"],
        )
        self.assertEqual(result["main_progression"], ["event-1", "event-2"])
        self.assertEqual(result["issues"][0]["code"], "duplicate_progression_event")


if __name__ == "__main__":
    unittest.main()
