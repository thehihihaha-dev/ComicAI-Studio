import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.asset import Asset
from app.models.project import Project
from app.models.reader_router_validation_review import ReaderRouterValidationReview
from app.services.ocr_acceptance_router_experiment import STRUCTURAL, route
from app.services.reader_router_validation_review import crop_bytes, save_review, serialize_queue


class ReaderRouterValidationTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.Session=sessionmaker(bind=self.engine);self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.image=root/"source.png";Image.new("RGB",(120,100),"white").save(self.image);source_hash=hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.manifest=root/"manifest.json";self.manifest.write_text(json.dumps({"source_hash_separation_passed":True,"samples":[{"sample_id":"11.13:s1:LR_A","asset_id":"a","page_order":6,"source_hash":source_hash,"representation_hash":"rep","logical_region_id":"LR_A","bbox":[10,10,90,70],"prediction":"SECRET OCR","features":{"min_confidence":.99}}]}))
        db=self.Session();db.add(Project(id="p",name="P",content_type="short",status="ready",created_at=datetime.now(timezone.utc)));db.add(Asset(id="a",project_id="p",filename="source.png",file_type="image/png",file_path=str(self.image),page_order=6,created_at=datetime.now(timezone.utc),status="ready",vision_status="completed",dialogue_status="completed"));db.commit();db.close()
        self.queue_patch=patch("app.services.reader_router_validation_review.MANIFEST",self.manifest);self.queue_patch.start()

    def tearDown(self):
        self.queue_patch.stop();self.temp.cleanup();self.engine.dispose()

    def test_blinded_payload_and_human_persistence(self):
        db=self.Session();payload=serialize_queue(db,"p");item=payload["items"][0]
        self.assertEqual("PENDING",item["state"]);self.assertFalse({"prediction","confidence","features","r2_state","fragment_count"}&set(item))
        saved=save_review(db,"p",item["sample_id"],"VERIFIED","  Chữ người đọc\n");self.assertEqual("VERIFIED",saved["state"])
        db.expire_all();row=db.get(ReaderRouterValidationReview,item["sample_id"]);self.assertEqual("  Chữ người đọc\n",row.human_transcription);self.assertEqual("human",row.provenance)
        self.assertEqual("  Chữ người đọc\n",serialize_queue(db,"p")["items"][0]["human_transcription"]);db.close()

    def test_unreadable_and_source_revision_guard(self):
        db=self.Session();item=serialize_queue(db,"p")["items"][0];save_review(db,"p",item["sample_id"],"UNREADABLE",None)
        self.assertIsNone(db.get(ReaderRouterValidationReview,item["sample_id"]).human_transcription);self.assertTrue(crop_bytes(db,"p",item["sample_id"]))
        Image.new("RGB",(120,100),"black").save(self.image)
        with self.assertRaises(HTTPException):save_review(db,"p",item["sample_id"],"VERIFIED","X")
        self.assertEqual("SOURCE_UNAVAILABLE",serialize_queue(db,"p")["items"][0]["state"]);db.close()

    @patch("app.services.ollama_vision.call_vision_model")
    @patch("app.services.ocr_service.extract_ocr_blocks")
    def test_queue_has_zero_inference_calls(self,ocr,vision):
        db=self.Session();serialize_queue(db,"p");save_review(db,"p","11.13:s1:LR_A","UNREADABLE",None);ocr.assert_not_called();vision.assert_not_called();db.close()

    def test_frozen_r2_definition(self):
        base={"merge_split_warning":False,"boundary_clipping_warning":False,"min_confidence":.98}
        self.assertEqual("SAFE_CANDIDATE",route(base,"R2"));self.assertEqual("HARD",route({**base,"min_confidence":.979999},"R2"));self.assertEqual(STRUCTURAL,route({**base,"merge_split_warning":True},"R2"));self.assertEqual(STRUCTURAL,route({**base,"boundary_clipping_warning":True},"R2"))

    def test_repository_manifest_is_page_grouped_and_unseen(self):
        root=Path(__file__).resolve().parents[2];manifest=json.loads((root/"benchmarks/day11/reader-router-validation-manifest-11.13.json").read_text());calibration=json.loads((root/"benchmarks/day11/reader-logical-region-sample-11.11.json").read_text())
        validation={page["source_hash"] for page in manifest["pages"]};old={page["source_hash"] for page in calibration["pages"]}
        self.assertEqual(10,len(validation));self.assertFalse(validation&old);self.assertEqual(81,len(manifest["samples"]));self.assertTrue(manifest["selection_frozen_before_human_gt"])
        self.assertEqual({"name":"R2","confidence_threshold":.98,"requires_single_fragment":True,"requires_no_crop_boundary_warning":True},manifest["frozen_router"])

    def test_posthuman_artifacts_recompute_frozen_metrics(self):
        root=Path(__file__).resolve().parents[2];day=root/"benchmarks/day11"
        results=json.loads((day/"reader-router-validation-results-11.13.json").read_text());human=json.loads((day/"reader-router-validation-human-gt-11.13.json").read_text())
        self.assertEqual((81,71,10,0),(human["total_queue"],human["verified_regions"],human["unreadable_regions"],human["pending_regions"]))
        self.assertTrue(all(row["provenance"]=="human" for row in human["samples"]))
        verified=[row for row in results["samples"] if row["state"]=="VERIFIED"]
        unreadable=[row for row in results["samples"] if row["state"]=="UNREADABLE"]
        states=[route(row["features"],"R2") for row in verified]
        safe=[row for row,state in zip(verified,states) if state=="SAFE_CANDIDATE"]
        metrics=results["metrics_verified_only"]
        self.assertEqual(71,len(verified));self.assertEqual(10,len(unreadable));self.assertEqual(1,len(safe))
        self.assertEqual(0,sum(row["exact"] for row in safe));self.assertEqual(1,metrics["false_safe"])
        self.assertEqual(21,states.count("HARD"));self.assertEqual(49,states.count("STRUCTURAL_REVIEW"))
        unreadable_states=[route(row["features"],"R2") for row in unreadable]
        self.assertEqual((2,8,0),(unreadable_states.count("SAFE_CANDIDATE"),unreadable_states.count("HARD"),unreadable_states.count("STRUCTURAL_REVIEW")))

    def test_posthuman_leakage_preservation_and_decision(self):
        root=Path(__file__).resolve().parents[2];day=root/"benchmarks/day11"
        summary=json.loads((day/"reader-router-validation-summary-11.13.json").read_text());errors=json.loads((day/"reader-router-validation-errors-11.13.json").read_text())
        self.assertTrue(all(summary["leakage_checks"].values()));self.assertTrue(all(summary["preservation"][key] for key in ("manifest_unchanged","authoritative_state_unchanged")))
        self.assertEqual("C. R2 GENERALIZATION FAIL",summary["decision"]);self.assertEqual(1,errors["high_confidence_wrong_count"])
        self.assertTrue(errors["any_high_confidence_wrong_satisfied_all_safe_conditions"]);self.assertEqual(2,len(errors["unreadable_safe_risk_samples"]))
        self.assertEqual((0,0,0),(summary["resource_safety"]["ocr_inference_calls"],summary["resource_safety"]["vlm_calls"],summary["resource_safety"]["ollama_calls"]))


if __name__=="__main__":unittest.main()
