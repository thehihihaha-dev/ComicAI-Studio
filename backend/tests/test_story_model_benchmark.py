import unittest

from app.services.story_model_benchmark import (
    compare_events,
    validate_candidate_artifact,
)


def event(event_id, region_ids, text="fact", unsupported=False):
    return {
        "id": event_id,
        "claims": [
            {
                "text": text,
                "sources": [
                    {"asset_id": "a", "page_order": 1, "region_ids": region_ids}
                ],
            }
        ],
        "unsupported_claims": [{"text": "bad"}] if unsupported else [],
    }


class CandidateArtifactTests(unittest.TestCase):
    def test_valid_schema(self):
        validate_candidate_artifact(
            {
                "schema_version": 1,
                "checkpoint": "11.2",
                "candidate_model": "qwen3:4b-instruct",
                "input": {},
                "performance": {},
                "correctness": {"accepted_unsupported_claims": 0},
                "safety": {},
            }
        )

    def test_rejects_missing_or_malformed_artifact(self):
        with self.assertRaises(ValueError):
            validate_candidate_artifact({})
        with self.assertRaises(ValueError):
            validate_candidate_artifact(
                {
                    "schema_version": 1,
                    "checkpoint": "11.2",
                    "candidate_model": "candidate",
                    "input": {},
                    "performance": {},
                    "correctness": {"accepted_unsupported_claims": "unknown"},
                    "safety": {},
                }
            )

    def test_event_diff_is_deterministic_and_source_based(self):
        control = [event("control-1", [1, 2]), event("control-2", [3])]
        candidate = [event("candidate-1", [1])]
        self.assertEqual(
            compare_events(control, candidate),
            [
                {
                    "control_event_id": "control-1",
                    "candidate_event_id": "candidate-1",
                    "classification": "less complete",
                    "human_judgment_required": True,
                    "shared_source_count": 1,
                },
                {
                    "control_event_id": "control-2",
                    "candidate_event_id": None,
                    "classification": "missing",
                    "human_judgment_required": False,
                    "shared_source_count": 0,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
