"""Unit tests for Day 15 Phase 2: Text Post-Processing & Structured Script Assembly.

Verifies:
1. Specific OCR cleaning cases (TÔ1 -> TÔI, Mìnb -> Mình, diacritic and punctuation repair).
2. Fail-closed fallback: Empty or degenerate cleaning preserves raw text safely.
3. Structural integrity of assembled script: 10 pages, 50 dialogues, 0 missing bubbles.
4. Determinism: Repeated assembly runs yield 100% identical outputs.
"""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day15_cleaner import (
    DialogueScriptAssembler,
    MangaTextCleaner,
)


class Day15CleanerTests(unittest.TestCase):

    def setUp(self):
        self.cleaner = MangaTextCleaner()
        self.assembler = DialogueScriptAssembler(cleaner=self.cleaner)

        self.raw_doc = json.loads(
            (ROOT / "benchmarks" / "day15" / "day15-ocr-raw-extraction.json").read_text(encoding="utf-8")
        )
        self.eval_doc = json.loads(
            (ROOT / "benchmarks" / "day14" / "day14-full-realistic-evaluation.json").read_text(encoding="utf-8")
        )
        self.audit_doc = json.loads(
            (ROOT / "benchmarks" / "day12" / "panel-relation-model-input-audit-12.7.json").read_text(encoding="utf-8")
        )

    def test_cleaner_specific_cases(self):
        """Common optical OCR misreads must be repaired deterministically."""
        cases = [
            ("CHÚNG TÔ1", "CHÚNG TÔI"),
            ("Mìnb là Rin", "Mình là Rin"),
            ("VÓl NHAU", "VỚI NHAU"),
            ("KẾT HÔN RỒl", "KẾT HÔN RỒI"),
            ("THÔl SAO!?", "THÔI SAO!?"),
            ("CÁl NÀY", "CÁI NÀY"),
            ("4 NĂM TRUớc _", "4 NĂM TRUớc..."),
            ("Con XIN THỀ !", "Con XIN THỀ!"),
            ("Hôy", "Hầy"),
        ]
        for raw, expected in cases:
            cleaned = self.cleaner.clean_text(raw)
            self.assertEqual(cleaned, expected, f"Failed cleaning '{raw}' -> got '{cleaned}', expected '{expected}'")

    def test_cleaner_fail_closed_fallback(self):
        """Degenerate text must not disappear or become empty."""
        self.assertEqual(self.cleaner.clean_text(""), "")
        self.assertEqual(self.cleaner.clean_text("   "), "   ")
        # Text with only punctuation/symbols must be preserved
        self.assertEqual(self.cleaner.clean_text("..."), "...")

    def test_assembler_structural_integrity(self):
        """Assembled script must contain exactly 10 pages, 50 dialogues, and 0 unassigned bubbles."""
        script = self.assembler.assemble_script(self.raw_doc, self.eval_doc, self.audit_doc)

        self.assertEqual(len(script["pages"]), 10)
        self.assertEqual(len(script["dialogues"]), 50)
        self.assertEqual(script["summary"]["total_dialogues"], 50)
        self.assertEqual(script["summary"]["total_pages"], 10)

        # Check dialogue ID format and sequential order
        for idx, d in enumerate(script["dialogues"], 1):
            self.assertTrue(d["dialogue_id"].startswith("D_P"))
            self.assertNotEqual(d["panel_id"], "UNASSIGNED", f"Dialogue {d['dialogue_id']} has unassigned panel")
            self.assertGreater(len(d["cleaned_text"]), 0)
            self.assertEqual(len(d["bbox"]), 4)

        # Check per-page sequence
        for page in script["pages"]:
            page_bubbles = [b for panel in page["panels"] for b in panel["dialogues"]]
            indices = sorted(b["reading_order_index"] for b in page_bubbles)
            self.assertEqual(indices, list(range(1, len(page_bubbles) + 1)))

    def test_assembler_determinism_10_runs(self):
        """Multiple assembly runs must produce identical SHA-256 digests."""
        def run_hash():
            script = self.assembler.assemble_script(self.raw_doc, self.eval_doc, self.audit_doc)
            data = json.dumps(script, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(data.encode("utf-8")).hexdigest()

        base_hash = run_hash()
        for _ in range(9):
            self.assertEqual(run_hash(), base_hash, "Nondeterministic script assembly detected!")


if __name__ == "__main__":
    unittest.main()

