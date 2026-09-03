import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAY12 = ROOT / "benchmarks/day12"
OLD_SNAPSHOT = "d49cc0aab140a743317bbb36a3f53a74ecf1c2305f279ccb75d306855e9e3b1c"


class InvalidPanelGroundTruthAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((DAY12 / "panel-human-gt-invalid-coordinate-audit-12.2.json").read_text())
        cls.sources = {int(item["page_order"]): item for item in
                       json.loads((DAY12 / "panel-extraction-input-audit-12.2.json").read_text())["inputs"]}

    def test_invalid_evidence_is_explicitly_non_authoritative(self):
        self.assertEqual(self.audit["status"], "INVALID_COORDINATE_SYSTEM")
        self.assertEqual(self.audit["authority"], "NOT AUTHORITATIVE GT")
        self.assertFalse(self.audit["old_gt_active"])
        self.assertFalse(self.audit["new_gt_used_for_recovery"])

    def test_exact_pages_counts_and_source_hashes(self):
        self.assertEqual(self.audit["affected_pages"], [1, 2, 15, 17])
        self.assertEqual(self.audit["original_panel_counts"], {"1": 3, "2": 2, "15": 3, "17": 5})
        self.assertEqual(self.audit["original_annotation_count"], 13)
        for page in self.audit["pages"]:
            self.assertEqual(page["source_image_hash"], self.sources[page["page_order"]]["source_hash"])

    def test_recovered_material_reproduces_known_snapshot(self):
        material = [{"id": page["review_id"], "state": page["original_state"],
                     "revision": page["original_revision"], "panels": page["original_boxes"],
                     "hash": page["source_image_hash"]} for page in self.audit["pages"]]
        encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), OLD_SNAPSHOT)
        self.assertEqual(self.audit["snapshot_verification"], "EXACT_MATCH")

    def test_frozen_prediction_fingerprint(self):
        current = hashlib.sha256((DAY12 / "panel-predictions-12.2.json").read_bytes()).hexdigest()
        self.assertEqual(current, "80e46d5c6216e3d18e9686af149a0012911795a246d1323ae4bb74d516b4b735")
        self.assertEqual(self.audit["frozen_prediction_file_sha256"], current)


if __name__ == "__main__":
    unittest.main()
