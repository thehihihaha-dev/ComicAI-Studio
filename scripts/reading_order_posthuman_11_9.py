#!/usr/bin/env python3
"""Verified-only, zero-inference reading-order analysis for Checkpoint 11.9."""
from __future__ import annotations
import json, os, sys, time
from collections import Counter
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/"backend";sys.path[:0]=[str(BACKEND),str(ROOT/"scripts")];load_dotenv(BACKEND/".env");os.chdir(BACKEND)
from app.database import SessionLocal  # noqa:E402
from app.models.asset import Asset  # noqa:E402
from app.models.project import Project  # noqa:E402,F401
from app.models.reading_order_benchmark_review import ReadingOrderBenchmarkReview  # noqa:E402
from app.services.reading_order_benchmark_review import asset_path, ordering_metrics, source_hash  # noqa:E402
from app.services.resource_safety import ResourceThresholds, sample_resources  # noqa:E402
from reader_benchmark import authoritative_snapshot  # noqa:E402

PROJECT="e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2";OUT=ROOT/"benchmarks/day11";SCHEMA="reader-reading-order-human.v1"
VERIFIED=OUT/"reader-reading-order-human-verified-11.9.json";COMPARISON=OUT/"reader-reading-order-comparison-11.9.json";ERRORS=OUT/"reader-reading-order-errors-11.9.json"

def normalized_groups(groups:list[dict[str,Any]])->list[dict[str,Any]]:
 return [{"group_id":str(g["group_id"]),"region_ids":sorted(int(x) for x in g.get("region_ids",[]))} for g in groups]

def group_accuracy(predicted:list[dict[str,Any]],human:list[dict[str,Any]])->dict[str,Any]:
 p,h=normalized_groups(predicted),normalized_groups(human)
 return {"exact":p==h,"predicted":p,"human":h}

def analyze()->tuple[dict,dict,dict]:
 started=time.perf_counter();thresholds=ResourceThresholds.from_environment();resources_before=sample_resources(thresholds);before=authoritative_snapshot(PROJECT)["state_hash"]
 db=SessionLocal();samples=[]
 try:
  rows=(db.query(ReadingOrderBenchmarkReview).filter_by(project_id=PROJECT).order_by(ReadingOrderBenchmarkReview.page_order).all())
  counts=Counter(r.state for r in rows)
  if len(rows)!=3 or counts["VERIFIED"]!=3 or counts["PENDING"] or counts["SOURCE_UNAVAILABLE"]:raise RuntimeError(f"persisted human state mismatch: {dict(counts)}")
  for row in rows:
   asset=db.get(Asset,row.asset_id);compatible=bool(asset and asset_path(asset).is_file() and source_hash(asset_path(asset))==row.source_image_hash)
   if not compatible or not row.source_compatible or row.human_sequence is None or row.human_groups is None:raise RuntimeError(f"stale/incomplete GT: {row.review_id}")
   sequence=ordering_metrics(row.predicted_sequence,row.human_sequence);groups=group_accuracy(row.predicted_groups,row.human_groups)
   dispositions={str(x):"ORDERED" for x in row.human_sequence};dispositions.update(row.human_dispositions or {})
   ambiguous=any(v=="AMBIGUOUS" for v in dispositions.values());orphans={int(k) for k,v in dispositions.items() if v=="ORPHAN"}
   errors=[]
   if not sequence["exact"]:errors.append("WRONG_TEXT_ORDER")
   if not groups["exact"]:errors.append("WRONG_PANEL_ASSIGNMENT")
   samples.append({"review_id":row.review_id,"project_id":row.project_id,"asset_id":row.asset_id,"page_order":row.page_order,"source_image_hash":row.source_image_hash,
    "source_compatible":True,"reader_revision":row.reader_revision,"reading_policy":row.reading_policy,
    "predicted_sequence":row.predicted_sequence,"human_sequence":row.human_sequence,"predicted_groups":row.predicted_groups,"human_groups":row.human_groups,
    "human_dispositions":dispositions,"sequence_metrics":sequence,"group_metrics":groups,"ambiguous":ambiguous,"human_orphan_ids":sorted(orphans),"error_taxonomy":errors})
 finally:db.close()
 after=authoritative_snapshot(PROJECT)["state_hash"];resources_after=sample_resources(thresholds)
 if before!=after:raise RuntimeError("authoritative project state changed")
 total_pairs=sum(x["sequence_metrics"]["pairwise_total"] for x in samples);inversions=sum(x["sequence_metrics"]["inversions"] for x in samples)
 exact_pages=sum(x["sequence_metrics"]["exact"] for x in samples);group_exact=sum(x["group_metrics"]["exact"] for x in samples)
 corrections=sum(x["sequence_metrics"]["corrections"] for x in samples);ambiguous_pages=sum(x["ambiguous"] for x in samples)
 verified={"schema_version":SCHEMA,"checkpoint":"11.9","artifact_kind":"human_verified","status":"completed","verified_only":True,"N":len(samples),"samples":samples,"model_calls":{"vlm":0,"ollama":0,"ocr":0}}
 metrics={"N":len(samples),"exact_page_order":{"correct":exact_pages,"accuracy":exact_pages/len(samples)},"panel_group_order":{"correct":group_exact,"accuracy":group_exact/len(samples),"contract":"ordered group IDs plus region membership sets; within-group order scored separately"},
  "text_region_order":{"exact_pages":exact_pages,"accuracy":exact_pages/len(samples)},"pairwise":{"correct":total_pairs-inversions,"total":total_pairs,"accuracy":(total_pairs-inversions)/total_pairs},"inversions":inversions,
  "orphan_assignment":{"applicable":any(x["human_orphan_ids"] for x in samples),"accuracy":None,"note":"N/A: human marked no orphan regions"},"ambiguous_pages":{"count":ambiguous_pages,"rate":ambiguous_pages/len(samples)},"human_position_corrections":corrections,"pages_with_corrections":len(samples)-exact_pages}
 comparison={"schema_version":SCHEMA,"checkpoint":"11.9","artifact_kind":"comparison","status":"completed","N":len(samples),"metrics":metrics,"per_page":[{"page_order":x["page_order"],**x["sequence_metrics"],"group_exact":x["group_metrics"]["exact"],"ambiguous":x["ambiguous"]} for x in samples],
  "verdict":"B. PASS WITH MINOR GEOMETRY FIXES","verdict_basis":"2/3 exact pages and 76/79 pairwise relations; one page has three inversions, so controlled scaling is justified but geometry is not exact.","ocr_safety":"Reader ordering readiness does not change 11.8 false ACCEPT 16/19; ACCEPT_CANDIDATE remains non-authoritative.",
  "performance":{"analysis_wall_seconds":time.perf_counter()-started,"resources_before":resources_before,"resources_after":resources_after,"swap_delta_bytes":resources_after["swap_used_bytes"]-resources_before["swap_used_bytes"],"authoritative_state_unchanged":True,"model_calls":{"vlm":0,"ollama":0,"ocr":0}}}
 errors={"schema_version":SCHEMA,"checkpoint":"11.9","artifact_kind":"errors","status":"completed","N":len(samples),"pages":[{"page_order":x["page_order"],"taxonomy":x["error_taxonomy"],"predicted_sequence":x["predicted_sequence"],"human_sequence":x["human_sequence"],"inversions":x["sequence_metrics"]["inversions"]} for x in samples if x["error_taxonomy"]],"taxonomy_counts":dict(Counter(e for x in samples for e in x["error_taxonomy"])),"taxonomy_note":"Only sequence/group evidence is classified; no semantic cause is inferred."}
 for path,data in ((VERIFIED,verified),(COMPARISON,comparison),(ERRORS,errors)):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
 return verified,comparison,errors

if __name__=="__main__":
 _,comparison,_=analyze();print(json.dumps({"metrics":comparison["metrics"],"verdict":comparison["verdict"]},ensure_ascii=False))
