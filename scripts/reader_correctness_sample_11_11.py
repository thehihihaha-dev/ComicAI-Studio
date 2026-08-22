#!/usr/bin/env python3
"""Build the deterministic, stratified 11.11 human-review sample from cached Gate D."""
from __future__ import annotations
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/"benchmarks/day11/reader-v2-scale-40p-11.10.json";OUT=ROOT/"benchmarks/day11/reader-v2-correctness-review-sample-11.11.json"

def score(page):
 regions=page["result"]["regions"];conf=[r["ocr"]["confidence"] for r in regions if r["ocr"]["confidence"] is not None]
 return {"non_accept":sum(r["routing_state"]!="ACCEPT_CANDIDATE" for r in regions),"min_conf":min(conf,default=0),"has_conf":bool(conf),"regions":len(regions),"transient":page["diagnostics"]["geometry_source"]=="easyocr_transient_detection"}

def build():
 gate=json.loads(SOURCE.read_text());pages=gate["pages"];metrics={p["asset_id"]:score(p) for p in pages};selected={}
 def take(candidates,n,reason):
  for page in candidates:
   if len([x for x in selected.values() if reason in x])>=n:break
   selected.setdefault(page["asset_id"],[]).append(reason)
 regression=next(p for p in pages if p["page_order"]==3);selected[regression["asset_id"]]=["REGRESSION_11_9_PAGE_3"]
 take(sorted((p for p in pages if metrics[p["asset_id"]]["non_accept"]),key=lambda p:(-metrics[p["asset_id"]]["non_accept"],p["page_order"])),2,"FLAGGED_NEEDS_HUMAN_REVIEW")
 take(sorted((p for p in pages if metrics[p["asset_id"]]["transient"]),key=lambda p:(-metrics[p["asset_id"]]["regions"],p["page_order"])),1,"UNUSUAL_GEOMETRY")
 take(sorted((p for p in pages if metrics[p["asset_id"]]["has_conf"]),key=lambda p:(metrics[p["asset_id"]]["min_conf"],p["page_order"])),2,"LOW_CONFIDENCE_OCR")
 take(sorted((p for p in pages if metrics[p["asset_id"]]["non_accept"]==0),key=lambda p:(-metrics[p["asset_id"]]["min_conf"],p["page_order"])),2,"HIGH_CONFIDENCE_EASY")
 ordinary=[p for p in pages if p["asset_id"] not in selected]
 ordinary.sort(key=lambda p:hashlib.sha256(f"11.11:{p['source_hash']}".encode()).hexdigest())
 take(ordinary,2,"RANDOM_ORDINARY")
 for page in sorted(pages,key=lambda p:p["page_order"]):
  if len(selected)>=10:break
  selected.setdefault(page["asset_id"],[]).append("STRATIFIED_FILL")
 output=[]
 for page in pages:
  if page["asset_id"] not in selected:continue
  regions=[{"region_id":r["region_id"],"bbox":r["bbox"],"crop_bbox":r["crop_bbox"],"region_type":r["region_type"],"ocr_confidence":r["ocr"]["confidence"],"predicted_text":r["ocr"]["text"],"routing_state":r["routing_state"],"quality_signals":r["quality_signals"],"ambiguity_reasons":r["ambiguity_reasons"]} for r in page["result"]["regions"]]
  output.append({"asset_id":page["asset_id"],"page_order":page["page_order"],"source_hash":page["source_hash"],"selection_reasons":selected[page["asset_id"]],"predicted_sequence":page["diagnostics"]["predicted_sequence"],"predicted_groups":page["diagnostics"]["group_assignments"],"predicted_ambiguity":{str(r["region_id"]):r["ambiguity_reasons"] for r in page["result"]["regions"]},"geometry_source":page["diagnostics"]["geometry_source"],"regions":regions})
 artifact={"schema_version":"reader-correctness-review.v1","checkpoint":"11.11","status":"HUMAN_TESTING_REQUIRED","source_artifact":SOURCE.name,"dataset_pages":40,"selected_pages":len(output),"total_ocr_regions":sum(len(p["regions"]) for p in output),"selection_method":"deterministic stratified sample; SHA-256 seeded ordinary-page selection","pages":output,"model_calls":{"vlm":0,"ollama":0}}
 OUT.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+"\n");return artifact
if __name__=="__main__":print(json.dumps({k:v for k,v in build().items() if k!="pages"},ensure_ascii=False))
