import hashlib,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.models.asset import Asset
from app.models.project import Project
from app.models.reader_correctness_review import ReaderCorrectnessReview
from app.models.reader_logical_review import ReaderLogicalReview
from app.services.reader_logical_review import save_order,save_transcription
class ClickOrderGTTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool);Base.metadata.create_all(self.engine);self.Session=sessionmaker(bind=self.engine);self.temp=tempfile.TemporaryDirectory();self.image=Path(self.temp.name)/"p.png";Image.new("RGB",(100,100),"white").save(self.image);h=hashlib.sha256(self.image.read_bytes()).hexdigest();db=self.Session();now=datetime.now(timezone.utc);db.add(Project(id="p",name="P",content_type="short",status="ready",created_at=now));db.add(Asset(id="a",project_id="p",filename="p.png",file_type="image/png",file_path=str(self.image),page_order=1,created_at=now,status="ready"));db.add(ReaderCorrectnessReview(review_id="old",project_id="p",asset_id="a",page_order=1,source_image_hash=h,selection_reasons=[],predicted_regions=[],predicted_sequence=[],predicted_groups=[],predicted_ambiguity={},human_sequence=[9],human_groups=[{"group_id":"old","region_ids":[9]}],reading_state="VERIFIED",ocr_reviews={}));db.add(ReaderLogicalReview(review_id="new",project_id="p",asset_id="a",page_order=1,source_image_hash=h,representation_version="logical.v1",representation_hash="hash",logical_regions=[{"logical_region_id":"A","bbox":[0,0,20,20]},{"logical_region_id":"B","bbox":[30,0,50,20]},{"logical_region_id":"C","bbox":[60,0,80,20]}],state="PENDING"));db.commit();db.close()
 def tearDown(self):self.temp.cleanup();self.engine.dispose()
 def test_click_first_second_and_reload_persistence(self):
  db=self.Session();save_order(db,"p","new",["B"],[],False);save_order(db,"p","new",["B","A"],[],False);db.expire_all();self.assertEqual(["B","A"],db.get(ReaderLogicalReview,"new").human_ordered_region_ids);db.close()
 def test_undo_last_and_reset_order_persist(self):
  db=self.Session();save_order(db,"p","new",["A","B"],[],False);save_order(db,"p","new",["A"],[],False);self.assertEqual(["A"],db.get(ReaderLogicalReview,"new").human_ordered_region_ids);save_order(db,"p","new",[],[],False);self.assertEqual([],db.get(ReaderLogicalReview,"new").human_ordered_region_ids);db.close()
 def test_exclude_and_undo_exclusion_never_orders_region(self):
  db=self.Session();save_order(db,"p","new",["A"],["B"],False);row=db.get(ReaderLogicalReview,"new");self.assertNotIn("B",row.human_ordered_region_ids);self.assertIn("B",row.human_excluded_region_ids);save_order(db,"p","new",["A"],[],False);self.assertEqual([],db.get(ReaderLogicalReview,"new").human_excluded_region_ids);db.close()
 def test_page_verify_requires_all_regions_resolved(self):
  db=self.Session()
  with self.assertRaises(HTTPException):save_order(db,"p","new",["A"],["B"],True)
  result=save_order(db,"p","new",["B","A"],["C"],True);self.assertEqual("VERIFIED",result["state"]);self.assertEqual(["B","A"],result["ordered_region_ids"]);db.close()
 def test_edit_transcription_reload_and_old_gt_prediction_preservation(self):
  db=self.Session();old_before=list(db.get(ReaderCorrectnessReview,"old").human_sequence);save_transcription(db,"p","new","A","Chữ đúng");save_order(db,"p","new",["A","B","C"],[],True);db.expire_all();self.assertEqual("Chữ đúng",db.get(ReaderLogicalReview,"new").human_transcriptions["A"]);self.assertEqual(old_before,db.get(ReaderCorrectnessReview,"old").human_sequence);self.assertIsNone(db.get(ReaderLogicalReview,"new").human_panel_order);db.close()
 def test_source_hash_mismatch_rejected(self):
  db=self.Session();Image.new("RGB",(100,100),"black").save(self.image)
  with self.assertRaises(HTTPException):save_order(db,"p","new",["A","B","C"],[],True)
  with self.assertRaises(HTTPException):save_transcription(db,"p","new","A","x")
  db.close()
 def test_zero_model_fields_are_not_part_of_human_mutation(self):
  db=self.Session();result=save_order(db,"p","new",["A","B","C"],[],True);self.assertNotIn("prediction",result);self.assertNotIn("model_calls",result);db.close()
if __name__=="__main__":unittest.main()
