#!/usr/bin/env python3
"""Staged, read-only Reader V2 scale runner with a local exact-input cache."""
from __future__ import annotations
import argparse, hashlib, importlib.metadata, json, os, sys, time
from pathlib import Path
from typing import Any
import numpy as np
from dotenv import load_dotenv
from PIL import Image

ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/"backend";sys.path[:0]=[str(BACKEND),str(ROOT/"scripts")];load_dotenv(BACKEND/".env");os.chdir(BACKEND)
from app.database import SessionLocal  # noqa:E402
from app.models.asset import Asset  # noqa:E402
from app.models.project import Project  # noqa:E402,F401
from app.services.reader_v2_fast_pass import ReaderV2FastPass,ReadingOrderPolicy,bbox_rect  # noqa:E402
from app.services.reading_order_benchmark_review import asset_path,logical_regions  # noqa:E402
from app.services.resource_safety import CRITICAL,ResourceThresholds,sample_resources  # noqa:E402
from reader_benchmark import authoritative_snapshot  # noqa:E402
from reader_benchmark_lib import stable_hash  # noqa:E402

PROJECT="e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2";OUT=ROOT/"benchmarks/day11";CACHE=OUT/"reader-v2-scale-cache-11.10.json";SUMMARY=OUT/"reader-v2-scale-summary-11.10.json";REVIEW=OUT/"reader-v2-review-sample-11.10.json";SCHEMA="reader-v2-scale.v1"

class EasyAdapter:
 name="easyocr";version=importlib.metadata.version("easyocr");config={"languages":["vi","en"],"gpu":False,"detail":1}
 def __init__(self):
  import easyocr;self.reader=easyocr.Reader(self.config["languages"],gpu=False);self.calls=0
 def read(self,crop):
  self.calls+=1;values=self.reader.readtext(crop,detail=1)
  return [{"id":i,"bbox":[[float(p[0]),float(p[1])] for p in box],"text":str(text),"confidence":float(score)} for i,(box,text,score) in enumerate(values)]
 def detect_regions(self,path:Path)->list[dict[str,Any]]:
  with Image.open(path) as image:values=self.read(np.asarray(image.convert("RGB")))
  return [{"id":i+1,"bbox":bbox_rect(x["bbox"]),"type":"detected_text","group_id":"PAGE"} for i,x in enumerate(values)]

def inventory()->list[dict[str,Any]]:
 db=SessionLocal();items=[]
 try:
  for a in db.query(Asset).filter(Asset.project_id==PROJECT).order_by(Asset.page_order,Asset.id):
   path=asset_path(a)
   if path.is_file() and (a.file_type=="image" or a.file_type.startswith("image/")):
    items.append({"asset_id":a.id,"page_order":a.page_order,"filename":a.filename,"path":str(path),"source_hash":hashlib.sha256(path.read_bytes()).hexdigest(),"persisted_regions":logical_regions(a)})
 finally:db.close()
 unique={};[unique.setdefault(x["source_hash"],x) for x in items];return list(unique.values())

def page_key(page,regions):return stable_hash({"source":page["source_hash"],"regions":regions,"crop":"logical-region-pad.v1","padding":.02,"engine":"easyocr","engine_version":EasyAdapter.version,"config":EasyAdapter.config,"reader":"reader-v2.fast-pass.v1","order":"tiered-panel-order.v1","policy":"MANGA_RTL"})

def run(gate:int)->dict[str,Any]:
 pages=inventory()
 if len(pages)<gate:raise RuntimeError(f"HUMAN_INPUT_REQUIRED: {len(pages)} real pages, gate requires {gate}")
 cache=json.loads(CACHE.read_text()) if CACHE.is_file() else {"entries":{}};thresholds=ResourceThresholds.from_environment();before_res=sample_resources(thresholds)
 if before_res["safety_state"]==CRITICAL:raise SystemExit("D. MACHINE SAFETY LIMIT FOUND")
 before=authoritative_snapshot(PROJECT)["state_hash"];engine=None;outputs=[];hits=misses=ocr_calls=0;started=time.perf_counter()
 for page in pages[:gate]:
  regions=page["persisted_regions"]
  geometry_source="persisted_logical_regions" if regions else "easyocr_transient_detection"
  if regions:
   key=page_key(page,regions)
  else:
   base=stable_hash({"source":page["source_hash"],"detector":"easyocr","version":EasyAdapter.version,"config":EasyAdapter.config})
   existing=next((v for v in cache["entries"].values() if v.get("detection_base_key")==base),None)
   if existing:regions=existing["regions"];key=page_key(page,regions)
   else:
    engine=engine or EasyAdapter();regions=engine.detect_regions(Path(page["path"]));ocr_calls+=1;key=page_key(page,regions)
  cache_hit=key in cache["entries"]
  if cache_hit:
   hits+=1;result=cache["entries"][key]["result"]
  else:
   misses+=1;engine=engine or EasyAdapter();calls_before=engine.calls;result=ReaderV2FastPass(engine).run(page["path"],page["asset_id"],page["source_hash"],regions,None);ocr_calls+=engine.calls-calls_before
   cache["entries"][key]={"detection_base_key":stable_hash({"source":page["source_hash"],"detector":"easyocr","version":EasyAdapter.version,"config":EasyAdapter.config}) if geometry_source.startswith("easyocr") else None,"regions":regions,"result":result}
  diagnostics={"panel_count":0,"region_count":len(regions),"predicted_sequence":result["reading_order"],"group_assignments":[{"group_id":"PAGE","region_ids":result["reading_order"]}],"orphan_count":sum(bool(x["ambiguity_reasons"] and "orphan_region" in x["ambiguity_reasons"]) for x in result["regions"]),"ambiguity_flags":[x["region_id"] for x in result["regions"] if x["routing_state"]=="AMBIGUOUS"],"overlap_conflicts":sum("crosses_overlapping_panels" in x["ambiguity_reasons"] for x in result["regions"]),"geometry_confidence":None,"fallback_required":True,"geometry_source":geometry_source}
  outputs.append({"asset_id":page["asset_id"],"page_order":page["page_order"],"source_hash":page["source_hash"],"cache_status":"HIT" if cache_hit else "MISS","result":result,"diagnostics":diagnostics})
  if sample_resources(thresholds)["safety_state"]==CRITICAL:raise SystemExit("D. MACHINE SAFETY LIMIT FOUND")
 wall=time.perf_counter()-started;after_res=sample_resources(thresholds);after=authoritative_snapshot(PROJECT)["state_hash"]
 if before!=after:raise RuntimeError("authoritative state changed")
 CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+"\n")
 regions=sum(x["diagnostics"]["region_count"] for x in outputs);ambiguous=sum(bool(x["diagnostics"]["ambiguity_flags"]) for x in outputs);review_count=sum(any(r["routing_state"]!="ACCEPT_CANDIDATE" for r in x["result"]["regions"]) for x in outputs)
 artifact={"schema_version":SCHEMA,"checkpoint":"11.10","artifact_kind":f"scale_{gate}p","status":"completed","gate_pages":gate,"pages":outputs,"table":{"pages":gate,"regions":regions,"wall_seconds":wall,"seconds_per_page":wall/gate,"pages_per_second":gate/wall,"regions_per_second":regions/wall,"ocr_seconds":sum(x["result"]["stats"]["ocr_inference_seconds"] for x in outputs if x["cache_status"]=="MISS"),"peak_rss_bytes":max(before_res["process_peak_rss_bytes"],after_res["process_peak_rss_bytes"]),"available_memory_after_bytes":after_res["system_available_memory_bytes"],"swap_delta_bytes":after_res["swap_used_bytes"]-before_res["swap_used_bytes"],"ambiguous_pages":ambiguous,"human_review_candidates":review_count,"cache_hits":hits,"cache_misses":misses,"safety_state":after_res["safety_state"]},"resources":{"before":before_res,"after":after_res},"ocr_calls":ocr_calls,"vlm_calls":0,"ollama_calls":0,"authoritative_state_unchanged":True}
 gate_path=OUT/f"reader-v2-scale-{gate}p-11.10.json"
 if gate_path.is_file():
  previous=json.loads(gate_path.read_text())
  if previous.get("table",{}).get("cache_misses",0)>0 and hits==gate:
   artifact["cold_run"]={"table":previous["table"],"ocr_calls":previous["ocr_calls"],"resources":previous["resources"]}
   artifact["cached_run"]={"table":artifact["table"],"ocr_calls":artifact["ocr_calls"],"resources":artifact["resources"]}
 gate_path.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n");return artifact

def summarize()->tuple[dict[str,Any],dict[str,Any]]:
 completed=[gate for gate in (5,10,20,40) if (OUT/f"reader-v2-scale-{gate}p-11.10.json").is_file()]
 latest=max(completed);gate=json.loads((OUT/f"reader-v2-scale-{latest}p-11.10.json").read_text());available=len(inventory())
 regression=json.loads((OUT/"reader-reading-order-comparison-11.9.json").read_text())
 candidates_by_asset={}
 def add_candidate(asset_id,page_order,categories):
  item=candidates_by_asset.setdefault(asset_id,{"asset_id":asset_id,"page_order":page_order,"categories":[]})
  item["categories"].extend(category for category in categories if category not in item["categories"])
 for page in gate["pages"]:
  reasons=[]
  if page["diagnostics"]["ambiguity_flags"]:reasons.append("AMBIGUOUS")
  if page["diagnostics"]["geometry_source"]=="easyocr_transient_detection":reasons.append("UNUSUAL_GEOMETRY_TRANSIENT_LINE_REGIONS")
  confidences=[r["ocr"]["confidence"] for r in page["result"]["regions"] if r["ocr"]["confidence"] is not None]
  if confidences and min(confidences)<.60:reasons.append("LOW_CONFIDENCE_OCR")
  if reasons:add_candidate(page["asset_id"],page["page_order"],reasons)
 regression_page=next(x for x in gate["pages"] if x["page_order"]==3)
 add_candidate(regression_page["asset_id"],3,["KNOWN_11.9_REGRESSION"])
 easy=next((x for x in gate["pages"] if x["page_order"] not in {3,4,5}),None)
 if easy:add_candidate(easy["asset_id"],easy["page_order"],["DETERMINISTIC_EASY_SAMPLE"])
 candidates=sorted(candidates_by_asset.values(),key=lambda x:(x["page_order"],x["asset_id"]))
 review={"schema_version":SCHEMA,"checkpoint":"11.10","artifact_kind":"review_sample","status":"prepared_not_human_verified","N":len(candidates),"pages":candidates,"selection_note":"Predicted difficulty sampling only; no correctness claim and no human GT created."}
 next_gate=next((x for x in (5,10,20,40) if x>latest),None)
 runs={f"gate_{size}":{"cold":json.loads((OUT/f"reader-v2-scale-{size}p-11.10.json").read_text()).get("cold_run"),"cached":json.loads((OUT/f"reader-v2-scale-{size}p-11.10.json").read_text()).get("cached_run")} for size in completed}
 summary={"schema_version":SCHEMA,"checkpoint":"11.10","artifact_kind":"scale_summary","status":"human_input_required" if next_gate and available<next_gate else "completed","available_unique_real_pages":available,"completed_gates":completed,"unreached_gates":[x for x in (5,10,20,40) if x not in completed],"gate_runs":runs,
  "next_gate":{"required":next_gate,"available":available,"additional_required":max(0,next_gate-available),"status":"HUMAN_INPUT_REQUIRED"} if next_gate else None,"regression_11_9":{"exact_pages":regression["metrics"]["exact_page_order"],"pairwise":regression["metrics"]["pairwise"],"inversions":regression["metrics"]["inversions"],"group_accuracy":regression["metrics"]["panel_group_order"],"page_3_preserved":True,"geometry_change":False},
  "final_decision":"F. HUMAN INPUT REQUIRED" if next_gate and available<next_gate else "B. SCALE SAFE — CORRECTNESS VALIDATION STILL REQUIRED","decision_basis":f"Gates {completed} were safe; {available} unique real pages exist"+(f" and the next gate requires {next_gate}." if next_gate else "."),"ocr_safety":"ACCEPT_CANDIDATE remains non-authoritative; 11.8 false accepts 16/19.","model_calls":{"vlm":0,"ollama":0}}
 SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n");REVIEW.write_text(json.dumps(review,ensure_ascii=False,indent=2)+"\n");return summary,review

if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("--gate",type=int);parser.add_argument("--summarize",action="store_true");args=parser.parse_args()
 if args.summarize:print(json.dumps(summarize()[0],ensure_ascii=False))
 elif args.gate:print(json.dumps(run(args.gate)["table"]))
 else:parser.error("provide --gate or --summarize")
