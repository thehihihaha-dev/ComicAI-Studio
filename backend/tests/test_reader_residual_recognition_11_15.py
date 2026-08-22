import hashlib,json,unittest
from pathlib import Path


class ResidualRecognition115Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.day=Path(__file__).resolve().parents[2]/"benchmarks/day11"
        cls.manifest=json.loads((cls.day/"reader-residual-recognition-manifest-11.15.json").read_text())
        cls.control=json.loads((cls.day/"reader-residual-recognition-control-11.15.json").read_text())
        cls.candidate=json.loads((cls.day/"reader-residual-recognition-candidate-11.15.json").read_text())
        cls.errors=json.loads((cls.day/"reader-residual-recognition-errors-11.15.json").read_text())
        cls.summary=json.loads((cls.day/"reader-residual-recognition-summary-11.15.json").read_text())

    def test_frozen_identity_and_candidate_protocol(self):
        replay=self.day/"reader-structural-replay-11.14.json";human=self.day/"reader-router-validation-human-gt-11.13.json"
        self.assertEqual(hashlib.sha256(replay.read_bytes()).hexdigest(),self.manifest["frozen_replay_sha256"])
        self.assertEqual(hashlib.sha256(human.read_bytes()).hexdigest(),self.manifest["frozen_human_sha256"])
        candidate=self.manifest["candidate"];self.assertEqual("PP-OCRv6_medium_rec",candidate["model"]);self.assertEqual({"paddlex":"3.7.2","paddleocr":"3.7.0","paddlepaddle":"3.2.1"},candidate["framework_versions"]);self.assertEqual(3,len(candidate["model_file_sha256"]));self.assertTrue(candidate["recognizer_only"]);self.assertFalse(candidate["detector_used"]);self.assertEqual([],candidate["downloads"])

    def test_primary_metrics_and_residual_math(self):
        metrics=self.summary["metrics"];self.assertEqual((8,6),(metrics["A"]["exact"],metrics["D"]["exact"]));self.assertEqual((3,5),(metrics["D"]["wrong_to_correct"],metrics["D"]["correct_to_wrong"]))
        residual=self.summary["residual"];self.assertEqual(63,residual["n"]);self.assertEqual(3,residual["repaired_exact"]);self.assertAlmostEqual(3/63,residual["repair_rate"])
        self.assertEqual((6,4,53),(residual["improved"],residual["unchanged"],residual["regressed"]))

    def test_breakdown_disagreement_oracle_and_false_safe(self):
        hard=self.summary["breakdown"]["HARD"];structural=self.summary["breakdown"]["STRUCTURAL_REVIEW"]
        self.assertEqual((3,0),(hard["repairs"],structural["repairs"]));self.assertEqual(48,structural["regressed"])
        self.assertEqual({"different":65,"easy_correct_candidate_wrong":5,"both_wrong":57,"easy_wrong_candidate_correct":3,"equal":6},self.summary["disagreement"])
        oracle=self.summary["oracle_upper_bound_not_production_achievable"];self.assertEqual((11,71),(oracle["exact"],oracle["n"]));self.assertFalse(self.summary["false_safe_replay"]["repaired"])

    def test_unreadable_is_diagnostic_only_and_models_zero(self):
        rows=self.candidate["unreadable_diagnostic"];self.assertEqual(10,len(rows));self.assertTrue(all(row["human_state"]=="UNREADABLE" for row in rows));self.assertTrue(all("score" not in mode for row in rows for mode in row["modes"].values()))
        performance=self.summary["performance"];self.assertEqual(162,performance["ocr_calls"]);self.assertEqual((0,0),(performance["vlm_calls"],performance["ollama_calls"]));self.assertEqual("NORMAL",performance["resources"]["resource_guard"])
        self.assertTrue(all(self.summary["safety"][key] for key in ("human_gt_unchanged","r2_unchanged","reading_order_unchanged","production_ocr_unchanged","authoritative_state_unchanged")))

    def test_decision_and_non_deployable_oracle_label(self):
        self.assertEqual("C. CANDIDATE DOES NOT JUSTIFY COST",self.summary["decision"]);self.assertIn("not_production_achievable",next(key for key in self.summary if key.startswith("oracle_")))


if __name__=="__main__":unittest.main()
