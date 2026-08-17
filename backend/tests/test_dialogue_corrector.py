import unittest
from unittest.mock import patch

from app.services.dialogue_corrector import (
    apply_dialogue_decisions,
    apply_verified_ground_truth,
    calculate_correction_score,
    has_risky_text_change,
    recover_uncertain_dialogues,
    correct_dialogues,
    screen_dialogues,
    validate_corrected_dialogues,
    correction_recovery_agree,
    decide_dialogue_action,
    process_dialogue_batches,
)


class DialogueValidationTests(unittest.TestCase):
    def setUp(self):
        self.original = [
            {
                "order": 1,
                "region_id": 7,
                "raw_text": "NGUYỆN YẾU",
                "block_ids": [0],
            }
        ]
        self.corrected = [
            {
                "order": 1,
                "region_id": 7,
                "raw_text": "NGUYỆN YẾU",
                "clean_text": "NGUYỆN YÊU",
                "confidence": 0.95,
                "needs_review": False,
            }
        ]

    def test_accepts_structurally_valid_correction(self):
        result = validate_corrected_dialogues(self.original, self.corrected)
        self.assertTrue(result["is_valid"])

    def test_rejects_changed_raw_text(self):
        self.corrected[0]["raw_text"] = "CHANGED"
        result = validate_corrected_dialogues(self.original, self.corrected)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["raw_text_mismatches"], [7])

    def test_rejects_duplicate_region(self):
        self.corrected.append(dict(self.corrected[0]))
        result = validate_corrected_dialogues(self.original, self.corrected)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["duplicate_region_ids"], [7])

    def test_rejects_invalid_confidence(self):
        self.corrected[0]["confidence"] = 1.5
        result = validate_corrected_dialogues(self.original, self.corrected)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["invalid_confidence_region_ids"], [7])


class DialogueDecisionTests(unittest.TestCase):
    @patch("app.services.dialogue_corrector._process_dialogue_batch")
    def test_recovered_review_does_not_rewrite_safe_sibling(self, process):
        def result(_image, dialogues, _blocks, _verified):
            return [
                {
                    **item,
                    "clean_text": item["raw_text"],
                    "decision": (
                        "needs_review" if item["region_id"] == 8 else "auto_recovered"
                    ),
                }
                for item in dialogues
            ]

        process.side_effect = result
        dialogues = [
            {"order": 1, "region_id": 1, "raw_text": "safe"},
            {"order": 2, "region_id": 8, "raw_text": "uncertain"},
        ]
        regions = [
            {"id": 1, "region_source": "geometry_split"},
            {"id": 8, "region_source": "vision_ocr_recovery"},
        ]
        merged = process_dialogue_batches("page.jpg", dialogues, [], regions)
        self.assertEqual([item["region_id"] for item in merged], [1, 8])
        self.assertEqual(merged[0]["decision"], "auto_recovered")
        self.assertEqual(merged[1]["decision"], "needs_review")
        self.assertTrue(any(item["decision"] == "needs_review" for item in merged))
        self.assertEqual(process.call_count, 2)
        self.assertEqual(
            [item["region_id"] for item in process.call_args_list[0].args[1]],
            [1],
        )
        self.assertEqual(
            [item["region_id"] for item in process.call_args_list[1].args[1]],
            [8],
        )

    @patch("app.services.dialogue_corrector._process_dialogue_batch")
    def test_normal_page_uses_one_unchanged_batch(self, process):
        dialogues = [{"order": 1, "region_id": 1, "raw_text": "safe"}]
        process.side_effect = lambda _image, items, _blocks, _verified: [
            {**item, "decision": "auto_recovered"} for item in items
        ]
        result = process_dialogue_batches(
            "page.jpg",
            dialogues,
            [],
            [{"id": 1, "region_source": "original_layout"}],
        )
        self.assertEqual(result[0]["region_id"], 1)
        process.assert_called_once()

    def test_ground_truth_wins_after_pipeline_rerun(self):
        result = apply_verified_ground_truth(
            [
                {
                    "region_id": 2,
                    "clean_text": "NGUYỆN YẾU",
                    "decision": "auto_recovered",
                    "needs_review": True,
                }
            ],
            {2: "NGUYỆN YÊU"},
        )

        self.assertEqual(result[0]["clean_text"], "NGUYỆN YÊU")
        self.assertEqual(result[0]["verified_text"], "NGUYỆN YÊU")
        self.assertEqual(result[0]["decision"], "verified")
        self.assertFalse(result[0]["needs_review"])

    def test_risky_change_detects_single_word_change_in_short_text(self):
        self.assertTrue(has_risky_text_change("NGUYỆN YẾU", "NGUYỆN YÊU"))

    def test_safe_unchanged_dialogue_is_auto_accepted(self):
        scored = calculate_correction_score(
            [
                {
                    "order": 1,
                    "region_id": 1,
                    "raw_text": "XIN CHÀO",
                    "block_ids": [0],
                }
            ],
            [
                {
                    "order": 1,
                    "region_id": 1,
                    "raw_text": "XIN CHÀO",
                    "clean_text": "XIN CHÀO",
                    "confidence": 0.99,
                    "needs_review": False,
                }
            ],
            [{"confidence": 0.99}],
        )
        decided = apply_dialogue_decisions(scored)
        self.assertEqual(decided[0]["decision"], "auto_accepted")

    @patch("app.services.dialogue_corrector.recover_dialogues_batch")
    def test_recovery_promotes_recovered_text_to_clean_text(self, recover):
        recover.return_value = [{
            "region_id": 1,
            "recovered_text": "CHO DÙ",
            "confidence": 0.96,
            "still_uncertain": False,
            "reason": "Confirmed from image",
        }]
        result = recover_uncertain_dialogues(
            "page.jpg",
            [
                {
                    "order": 1,
                    "region_id": 1,
                    "raw_text": "CHỜ DÙ",
                    "clean_text": "CHỜ DÙ",
                    "decision": "needs_recovery",
                }
            ],
        )
        self.assertEqual(result[0]["clean_text"], "CHO DÙ")
        self.assertEqual(result[0]["initial_clean_text"], "CHỜ DÙ")
        self.assertEqual(result[0]["decision"], "auto_recovered")

    @patch("app.services.dialogue_corrector.recover_dialogues_batch")
    def test_recovery_rejects_wrong_region_id(self, recover):
        recover.return_value = [{
            "region_id": 999,
            "recovered_text": "INVENTED",
            "confidence": 1.0,
            "still_uncertain": False,
        }]
        result = recover_uncertain_dialogues(
            "page.jpg",
            [
                {
                    "region_id": 1,
                    "clean_text": "ORIGINAL",
                    "decision": "needs_recovery",
                }
            ],
        )
        self.assertEqual(result[0]["decision"], "needs_review")
        self.assertEqual(result[0]["recovery_confidence"], 0.0)

    @patch("app.services.dialogue_corrector.call_vision_model")
    def test_batch_recovery_uses_one_model_call(self, call_model):
        call_model.return_value = {"items": [
            {"region_id": 1, "action": "changed", "clean_text": "A", "confidence": 0.95, "decision": "accept", "reason_code": "ocr_typo"},
            {"region_id": 2, "action": "changed", "clean_text": "B", "confidence": 0.96, "decision": "accept", "reason_code": "ocr_typo"},
        ]}
        result = recover_uncertain_dialogues("page.jpg", [
            {"region_id": 1, "clean_text": "X", "decision": "needs_recovery"},
            {"region_id": 2, "clean_text": "Y", "decision": "needs_recovery"},
        ])
        self.assertEqual(call_model.call_count, 1)
        self.assertEqual([item["decision"] for item in result], ["auto_recovered", "auto_recovered"])

    @patch("app.services.dialogue_corrector.recover_dialogues_batch")
    def test_invalid_batch_item_does_not_corrupt_valid_item(self, recover):
        recover.return_value = [
            {"region_id": 1, "recovered_text": "SAFE", "confidence": 0.95, "still_uncertain": False},
            {"region_id": 999, "recovered_text": "INVENTED", "confidence": 1.0, "still_uncertain": False},
        ]
        result = recover_uncertain_dialogues("page.jpg", [
            {"region_id": 1, "clean_text": "ONE", "decision": "needs_recovery"},
            {"region_id": 2, "clean_text": "TWO", "decision": "needs_recovery"},
        ])
        self.assertEqual(result[0]["clean_text"], "SAFE")
        self.assertEqual(result[0]["decision"], "auto_recovered")
        self.assertEqual(result[1]["clean_text"], "TWO")
        self.assertEqual(result[1]["decision"], "needs_review")


class DialogueFastPathTests(unittest.TestCase):
    def test_high_confidence_dialogue_skips_model(self):
        dialogue = {"order": 1, "region_id": 1, "raw_text": "XIN CHÀO", "block_ids": [0]}
        accepted, uncertain = screen_dialogues([dialogue], [{"confidence": 0.99}])
        self.assertEqual(accepted[0]["correction_path"], "fast_path")
        self.assertEqual(uncertain, [])

    def test_low_confidence_dialogue_enters_correction(self):
        dialogue = {"order": 1, "region_id": 1, "raw_text": "XIN CHÀO", "block_ids": [0]}
        accepted, uncertain = screen_dialogues([dialogue], [{"confidence": 0.5}])
        self.assertEqual(accepted, [])
        self.assertEqual(uncertain, [dialogue])

    def test_mixed_page_only_sends_uncertain_dialogues(self):
        dialogues = [
            {"order": 1, "region_id": 1, "raw_text": "XIN CHÀO", "block_ids": [0]},
            {"order": 2, "region_id": 2, "raw_text": "TÔ1", "block_ids": [1]},
        ]
        accepted, uncertain = screen_dialogues(dialogues, [{"confidence": 0.99}, {"confidence": 0.99}])
        self.assertEqual([item["region_id"] for item in accepted], [1])
        self.assertEqual([item["region_id"] for item in uncertain], [2])

    def test_ground_truth_skips_screening_and_models(self):
        dialogue = {"order": 1, "region_id": 3, "raw_text": "NGUYỆN YẾU", "block_ids": [0]}
        accepted, uncertain = screen_dialogues([dialogue], [{"confidence": 0.1}], {3: "NGUYỆN YÊU"})
        self.assertEqual(accepted[0]["decision"], "verified")
        self.assertEqual(uncertain, [])

    @patch("app.services.dialogue_corrector.call_text_model")
    def test_text_first_experiment_returns_structural_candidate(self, text_model):
        dialogue = {"order": 1, "region_id": 1, "raw_text": "XIN CHÀO", "block_ids": [0]}
        text_model.return_value = {"dialogues": [{"region_id": 1, "clean_text": "XIN CHÀO", "confidence": 0.99, "needs_review": False, "needs_visual": False}]}
        from app.services.dialogue_corrector import correct_dialogues_text_first
        result = correct_dialogues_text_first([dialogue])
        self.assertEqual(result[0]["raw_text"], "XIN CHÀO")

    @patch("app.services.dialogue_corrector._correct_dialogues_vision")
    def test_rejected_text_first_strategy_uses_visual(self, vision):
        dialogue = {"order": 1, "region_id": 1, "raw_text": "X1N", "block_ids": [0]}
        vision.return_value = [{**dialogue, "clean_text": "XIN"}]
        correct_dialogues("page.jpg", [dialogue], [{"confidence": 0.2}])
        vision.assert_called_once()

    @patch("app.services.dialogue_corrector._combined_dialogue_crop", return_value="crop.jpg")
    @patch("app.services.dialogue_corrector.call_vision_model")
    @patch("app.services.dialogue_corrector.Path.unlink")
    def test_crop_correction_path(self, _unlink, model, _crop):
        dialogue = {"order": 1, "region_id": 1, "raw_text": "X1N"}
        model.return_value = {"dialogues": [{**dialogue, "clean_text": "XIN", "confidence": 0.95, "needs_review": False}]}
        from app.services.dialogue_corrector import _correct_dialogues_vision
        result = _correct_dialogues_vision("page.jpg", [dialogue], [])
        self.assertEqual(model.call_args.kwargs["image_path"], "crop.jpg")
        self.assertEqual(result[0]["correction_path"], "vision_crop")

    @patch("app.services.dialogue_corrector._combined_dialogue_crop", return_value="crop.jpg")
    @patch("app.services.dialogue_corrector.call_vision_model")
    @patch("app.services.dialogue_corrector.Path.unlink")
    def test_invalid_crop_uses_full_page_fallback(self, _unlink, model, _crop):
        dialogue = {"order": 1, "region_id": 1, "raw_text": "X1N"}
        model.side_effect = [RuntimeError("bad crop"), {"dialogues": [{**dialogue, "clean_text": "XIN", "confidence": 0.95, "needs_review": False}]}]
        from app.services.dialogue_corrector import _correct_dialogues_vision
        _correct_dialogues_vision("page.jpg", [dialogue], [])
        self.assertEqual(model.call_args.kwargs["image_path"], "page.jpg")


class CompactDialogueContractTests(unittest.TestCase):
    def setUp(self):
        self.original = [{"order": 2, "region_id": 7, "raw_text": "NGUYỆN YẾU", "block_ids": [3]}]

    def test_unchanged_reuses_trusted_input_and_reattaches_immutables(self):
        from app.services.dialogue_corrector import parse_compact_corrections
        result = parse_compact_corrections(self.original, {"items": [{"region_id": 7, "action": "unchanged", "confidence": 0.98, "decision": "accept", "reason_code": "unchanged"}]})
        self.assertEqual(result[0]["clean_text"], "NGUYỆN YẾU")
        self.assertEqual(result[0]["raw_text"], "NGUYỆN YẾU")
        self.assertEqual(result[0]["order"], 2)

    def test_changed_requires_clean_text(self):
        from app.services.dialogue_corrector import parse_compact_corrections
        with self.assertRaisesRegex(ValueError, "requires clean_text"):
            parse_compact_corrections(self.original, {"items": [{"region_id": 7, "action": "changed", "confidence": 0.9, "decision": "review", "reason_code": "low_confidence"}]})

    def test_reason_code_must_be_allowlisted(self):
        from app.services.dialogue_corrector import parse_compact_corrections
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            parse_compact_corrections(self.original, {"items": [{"region_id": 7, "action": "unchanged", "confidence": 0.9, "decision": "accept", "reason_code": "long invented prose"}]})

    @patch("app.services.dialogue_corrector.call_vision_model")
    def test_dialogue_options_and_json_mode_are_scoped(self, model):
        from app.services.dialogue_corrector import _correct_dialogues_vision
        from app.services.model_runtime import DETERMINISTIC_BENCHMARK_OPTIONS, effective_generation_options, generation_options
        observed = {}
        def response(**_kwargs):
            observed.update(effective_generation_options())
            return {"items": [{"region_id": 7, "action": "unchanged", "confidence": 0.98, "decision": "accept", "reason_code": "unchanged"}]}
        model.side_effect = response
        with generation_options(DETERMINISTIC_BENCHMARK_OPTIONS):
            _correct_dialogues_vision("page.jpg", self.original, None)
            self.assertEqual(effective_generation_options(), DETERMINISTIC_BENCHMARK_OPTIONS)
        self.assertEqual(observed["num_predict"], 512)
        self.assertEqual(observed["seed"], 424242)
        self.assertTrue(model.call_args.kwargs["json_mode"])


class DialogueCalibrationTests(unittest.TestCase):
    def base(self, **overrides):
        return {
            "raw_text": "CÔ GÁl TÊN LÀ \"RIN\"",
            "clean_text": "CÔ GÁI TÊN LÀ \"RIN\"",
            "confidence": 0.98,
            "ocr_confidence": 0.70,
            "text_similarity": 0.97,
            "correction_score": 0.80,
            "needs_review": False,
            "reason_code": "ocr_typo",
            **overrides,
        }

    def test_tiny_ocr_typo_is_safe(self):
        self.assertEqual(decide_dialogue_action(self.base())["decision"], "auto_accepted")

    def test_large_rewrite_stays_in_recovery(self):
        result = decide_dialogue_action(self.base(clean_text="NỘI DUNG HOÀN TOÀN KHÁC", text_similarity=0.3))
        self.assertEqual(result["decision"], "needs_recovery")

    def test_exact_correction_recovery_agreement(self):
        dialogue = self.base()
        recovery = {"recovered_text": dialogue["clean_text"], "confidence": 0.96, "reason_code": "ocr_typo"}
        self.assertTrue(correction_recovery_agree(dialogue, recovery))

    def test_disagreement_stays_review(self):
        dialogue = self.base()
        recovery = {"recovered_text": "KHÁC", "confidence": 0.99, "reason_code": "ocr_typo"}
        self.assertFalse(correction_recovery_agree(dialogue, recovery))

    def test_proper_name_uncertainty_stays_review(self):
        dialogue = self.base(reason_code="proper_name_uncertain")
        recovery = {"recovered_text": dialogue["clean_text"], "confidence": 0.99, "reason_code": "proper_name_uncertain"}
        self.assertFalse(correction_recovery_agree(dialogue, recovery))

    def test_ambiguous_visual_stays_review(self):
        dialogue = self.base(reason_code="ambiguous_visual")
        recovery = {"recovered_text": dialogue["clean_text"], "confidence": 0.99, "reason_code": "ambiguous_visual"}
        self.assertFalse(correction_recovery_agree(dialogue, recovery))

    def test_fragmented_ocr_requires_stronger_evidence(self):
        dialogue = self.base(reason_code="fragmented_ocr", confidence=0.97, ocr_confidence=0.79)
        recovery = {"recovered_text": dialogue["clean_text"], "confidence": 0.99, "reason_code": "fragmented_ocr"}
        self.assertFalse(correction_recovery_agree(dialogue, recovery))


if __name__ == "__main__":
    unittest.main()
