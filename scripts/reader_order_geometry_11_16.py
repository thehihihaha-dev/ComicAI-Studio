#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"backend"),str(ROOT/"scripts")]
from app.services.reading_order_geometry_experiment import box,center_distance,contains,height,tier_order,vertical_overlap
from app.services.resource_safety import ResourceThresholds,sample_resources
DAY=ROOT/"benchmarks/day11";FROZEN=DAY/"reader-reading-order-comparison-11.11.json";LOGICAL=DAY/"reader-logical-region-sample-11.11.json";HUMAN=DAY/"reader-correctness-human-verified-11.11.json";OLD9=DAY/"reader-reading-order-comparison-11.9.json";CONTROL=DAY/"reader-order-control-11.16.json";AUDIT=DAY/"reader-order-inversion-audit-11.16.json";CANDIDATES=DAY/"reader-order-candidates-11.16.json";STABILITY=DAY/"reader-order-stability-11.16.json";SUMMARY=DAY/"reader-order-summary-11.16.json"
RULES={"A_VERTICAL_OVERLAP":{"vertical_overlap_min":.50},"B_NORMALIZED_CENTER":{"normalized_center_distance_max":.50},"C_HYBRID_TALL_PROTECTION":{"vertical_overlap_min":.30,"center_max":.75,"strong_center_max":.35,"tall_height_ratio":1.8}}
def pairs(sequence):return {(a,b) for i,a in enumerate(sequence) for b in sequence[i+1:]}
def score_pages(pages):
 exact=sum(p["prediction"]==p["human"] for p in pages);positions=sum(i<len(p["prediction"]) and p["prediction"][i]==rid for p in pages for i,rid in enumerate(p["human"]));total_positions=sum(len(p["human"]) for p in pages);correct_pairs=sum(len(pairs(p["prediction"])&pairs(p["human"])) for p in pages);total_pairs=sum(len(pairs(p["human"])) for p in pages);inversions=total_pairs-correct_pairs
 return {"exact_pages":{"correct":exact,"total":len(pages),"accuracy":exact/len(pages)},"exact_positions":{"correct":positions,"total":total_positions,"accuracy":positions/total_positions},"pairwise":{"correct":correct_pairs,"total":total_pairs,"accuracy":correct_pairs/total_pairs},"inversions":inversions}
def classify(a,b):
 overlap=vertical_overlap(a,b);center=center_distance(a,b);ratio=max(height(a),height(b))/max(1,min(height(a),height(b)))
 if contains(a,b) or contains(b,a):kind="nested/contained region"
 elif ratio>=1.8 and overlap>0:kind="tall-panel interference"
 elif overlap>=.5 and center<=.5:kind="same-row misclassification"
 elif overlap>0:kind="vertical-overlap ambiguity"
 elif center<=.5:kind="center-point ordering failure"
 elif abs(box(a)[1]-box(b)[1])<min(height(a),height(b))*.3:kind="bbox-edge ordering failure"
 else:kind="different-row incorrectly merged"
 return {"classification":kind,"vertical_overlap":overlap,"normalized_center_distance":center,"height_ratio":ratio}
def main():
 frozen_bytes=FROZEN.read_bytes();logical_bytes=LOGICAL.read_bytes();human_bytes=HUMAN.read_bytes();frozen=json.loads(frozen_bytes);logical=json.loads(logical_bytes);human=json.loads(human_bytes);expected={"exact_page_order":.6,"exact_region_position":.74,"pairwise":.9354838709677419,"inversions":8};fm=frozen["metrics"]
 if (fm["exact_page_order"]["accuracy"],fm["exact_region_position"]["accuracy"],fm["pairwise"]["accuracy"],fm["total_inversions"])!=(expected["exact_page_order"],expected["exact_region_position"],expected["pairwise"],expected["inversions"]):raise RuntimeError("broken 11.11 baseline comparability")
 protocol={"schema_version":"reader-order-candidates.v1","checkpoint":"11.16","status":"DECLARED_BEFORE_EVALUATION","source_type":"MANGA","candidate_rules":RULES,"parameter_status":"BENCHMARK-FITTED, not production-calibrated","gt_runtime_features":[],"group_gt_availability":"N/A: flattened click-order GT has no authoritative panel/tier labels"};protocol_hash=hashlib.sha256(json.dumps(protocol,sort_keys=True,separators=(",",":")).encode()).hexdigest();CANDIDATES.write_text(json.dumps({**protocol,"protocol_hash":protocol_hash},ensure_ascii=False,indent=2)+"\n")
 logical_by={p["page_order"]:p for p in logical["pages"]};human_by={p["page_order"]:p for p in human["pages"]};control_pages=[]
 for page in frozen["pages"]:control_pages.append({"page_order":page["page_order"],"prediction":page["predicted_scored_after_human_exclusion"],"human":page["human_order"],"excluded":page["human_excluded"],"inversions":page["inversions"]})
 reproduced=score_pages(control_pages)
 if reproduced!={"exact_pages":{"correct":6,"total":10,"accuracy":.6},"exact_positions":{"correct":37,"total":50,"accuracy":.74},"pairwise":{"correct":116,"total":124,"accuracy":.9354838709677419},"inversions":8}:raise RuntimeError("control reproduction differs")
 before=sample_resources(ResourceThresholds.from_environment());started=time.perf_counter_ns();outputs={rule:[] for rule in RULES};ambiguous=Counter();tier_counts={rule:[] for rule in RULES}
 for rule in RULES:
  for page_order in sorted(logical_by):
   page=logical_by[page_order];hp=human_by[page_order];excluded=set(hp["excluded_region_ids"]);items=[{"id":r["logical_region_id"],"bbox":r["bbox"]} for r in page["logical_regions"] if r["logical_region_id"] not in excluded];result=tier_order(items,rule,"MANGA");outputs[rule].append({"page_order":page_order,"prediction":result["order"],"human":hp["ordered_region_ids"],"tiers":result["tiers"],"ambiguous":result["ambiguous"]});ambiguous[rule]+=len(result["ambiguous"]);tier_counts[rule].append(len(result["tiers"]))
 elapsed=time.perf_counter_ns()-started;after=sample_resources(ResourceThresholds.from_environment())
 control_map={p["page_order"]:p for p in control_pages};metrics={};page_deltas={}
 for rule,pages in outputs.items():
  metrics[rule]=score_pages(pages);deltas=[]
  for page in pages:
   control_inv=control_map[page["page_order"]]["inversions"];candidate_inv=len(pairs(page["human"])-pairs(page["prediction"]));deltas.append({"page_order":page["page_order"],"control_inversions":control_inv,"candidate_inversions":candidate_inv,"classification":"IMPROVED" if candidate_inv<control_inv else "REGRESSED" if candidate_inv>control_inv else "UNCHANGED","control_exact":control_map[page["page_order"]]["prediction"]==page["human"],"candidate_exact":page["prediction"]==page["human"]})
  page_deltas[rule]=deltas;metrics[rule].update({"pages_improved":sum(x["classification"]=="IMPROVED" for x in deltas),"pages_unchanged":sum(x["classification"]=="UNCHANGED" for x in deltas),"pages_regressed":sum(x["classification"]=="REGRESSED" for x in deltas),"ambiguous_regions":ambiguous[rule]})
 def preference(rules,pages=None):
  eligible={r:score_pages([p for p in outputs[r] if pages is None or p["page_order"] in pages]) for r in rules};return min(rules,key=lambda r:(eligible[r]["inversions"],-eligible[r]["exact_pages"]["correct"],-eligible[r]["pairwise"]["accuracy"],r))
 best=preference(list(RULES));all_pages={p["page_order"] for p in control_pages};lop=[]
 for held in sorted(all_pages):lop.append({"held_out_page":held,"selected_rule":preference(list(RULES),all_pages-{held})})
 stability_counts=Counter(x["selected_rule"] for x in lop)
 regions={p["page_order"]:{r["logical_region_id"]:{"id":r["logical_region_id"],"bbox":r["bbox"]} for r in p["logical_regions"]} for p in logical["pages"]};inversions=[];taxonomy=Counter()
 for page in control_pages:
  human_pairs=pairs(page["human"]);pred_pairs=pairs(page["prediction"])
  for left,right in sorted(human_pairs-pred_pairs):
   detail=classify(regions[page["page_order"]][left],regions[page["page_order"]][right]);taxonomy[detail["classification"]]+=1;inversions.append({"page_order":page["page_order"],"human_before":left,"human_after":right,**detail})
 page3={"control":next(p for p in control_pages if p["page_order"]==3),"candidates":{r:next(p for p in outputs[r] if p["page_order"]==3) for r in RULES},"11.9_source_preserved":OLD9.is_file(),"11.9_sha256":hashlib.sha256(OLD9.read_bytes()).hexdigest() if OLD9.is_file() else None}
 best_metrics=metrics[best];control_art={"schema_version":"reader-order-control.v1","checkpoint":"11.16","baseline_definition":{"bbox":"logical region bbox [x1,y1,x2,y2]","current_tier_rule":"center distance <= max(4px, min(item height, max tier height)*0.5)","center":"(y1+y2)/2; tier center is mean member center","overlap":"not used by current tiered_order","tie_break":"input top then stable id; within manga tier x descending then id","group_order":"tiers insertion/top order; within tier right-to-left"},"frozen_metrics":fm,"reproduced_metrics":reproduced,"pages":control_pages,"comparability":"PASS","frozen_sha256":hashlib.sha256(frozen_bytes).hexdigest()}
 audit_art={"schema_version":"reader-order-inversion-audit.v1","checkpoint":"11.16","inversion_count":len(inversions),"taxonomy":dict(taxonomy),"cases":inversions,"group_or_panel_error":"N/A: no authoritative Human panel/tier labels"}
 candidates_art={**protocol,"status":"COMPLETED","protocol_hash":protocol_hash,"results":metrics,"selected_best":best,"selection_rule":"minimum inversions, then maximum exact pages, pairwise accuracy, stable rule name","outputs":outputs,"page_deltas":page_deltas,"group_metrics":{"exact_group_structure":"N/A","same_tier_accuracy":"N/A","incorrect_tier_merges":"N/A","incorrect_tier_splits":"N/A","reason":"11.11 click-order GT intentionally has no Human panel/tier oracle"},"tier_counts":tier_counts}
 stability_art={"schema_version":"reader-order-stability.v1","checkpoint":"11.16","parameter_status":"BENCHMARK-FITTED","leave_one_page_out":lop,"selected_rule_counts":dict(stability_counts),"stable_selection":len(stability_counts)==1,"small_data_warning":"10 page-grouped Human GT pages"}
 control_inv=reproduced["inversions"];improved=best_metrics["inversions"]<control_inv and best_metrics["pages_regressed"]==0
 if improved and best_metrics["exact_pages"]["correct"]>reproduced["exact_pages"]["correct"]:decision="A. GEOMETRY FIX PASS"
 elif best_metrics["inversions"]<control_inv:decision="B. PARTIAL GEOMETRY IMPROVEMENT"
 elif all(metrics[r]["inversions"]>=control_inv for r in RULES):decision="C. CURRENT RULE IS BETTER"
 else:decision="D. PANEL REPRESENTATION MUST CHANGE"
 swap_delta=after["swap_used_bytes"]-before["swap_used_bytes"] if isinstance(after["swap_used_bytes"],int) and isinstance(before["swap_used_bytes"],int) else None
 summary_art={"schema_version":"reader-order-summary.v1","checkpoint":"11.16","decision":decision,"control":reproduced,"best_candidate":best,"best_metrics":best_metrics,"page_deltas":page_deltas[best],"inversion_taxonomy":dict(taxonomy),"group_metrics":"N/A: no Human panel/tier GT","tall_panel":{"rule":"height > 1.8x page median requires normalized center <= .35","best_candidate_uses_protection":best=="C_HYBRID_TALL_PROTECTION","result":"reported through candidate page metrics; no Human tall-panel label inferred"},"page_3":page3,"stability":stability_art,"runtime":{"total_nanoseconds":elapsed,"nanoseconds_per_page":elapsed/(10*len(RULES)),"nanoseconds_per_region":elapsed/(50*len(RULES))},"resources":{"before":before,"after":after,"swap_delta_bytes":swap_delta,"resource_guard":"CRITICAL" if "CRITICAL" in {before["safety_state"],after["safety_state"]} else after["safety_state"]},"safety":{"ocr_inference_calls":0,"vlm_calls":0,"ollama_calls":0,"human_gt_unchanged":hashlib.sha256(HUMAN.read_bytes()).hexdigest()==hashlib.sha256(human_bytes).hexdigest(),"frozen_control_unchanged":hashlib.sha256(FROZEN.read_bytes()).hexdigest()==hashlib.sha256(frozen_bytes).hexdigest(),"reading_order_production_changed":False,"authoritative_state_changed":False},"recommended_integration_experiment":"Use the winning benchmark-fitted geometry rule in an offline Reader V2 integration replay with explicit predicted panel/group geometry; do not deploy until new page-grouped Human validation."}
 for path,obj in ((CONTROL,control_art),(AUDIT,audit_art),(CANDIDATES,candidates_art),(STABILITY,stability_art),(SUMMARY,summary_art)):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"decision":decision,"control":reproduced,"best":best,"best_metrics":best_metrics,"taxonomy":dict(taxonomy),"page3":{r:next(p for p in outputs[r] if p["page_order"]==3)["prediction"]==next(p for p in outputs[r] if p["page_order"]==3)["human"] for r in RULES},"stability":dict(stability_counts),"runtime":summary_art["runtime"],"resources":summary_art["resources"]},ensure_ascii=False))
if __name__=="__main__":main()
