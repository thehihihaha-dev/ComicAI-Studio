#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from app.services.logical_region_aggregation import REVISION,aggregate_fragments
SOURCE=ROOT/"benchmarks/day11/reader-v2-correctness-review-sample-11.11.json";AUDIT=ROOT/"benchmarks/day11/reader-region-granularity-audit-11.11.json";OUT=ROOT/"benchmarks/day11/reader-logical-region-sample-11.11.json"
def build():
 src=json.loads(SOURCE.read_text());pages=[];classification={"logical_text_region_or_bubble":0,"ocr_line_or_fragment":0,"narration_box":0,"sfx":0,"other_detected_text":0};merged_fragments=0
 for p in src["pages"]:
  for r in p["regions"]:
   if r["region_type"]=="speech_bubble":classification["logical_text_region_or_bubble"]+=1
   elif r["region_type"]=="detected_text":classification["ocr_line_or_fragment"]+=1
   elif r["region_type"]=="narration_box":classification["narration_box"]+=1
   elif r["region_type"]=="sfx":classification["sfx"]+=1
   else:classification["other_detected_text"]+=1
  agg=aggregate_fragments(p["regions"]);frag_to_log={fid:lr["logical_region_id"] for lr in agg["logical_regions"] for fid in lr["source_fragment_ids"]};logical_sequence=[]
  for fid in p["predicted_sequence"]:
   lid=frag_to_log[fid]
   if lid not in logical_sequence:logical_sequence.append(lid)
  merged_fragments+=sum(max(0,len(lr["source_fragment_ids"])-1) for lr in agg["logical_regions"])
  pages.append({"asset_id":p["asset_id"],"page_order":p["page_order"],"source_hash":p["source_hash"],"selection_reasons":p["selection_reasons"],"geometry_source":p["geometry_source"],"representation_version":REVISION,"representation_hash":agg["representation_hash"],"raw_fragment_count":len(p["regions"]),"logical_region_count":len(agg["logical_regions"]),"logical_regions":agg["logical_regions"],"predicted_panel_order":["PAGE_FALLBACK"],"predicted_region_orders":{"PAGE_FALLBACK":logical_sequence},"predicted_sequence":logical_sequence})
 representative=max(pages,key=lambda p:(p["raw_fragment_count"]-p["logical_region_count"],p["raw_fragment_count"],-p["page_order"]))
 audit={"schema_version":"reader-region-granularity-audit.v1","checkpoint":"11.11","source_pages":len(pages),"displayed_regions":sum(p["raw_fragment_count"] for p in pages),"classification":classification,"logical_regions_after_aggregation":sum(p["logical_region_count"] for p in pages),"fragments_merged_into_multi_fragment_logical_regions":merged_fragments,"legacy_fragment_level_gt_compatibility":"INCOMPATIBLE_WITH_LOGICAL_V1","legacy_gt_conversion":"NONE — preserved without conversion or overwrite","per_page":[{k:p[k] for k in ("page_order","geometry_source","raw_fragment_count","logical_region_count","representation_hash")} for p in pages],"production_data_modified":False,"vlm_calls":0,"ollama_calls":0}
 manifest={"schema_version":"reader-logical-region-sample.v1","checkpoint":"11.11","status":"HUMAN_REPRESENTATION_CONFIRMATION_REQUIRED","representation_version":REVISION,"source_manifest":SOURCE.name,"pages":pages,"representative_asset_id":representative["asset_id"],"representative_page_order":representative["page_order"],"visible_queue_pages":1,"ocr_samples_preserved":src["total_ocr_regions"],"vlm_calls":0,"ollama_calls":0}
 AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n");OUT.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n");return audit,manifest
if __name__=="__main__":
 a,m=build();print(json.dumps({"audit":a,"representative_page_order":m["representative_page_order"]},ensure_ascii=False))
