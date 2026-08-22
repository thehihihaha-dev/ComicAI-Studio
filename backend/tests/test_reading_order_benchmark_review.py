import json, tempfile, unittest
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
from app.models.reading_order_benchmark_review import ReadingOrderBenchmarkReview
from app.services.reading_order_benchmark_review import load_queue, ordering_metrics, save_review, serialize_queue
sys_path = str(Path(__file__).resolve().parents[2] / "scripts")
import sys
if sys_path not in sys.path: sys.path.insert(0, sys_path)
from reading_order_posthuman_11_9 import group_accuracy, normalized_groups


class ReadingOrderReviewTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool);Base.metadata.create_all(self.engine);self.Session=sessionmaker(bind=self.engine)
  self.temp=tempfile.TemporaryDirectory();self.image=Path(self.temp.name)/"page.png";Image.new("RGB",(200,200),"white").save(self.image)
  db=self.Session();now=datetime.now(timezone.utc)
  db.add_all([Project(id="p1",name="P1",content_type="short",status="ready",created_at=now),Project(id="p2",name="P2",content_type="short",status="ready",created_at=now)])
  blocks=[{"box":[[10,10],[40,10],[40,30],[10,30]]},{"box":[[100,10],[140,10],[140,30],[100,30]]}]
  db.add(Asset(id="a1",project_id="p1",filename="page.png",file_type="image/png",file_path=str(self.image),page_order=1,created_at=now,status="ready",ocr_blocks=json.dumps(blocks),vision_regions=json.dumps([{"id":1,"type":"dialogue","block_ids":[0]},{"id":2,"type":"narration","block_ids":[1]}]),vision_status="completed",dialogue_status="completed"));db.commit();db.close()
 def tearDown(self):self.temp.cleanup();self.engine.dispose()
 def test_queue_prediction_visible_but_opening_does_not_verify(self):
  db=self.Session();payload=serialize_queue(db,"p1");self.assertEqual((payload["total"],payload["verified"],payload["pending"]),(1,0,1));self.assertEqual(payload["items"][0]["predicted_sequence"],[2,1]);self.assertIsNone(payload["items"][0]["human_sequence"]);db.close()
 def test_save_reload_duplicate_and_prediction_separation(self):
  db=self.Session();row=load_queue(db,"p1")[0];pred=list(row.predicted_sequence);groups=[{"group_id":"panel-a","region_ids":[1,2]}]
  first=save_review(db,"p1",row.review_id,[1,2],groups,{"1":"ORPHAN"});second=save_review(db,"p1",row.review_id,[1,2],groups,{"1":"ORPHAN"});self.assertEqual(first["revision"],second["revision"]);db.expire_all();saved=db.get(ReadingOrderBenchmarkReview,row.review_id);self.assertEqual(saved.predicted_sequence,pred);self.assertEqual(saved.human_sequence,[1,2]);self.assertEqual(serialize_queue(db,"p1")["verified"],1);db.close()
 def test_incomplete_duplicate_and_project_isolation_rejected(self):
  db=self.Session();row=load_queue(db,"p1")[0]
  for seq in ([1],[1,1]):
   with self.assertRaises(HTTPException):save_review(db,"p1",row.review_id,seq,[{"group_id":"P","region_ids":seq}],{})
  with self.assertRaises(HTTPException):save_review(db,"p2",row.review_id,[1,2],[{"group_id":"P","region_ids":[1,2]}],{});db.close()
 def test_source_hash_change_invalidates_review(self):
  db=self.Session();row=load_queue(db,"p1")[0];Image.new("RGB",(200,200),"black").save(self.image)
  with self.assertRaises(HTTPException):save_review(db,"p1",row.review_id,[1,2],[{"group_id":"P","region_ids":[1,2]}],{})
  self.assertEqual(serialize_queue(db,"p1")["items"][0]["state"],"SOURCE_UNAVAILABLE");db.close()
 def test_metrics_are_deterministic_and_expose_partial_error(self):
  expected={"exact":False,"pairwise_total":3,"inversions":1,"pairwise_accuracy":2/3,"corrections":2}
  self.assertEqual(ordering_metrics([1,2,3],[1,3,2]),expected);self.assertEqual(ordering_metrics([1,2,3],[1,3,2]),expected)
 def test_group_metric_separates_membership_from_region_order(self):
  predicted=[{"group_id":"P1","region_ids":[1,2]},{"group_id":"P2","region_ids":[3]}]
  self.assertTrue(group_accuracy(predicted,[{"group_id":"P1","region_ids":[2,1]},{"group_id":"P2","region_ids":[3]}])["exact"])
  self.assertFalse(group_accuracy(predicted,[{"group_id":"P2","region_ids":[3]},{"group_id":"P1","region_ids":[1,2]}])["exact"])
  self.assertEqual(normalized_groups(predicted),normalized_groups(predicted))
 @patch("app.services.ollama_vision.call_vision_model")
 @patch("app.services.ollama_text.call_text_model")
 def test_zero_model_calls(self,text,vision):
  db=self.Session();serialize_queue(db,"p1");text.assert_not_called();vision.assert_not_called();db.close()

if __name__=="__main__":unittest.main()
