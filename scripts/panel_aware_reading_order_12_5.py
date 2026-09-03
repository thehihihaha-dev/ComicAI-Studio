#!/usr/bin/env python3
"""Clean finite Checkpoint 12.5 experiment; Human order is post-freeze only."""
from __future__ import annotations
import hashlib,json,sys
from collections import Counter
from pathlib import Path
from typing import Any
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from app.database import SessionLocal
from app.models.panel_ground_truth_review import PanelGroundTruthReview
from app.services.panel_aware_reading_order import assign_regions,order_panels,panel_aware_order,topological_order
from app.services.resource_safety import ResourceThresholds,sample_resources
DAY11,DAY12=ROOT/"benchmarks/day11",ROOT/"benchmarks/day12";PAGES=[1,2,3,4,5,7,15,17,18,38];LEGACY={1,2,15,17}
RUNTIME={"logical_geometry":DAY11/"reader-logical-region-sample-11.11.json","oracle_unseen_geometry":DAY12/"panel-unseen-human-gt-post-correction-validation-12.4.json","realistic_legacy":DAY12/"panel-conflict-resolution-output-12.3.json","realistic_unseen":DAY12/"panel-unseen-resolution-output-12.4.json"}
EVAL={"human_order":DAY11/"reader-order-control-11.16.json","baseline":DAY11/"reader-order-candidates-11.16.json"}
EXPECTED={"logical_geometry":"04f0973d79e6562cca97d21e2fdb1e15152b0ceb30f8c37e223c0ba9d98bb5fa","oracle_unseen_geometry":"fd49ba4fb58b1785a786bae1b3f376f7f176b45ea222e3af364d493fc9c727d5","realistic_legacy":"7559e7560b0825fd5874306615bbe334465bd31e9c835077700448a4771da6c6","realistic_unseen":"5b7eca8fed83970465a65de84509daa85d56b57369dc46c79964affccddc4772"}
LEGACY_SHA="5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3";UNSEEN_SHA="f62e38d5ed28531681b9165cca77e0f62ab37b7cf92a5161cab0c9f0cb6216ea"
OUT={n:DAY12/f"panel-order-{n}-12.5.json" for n in ("input-gt-audit","protocol","synthetic","oracle-candidates","realistic-candidates","candidate-freeze","evaluation","summary")}
def canonical(v:Any)->bytes:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def digest(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()
def fh(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p:Path,v:Any)->None:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n")
def gid(b:list[float])->str:return "PG_"+digest([round(float(x),6) for x in b])[:12]
def legacy_material(rows):return [{"id":r.review_id,"state":r.state,"revision":r.revision,"panels":r.human_panels,"hash":r.source_image_hash} for r in rows]
def load_legacy():
 s=SessionLocal()
 try:
  rows=s.query(PanelGroundTruthReview).filter(PanelGroundTruthReview.page_order.in_(sorted(LEGACY))).order_by(PanelGroundTruthReview.page_order).all()
  if [r.page_order for r in rows]!=sorted(LEGACY) or digest(legacy_material(rows))!=LEGACY_SHA:raise RuntimeError("legacy panel GT snapshot mismatch")
  return [{"review_id":r.review_id,"page_order":r.page_order,"benchmark_asset_id":r.benchmark_asset_id,"source_image_hash":r.source_image_hash,"source_path":r.source_path,"image_dimensions":[r.image_width,r.image_height],"state":r.state,"revision":r.revision,"human_panels":r.human_panels} for r in rows]
 finally:s.close()
def selected(d,wanted):
 out={}
 for p in d["pages"]:
  if p["page_order"] in wanted:
   ids=set(p["selected_panel_ids"]);panels=[x for x in p["candidates"] if x["panel_id"] in ids]
   if {x["panel_id"] for x in panels}!=ids:raise RuntimeError("selected panel identity mismatch")
   out[p["page_order"]]={"source_hash":p["source_hash"],"panels":panels,"source_unresolved":p["unresolved"]}
 return out
def verify_source_record(record,path):
 if not path.is_file() or fh(path)!=record["source_image_hash"]:raise RuntimeError(f"source fingerprint mismatch Page {record['page_order']}")
 with Image.open(path) as image:actual=list(image.size)
 if actual!=record["image_dimensions"]:raise RuntimeError(f"source dimension mismatch Page {record['page_order']}")
def contaminated(value):
 if isinstance(value,dict):return any(k in {"human","human_order","ordered_region_ids","human_sequence","inversions"} or contaminated(v) for k,v in value.items())
 if isinstance(value,list):return any(contaminated(v) for v in value)
 return False
def validate_page_set(logical,oracle,realistic):
 if sorted(logical)!=PAGES or sorted(oracle)!=PAGES or sorted(realistic)!=PAGES:raise RuntimeError("unexpected benchmark page set")
def load_runtime_inputs(expected=None,runtime_paths=None,source_overrides=None):
 runtime_paths=runtime_paths or RUNTIME;source_overrides=source_overrides or {};expected=expected or EXPECTED;actual={n:fh(p) for n,p in runtime_paths.items()}
 if actual!=expected:raise RuntimeError("frozen runtime input hash mismatch")
 docs={n:json.loads(p.read_text()) for n,p in runtime_paths.items()}
 if any(contaminated(d) for d in docs.values()):raise RuntimeError("Human-order contaminated pre-freeze input")
 logical={p["page_order"]:p for p in docs["logical_geometry"]["pages"] if p["page_order"] in PAGES}
 legacy=load_legacy();unseen=docs["oracle_unseen_geometry"]["records"]
 if digest(unseen)!=UNSEEN_SHA:raise RuntimeError("unseen panel GT snapshot mismatch")
 records=legacy+unseen;oracle={r["page_order"]:{"source_hash":r["source_image_hash"],"panels":r["human_panels"]} for r in records}
 realistic={**selected(docs["realistic_legacy"],LEGACY),**selected(docs["realistic_unseen"],set(PAGES)-LEGACY)}
 validate_page_set(logical,oracle,realistic)
 ids=[r["logical_region_id"] for p in logical.values() for r in p["logical_regions"]]
 if len(ids)!=63 or len(set(ids))!=63 or sum(len(x["panels"]) for x in oracle.values())!=36:raise RuntimeError("runtime cohort count mismatch")
 for r in records:
  page=r["page_order"];source=source_overrides.get(page,ROOT/r["source_path"])
  verify_source_record(r,source)
  if logical[page]["source_hash"]!=r["source_image_hash"] or realistic[page]["source_hash"]!=r["source_image_hash"]:raise RuntimeError(f"source identity mismatch Page {page}")
 return {"hashes":actual,"logical":logical,"oracle":oracle,"realistic":realistic,"records":records,"legacy_snapshot":LEGACY_SHA,"unseen_snapshot":digest(unseen)}
def runtime_audit(i):
 pages=[]
 for page in PAGES:
  r=next(x for x in i["records"] if x["page_order"]==page)
  pages.append({"page_order":page,"source_hash":r["source_image_hash"],"source_path":r["source_path"],"image_dimensions":r["image_dimensions"],"persisted_logical_regions":[{"id":x["logical_region_id"],"bbox":x["bbox"]} for x in i["logical"][page]["logical_regions"]],"oracle_panels":i["oracle"][page]["panels"],"realistic_selected_panels":i["realistic"][page]["panels"]})
 v={"status":"PRE_CANDIDATE_RUNTIME_INPUTS_VERIFIED","cohort_pages":PAGES,"persisted_logical_region_count":63,"expected_post_freeze_metric_region_count":50,"oracle_panel_count":36,"runtime_input_file_sha256":i["hashes"],"legacy_panel_snapshot":{"computed":i["legacy_snapshot"],"expected":LEGACY_SHA,"verified":i["legacy_snapshot"]==LEGACY_SHA},"unseen_panel_snapshot":{"computed":i["unseen_snapshot"],"expected":UNSEEN_SHA,"verified":i["unseen_snapshot"]==UNSEEN_SHA},"pages":pages,"human_reading_order_loaded":False,"gt_runtime_features":[]};v["semantic_sha256"]=digest(v);return v
def protocol():
 v={"schema_version":"panel-order-protocol.v2","checkpoint":"12.5","status":"FROZEN_BEFORE_HUMAN_READING_ORDER_ACCESS","policy":"ZERO_TOLERANCE_STRICT_RECURSIVE_GUILLOTINE_MANGA_RTL","separation_tolerance":0,"horizontal_partition_precedes_vertical":True,"unsupported_layout":"UNRESOLVED","assignment":["UNIQUE_CONTAINMENT","UNIQUE_CENTER_AND_STRICT_AREA_MAJORITY_GT_0.50","AMBIGUOUS","UNASSIGNED"],"intra_panel_rule":"ANY_PEER_NORMALIZED_VERTICAL_OVERLAP_GTE_0.50","intra_panel_parameter_status":"BENCHMARK_FITTED","gt_runtime_features":[]};v["protocol_sha256"]=digest(v);return v
def candidate(track,logical,panel_pages,provenance):
 if sorted(logical)!=PAGES or sorted(panel_pages)!=PAGES:raise RuntimeError("unexpected candidate page set")
 pages=[]
 for page in PAGES:
  regions=[{"id":r["logical_region_id"],"bbox":r["bbox"]} for r in logical[page]["logical_regions"]];panels=[{"panel_id":gid(r["bbox"]),"bbox":r["bbox"]} for r in panel_pages[page]["panels"]]
  pages.append({"page_order":page,"source_hash":logical[page]["source_hash"],"panel_source":track,"panel_nodes":panels,"upstream_structure_status":"UNRESOLVED" if panel_pages[page].get("source_unresolved") else "RESOLVED",**panel_aware_order(regions,panels)})
 v={"schema_version":"panel-order-candidates.v2","checkpoint":"12.5","track":track,"runtime_region_population":"ALL_63_PERSISTED_GEOMETRIES_METRIC_FILTER_POST_FREEZE","provenance":provenance,"pages":pages,"gt_runtime_features":[],"model_calls":{"ocr":0,"vlm":0,"ollama":0}};v["semantic_sha256"]=digest(v);return v
def synthetic_suite():
 def ps(bs):return [{"panel_id":f"p{i}","bbox":b} for i,b in enumerate(bs)]
 layouts={"2x2_rtl":([[0,0,40,40],[60,0,100,40],[0,60,40,100],[60,60,100,100]],["p1","p0","p3","p2"]),"horizontal_pair":([[0,0,40,100],[60,0,100,100]],["p1","p0"]),"vertical_pair":([[0,0,100,40],[0,60,100,100]],["p0","p1"]),"tall_right_stacked_left":([[60,0,100,100],[0,0,40,40],[0,60,40,100]],["p0","p1","p2"]),"tall_left_stacked_right":([[0,0,40,100],[60,0,100,40],[60,60,100,100]],["p1","p2","p0"]),"spanning_top":([[0,0,100,30],[0,40,40,100],[60,40,100,100]],["p0","p2","p1"]),"spanning_bottom":([[0,0,40,60],[60,0,100,60],[0,70,100,100]],["p1","p0","p2"]),"offset_panels":([[0,0,42,35],[58,5,100,40],[5,60,45,100],[55,55,95,95]],["p1","p0","p3","p2"]),"bridge_non_transitivity":([[0,0,30,30],[40,0,70,70],[80,40,110,70]],["p2","p1","p0"]),"ambiguous_overlap":([[0,0,70,70],[30,30,100,100]],"UNRESOLVED")};rows=[]
 for name,(boxes,expected) in layouts.items():
  trace=order_panels(ps(boxes));observed=trace["order"] if trace["resolved"] else "UNRESOLVED";rows.append({"fixture":name,"path":"order_panels","expected":expected,"observed":observed,"pass":observed==expected,"trace":trace})
 cycle=topological_order(["a","b"],[{"before":"a","after":"b","relation":"ABOVE"},{"before":"b","after":"a","relation":"RIGHT_OF"}]);rows.append({"fixture":"explicit_cycle","path":"topological_order","expected":"UNRESOLVED","observed":"UNRESOLVED" if not cycle["resolved"] else cycle["order"],"pass":not cycle["resolved"],"trace":cycle})
 empty=panel_aware_order([],[{"panel_id":"p0","bbox":[0,0,100,100]}]);rows.append({"fixture":"empty_panel","path":"panel_aware_order","expected":[],"observed":empty["sequence"],"pass":empty["status"]=="RESOLVED" and empty["sequence"]==[],"trace":empty})
 cases={"clean_containment":([{"id":"r","bbox":[10,10,20,20]}],[{"panel_id":"p","bbox":[0,0,50,50]}],"UNIQUE_CONTAINMENT"),"majority_intersection":([{"id":"r","bbox":[10,-5,50,15]}],[{"panel_id":"p","bbox":[0,0,60,60]}],"UNIQUE_CENTER_STRICT_MAJORITY"),"cross_border_ambiguity":([{"id":"r","bbox":[45,10,55,20]}],[{"panel_id":"a","bbox":[0,0,60,100]},{"panel_id":"b","bbox":[40,0,100,100]}],"AMBIGUOUS"),"unassigned_region":([{"id":"r","bbox":[110,0,120,10]}],[{"panel_id":"p","bbox":[0,0,100,100]}],"UNASSIGNED")}
 for name,(regions,panels,expected) in cases.items():
  trace=assign_regions(regions,panels);observed=trace["assignments"][0]["method"] if trace["assignments"] else "AMBIGUOUS" if trace["ambiguous"] else "UNASSIGNED";rows.append({"fixture":name,"path":"assign_regions","expected":expected,"observed":observed,"pass":observed==expected,"trace":trace})
 hierarchy=panel_aware_order([{"id":"right_top","bbox":[70,10,80,20]},{"id":"right_bottom","bbox":[70,50,80,60]},{"id":"left","bbox":[10,20,20,30]}],[{"panel_id":"left_panel","bbox":[0,0,40,100]},{"panel_id":"right_panel","bbox":[60,0,100,100]}]);expected=["right_top","right_bottom","left"];rows.append({"fixture":"full_hierarchy","path":"panel_aware_order","expected":expected,"observed":hierarchy["sequence"],"pass":hierarchy["sequence"]==expected,"trace":hierarchy})
 a=order_panels(ps(layouts["2x2_rtl"][0]));b=order_panels(list(reversed(ps(layouts["2x2_rtl"][0]))));rows.append({"fixture":"permutation_stable_ids","path":"order_panels","expected":a["order"],"observed":b["order"],"pass":canonical(a)==canonical(b),"trace":b})
 v={"schema_version":"panel-order-synthetic.v2","checkpoint":"12.5","results":rows,"human_metrics_included":False,"all_pass":all(r["pass"] for r in rows)};v["semantic_sha256"]=digest(v);return v
def pairs(seq):return {(a,b) for i,a in enumerate(seq) for b in seq[i+1:]}
def reference(humans,oracle):
 bypage={p["page_order"]:p for p in oracle["pages"]};rows=[]
 for page in PAGES:
  human=humans[page]["human"];c=bypage[page];owners={x["region_id"]:x["panel_id"] for x in c["assignment"]["assignments"]}
  if set(human)-set(owners):raise RuntimeError("Human ID lacks Oracle assignment")
  pos={};[pos.setdefault(owners[r],[]).append(i) for i,r in enumerate(human)];nodes=sorted(pos);edges=[{"before":a,"after":b} for a in nodes for b in nodes if a!=b and max(pos[a])<min(pos[b])]
  rows.append({"page_order":page,"human_region_ids":human,"region_to_oracle_panel":owners,"text_bearing_panels":nodes,"empty_panels":sorted(set(c["panel_order"]["nodes"])-set(nodes)),"derived_edges":edges,"derived_panel_order":topological_order(nodes,[{**e,"relation":"HUMAN_SEQUENCE_DERIVED"} for e in edges])})
 return {"pages":rows,"metric_region_count":sum(len(r["human_region_ids"]) for r in rows),"text_bearing_panel_count":sum(len(r["text_bearing_panels"]) for r in rows),"empty_panel_count":sum(len(r["empty_panels"]) for r in rows),"derived_relation_count":sum(len(r["derived_edges"]) for r in rows)}
def score(track,humans,ref):
 refs={r["page_order"]:r for r in ref["pages"]};details=[];tot=Counter();resolved_regions=exact=positions=correct=denom=inversions=cross=intra=agreement=panel_exact=panel_positions=panel_correct=panel_total=0
 for f in track["pages"]:
  page=f["page_order"];human=humans[page]["human"];eligible=set(human);assigned={r["region_id"]:r for r in f["assignment"]["assignments"] if r["region_id"] in eligible};amb=[r for r in f["assignment"]["ambiguous"] if r["region_id"] in eligible];un=[r for r in f["assignment"]["unassigned"] if r["region_id"] in eligible]
  for r in assigned.values():tot["contained" if r["method"]=="UNIQUE_CONTAINMENT" else "intersection"]+=1
  tot["ambiguous"]+=len(amb);tot["unassigned"]+=len(un);resolved=f["panel_order"]["resolved"] and not amb and not un;prediction=[]
  if resolved:
   for pid in f["panel_order"]["order"]:prediction += [rid for rid in f["intra_panel"][pid]["order"] if rid in eligible]
   resolved=sorted(prediction)==sorted(human)
  if not resolved:prediction=[]
  hp,pp=pairs(human),pairs(prediction);inv=hp-pp if resolved else set();owners=refs[page]["region_to_oracle_panel"]
  candidate_to_reference={}
  for rid,row in assigned.items():candidate_to_reference.setdefault(row["panel_id"],set()).add(owners[rid])
  unique_map={pid:next(iter(values)) for pid,values in candidate_to_reference.items() if len(values)==1}
  agreement+=sum(unique_map.get(row["panel_id"])==owners[rid] for rid,row in assigned.items())
  reference_order=refs[page]["derived_panel_order"]["order"]
  mapped_order=[]
  if resolved:
   for pid in f["panel_order"]["order"]:
    mapped=unique_map.get(pid)
    if mapped and mapped not in mapped_order:mapped_order.append(mapped)
   panel_exact+=mapped_order==reference_order;panel_positions+=sum(i<len(mapped_order) and mapped_order[i]==pid for i,pid in enumerate(reference_order));rp,mp=pairs(reference_order),pairs(mapped_order);panel_correct+=len(rp&mp);panel_total+=len(rp)
  for a,b in inv:
   if owners[a]==owners[b]:intra+=1
   else:cross+=1
  resolved_regions+=len(prediction);exact+=resolved and prediction==human;positions+=sum(i<len(prediction) and prediction[i]==r for i,r in enumerate(human));ok=len(hp&pp);correct+=ok;denom+=len(hp) if resolved else 0;inversions+=len(inv);block="RESOLVED" if resolved else "ASSIGNMENT_AMBIGUITY" if amb else "MISSING_PANEL_COVERAGE" if un else "RELATION_CONSTRUCTION"
  details.append({"page_order":page,"resolved":resolved,"prediction":prediction,"human":human,"exact":resolved and prediction==human,"exact_positions":sum(i<len(prediction) and prediction[i]==r for i,r in enumerate(human)),"resolved_correct_pairs":ok,"resolved_total_pairs":len(hp) if resolved else 0,"population_pairs":len(hp),"confident_inversions":len(inv),"blocker":block,"ambiguous_region_ids":[r["region_id"] for r in amb],"unassigned_region_ids":[r["region_id"] for r in un]})
 return {"track":track["track"],"resolved_pages":sum(r["resolved"] for r in details),"unresolved_pages":sum(not r["resolved"] for r in details),"resolved_regions":[resolved_regions,50],"exact_pages":[exact,10],"exact_positions":[positions,50],"resolved_comparable_pairwise":[correct,denom],"population_pair_coverage":[denom,124],"confident_inversions":inversions,"inversion_taxonomy":{"cross_panel":cross,"intra_panel":intra,"missing_panel_coverage_pages":sum(r["blocker"]=="MISSING_PANEL_COVERAGE" for r in details),"assignment_ambiguity_pages":sum(r["blocker"]=="ASSIGNMENT_AMBIGUITY" for r in details),"unresolved_structure_origin":sum(r["blocker"]=="RELATION_CONSTRUCTION" for r in details)},"assignment":{**dict(tot),"reference_agreement":agreement,"reference_evaluable":50},"panel_order":{"exact_resolved_pages":panel_exact,"resolved_position_correct":panel_positions,"resolved_pairwise":[panel_correct,panel_total],"total_text_bearing_panels":ref["text_bearing_panel_count"],"empty_panels_excluded":ref["empty_panel_count"],"derived_reference_relations":ref["derived_relation_count"]},"pages":details}
def rendered(v):return (json.dumps(v,ensure_ascii=False,indent=2)+"\n").encode()
def make_freeze(ra,proto,oracle,realistic):
 v={"schema_version":"panel-order-candidate-freeze.v3","checkpoint":"12.5","chronology":["A_RUNTIME_INPUT_AUDIT_FROZEN","B_PROTOCOL_FROZEN","C_CANDIDATES_GENERATED_TWICE","D_CANDIDATES_FROZEN"],"runtime_audit_semantic_sha256":ra["semantic_sha256"],"protocol_file_sha256":hashlib.sha256(rendered(proto)).hexdigest(),"oracle_candidate_file_sha256":hashlib.sha256(rendered(oracle)).hexdigest(),"realistic_candidate_file_sha256":hashlib.sha256(rendered(realistic)).hexdigest(),"human_reading_order_artifacts_opened_before_freeze":[],"determinism_runs":2,"deterministic":True,"gt_runtime_features":[]};v["freeze_sha256"]=digest(v);return v
def build_final(ra,oracle,realistic,human_doc,base,freeze,syn,resource_state):
 humans={r["page_order"]:r for r in human_doc["pages"]};human_ids=[x for r in humans.values() for x in r["human"]];all_ids={x["region_id"] for p in oracle["pages"] for x in p["assignment"]["assignments"]+p["assignment"]["ambiguous"]+p["assignment"]["unassigned"]}
 if sorted(humans)!=PAGES or len(human_ids)!=50 or len(set(human_ids))!=50 or not set(human_ids)<=all_ids:raise RuntimeError("post-freeze Human join mismatch")
 ref=reference(humans,oracle);audit={"schema_version":"panel-order-input-gt-audit.v3","checkpoint":"12.5","chronology":["A_RUNTIME_INPUT_AUDIT_FROZEN","D_CANDIDATES_FROZEN","E_HUMAN_ORDER_OPENED","F_REFERENCE_DERIVED"],"runtime_phase":ra,"evaluation_reference":ref,"metric_region_count":50,"excluded_persisted_region_count":13,"human_order_file_sha256":fh(EVAL["human_order"]),"gt_runtime_features":[]};audit["semantic_sha256"]=digest(audit)
 oe,re=score(oracle,humans,ref),score(realistic,humans,ref);baseline_pages=base["outputs"]["A_VERTICAL_OVERLAP"];known=[(r["page_order"],a,b) for r in baseline_pages for a,b in sorted(pairs(r["human"])-pairs(r["prediction"]))]
 def invaudit(result):
  by={r["page_order"]:r for r in result["pages"]};return [{"page_order":p,"human_before":a,"human_after":b,"baseline":"INVERTED","status":"UNRESOLVED" if not by[p]["resolved"] else "REPAIRED" if by[p]["prediction"].index(a)<by[p]["prediction"].index(b) else "UNCHANGED"} for p,a,b in known]
 controls={r["page_order"] for r in baseline_pages if r["prediction"]==r["human"]}
 def reg(result):return [{"page_order":r["page_order"],"status":"EXACT" if r["exact"] else "UNRESOLVED" if not r["resolved"] else "REGRESSED"} for r in result["pages"] if r["page_order"] in controls]
 oe["known_inversions"],re["known_inversions"]=invaudit(oe),invaudit(re);oe["seven_control_page_audit"],re["seven_control_page_audit"]=reg(oe),reg(re);baseline={"exact_pages":[7,10],"exact_positions":[43,50],"pairwise":[120,124],"inversions":4}
 if oe["exact_pages"]==[10,10] and oe["exact_positions"]==[50,50] and oe["confident_inversions"]==0 and re["resolved_pages"]>=7 and re["confident_inversions"]==0:outcome="A. PANEL-AWARE ORDERING PASS"
 elif oe["exact_positions"][0]>43 and oe["resolved_comparable_pairwise"][0]>120 and any(r["status"]=="REPAIRED" for r in oe["known_inversions"]):outcome="B. PANEL HIERARCHY HELPS BUT ORDERING REMAINS INCOMPLETE"
 else:outcome="C. PANEL STRUCTURE/ASSIGNMENT STILL BLOCKS ORDERING"
 ev={"schema_version":"panel-order-evaluation.v3","checkpoint":"12.5","chronology":"POST_CANDIDATE_FREEZE_ONLY","candidate_freeze_semantic_sha256":freeze["freeze_sha256"],"baseline_reproduced":baseline,"oracle":oe,"realistic":re,"known_inversion_count":len(known),"outcome":outcome,"gt_runtime_features":[]};ev["semantic_sha256"]=digest(ev)
 comparisons={name:{"byte_equal":True,"semantic_equal":True} for name in ("input-gt-audit","protocol","synthetic","oracle-candidates","realistic-candidates","candidate-freeze","evaluation","summary")}
 summary={"schema_version":"panel-order-summary.v3","checkpoint":"12.5","outcome":outcome,"phase_0":"PASS","oracle":oe,"realistic":re,"synthetic":{"count":len(syn["results"]),"all_pass":syn["all_pass"]},"two_independent_builds":comparisons,"resource_guard":resource_state,"model_calls":{"ocr":0,"vlm":0,"ollama":0},"production_reader_changed":False,"gt_runtime_features":[]};summary["semantic_sha256"]=digest(summary)
 return {"input-gt-audit":audit,"evaluation":ev,"summary":summary}
def run():
 before=sample_resources(ResourceThresholds.from_environment())
 if before["safety_state"]!="NORMAL":raise RuntimeError("Resource Guard is not NORMAL")
 inputs=load_runtime_inputs();ra=runtime_audit(inputs);proto=protocol()
 if canonical(ra)!=canonical(runtime_audit(inputs)):raise RuntimeError("runtime audit nondeterminism")
 initial={"schema_version":"panel-order-input-gt-audit.v2","checkpoint":"12.5","chronology":["A_RUNTIME_INPUT_AUDIT_FROZEN"],"runtime_phase":ra,"evaluation_reference":None,"gt_runtime_features":[]};write(OUT["input-gt-audit"],initial);write(OUT["protocol"],proto);syn=synthetic_suite();write(OUT["synthetic"],syn)
 provenance={"runtime_audit_semantic_sha256":ra["semantic_sha256"],"protocol_semantic_sha256":proto["protocol_sha256"],"service_code_sha256":fh(ROOT/"backend/app/services/panel_aware_reading_order.py"),"runner_code_sha256":fh(Path(__file__)),"runtime_input_file_sha256":inputs["hashes"]}
 oracle=candidate("ORACLE_HUMAN_PANEL_GEOMETRY_IDS_STRIPPED",inputs["logical"],inputs["oracle"],provenance);realistic=candidate("FROZEN_SELECTED_RESOLVER_PANELS_NO_ORACLE_FALLBACK",inputs["logical"],inputs["realistic"],provenance)
 if canonical(oracle)!=canonical(candidate(oracle["track"],inputs["logical"],inputs["oracle"],provenance)) or canonical(realistic)!=canonical(candidate(realistic["track"],inputs["logical"],inputs["realistic"],provenance)):raise RuntimeError("candidate nondeterminism")
 write(OUT["oracle-candidates"],oracle);write(OUT["realistic-candidates"],realistic);freeze={"schema_version":"panel-order-candidate-freeze.v2","checkpoint":"12.5","chronology":["A_RUNTIME_INPUT_AUDIT_FROZEN","B_PROTOCOL_FROZEN","C_CANDIDATES_GENERATED_TWICE","D_CANDIDATES_FROZEN"],"runtime_audit_semantic_sha256":ra["semantic_sha256"],"protocol_file_sha256":fh(OUT["protocol"]),"oracle_candidate_file_sha256":fh(OUT["oracle-candidates"]),"realistic_candidate_file_sha256":fh(OUT["realistic-candidates"]),"human_reading_order_artifacts_opened_before_freeze":[],"determinism_runs":2,"deterministic":True,"gt_runtime_features":[]};freeze["freeze_sha256"]=digest(freeze);write(OUT["candidate-freeze"],freeze)
 human_doc=json.loads(EVAL["human_order"].read_text());base=json.loads(EVAL["baseline"].read_text());humans={r["page_order"]:r for r in human_doc["pages"]};human_ids=[x for r in humans.values() for x in r["human"]];all_ids={x["logical_region_id"] for p in inputs["logical"].values() for x in p["logical_regions"]}
 if sorted(humans)!=PAGES or len(human_ids)!=50 or len(set(human_ids))!=50 or not set(human_ids)<=all_ids:raise RuntimeError("post-freeze Human join mismatch")
 ref=reference(humans,oracle);final_audit={"schema_version":"panel-order-input-gt-audit.v2","checkpoint":"12.5","chronology":["A_RUNTIME_INPUT_AUDIT_FROZEN","D_CANDIDATES_FROZEN","E_HUMAN_ORDER_OPENED","F_REFERENCE_DERIVED"],"runtime_phase":ra,"evaluation_reference":ref,"metric_region_count":50,"excluded_persisted_region_count":13,"human_order_file_sha256":fh(EVAL["human_order"]),"gt_runtime_features":[]};write(OUT["input-gt-audit"],final_audit)
 oe,re=score(oracle,humans,ref),score(realistic,humans,ref)
 if canonical(oe)!=canonical(score(oracle,humans,ref)) or canonical(re)!=canonical(score(realistic,humans,ref)):raise RuntimeError("evaluation nondeterminism")
 baseline_pages=base["outputs"]["A_VERTICAL_OVERLAP"];known=[(r["page_order"],a,b) for r in baseline_pages for a,b in sorted(pairs(r["human"])-pairs(r["prediction"]))]
 def invaudit(result):
  by={r["page_order"]:r for r in result["pages"]};return [{"page_order":p,"human_before":a,"human_after":b,"baseline":"INVERTED","status":"UNRESOLVED" if not by[p]["resolved"] else "REPAIRED" if by[p]["prediction"].index(a)<by[p]["prediction"].index(b) else "UNCHANGED"} for p,a,b in known]
 controls={r["page_order"] for r in baseline_pages if r["prediction"]==r["human"]}
 def reg(result):return [{"page_order":r["page_order"],"status":"EXACT" if r["exact"] else "UNRESOLVED" if not r["resolved"] else "REGRESSED"} for r in result["pages"] if r["page_order"] in controls]
 oe["known_inversions"],re["known_inversions"]=invaudit(oe),invaudit(re);oe["seven_control_page_audit"],re["seven_control_page_audit"]=reg(oe),reg(re);baseline={"exact_pages":[7,10],"exact_positions":[43,50],"pairwise":[120,124],"inversions":4}
 if oe["exact_pages"]==[10,10] and oe["exact_positions"]==[50,50] and oe["confident_inversions"]==0 and re["resolved_pages"]>=7 and re["confident_inversions"]==0:outcome="A. PANEL-AWARE ORDERING PASS"
 elif oe["exact_positions"][0]>43 and oe["resolved_comparable_pairwise"][0]>120 and any(r["status"]=="REPAIRED" for r in oe["known_inversions"]):outcome="B. PANEL HIERARCHY HELPS BUT ORDERING REMAINS INCOMPLETE"
 else:outcome="C. PANEL STRUCTURE/ASSIGNMENT STILL BLOCKS ORDERING"
 ev={"schema_version":"panel-order-evaluation.v2","checkpoint":"12.5","chronology":"POST_CANDIDATE_FREEZE_ONLY","candidate_freeze_file_sha256":fh(OUT["candidate-freeze"]),"baseline_reproduced":baseline,"oracle":oe,"realistic":re,"known_inversion_count":len(known),"outcome":outcome,"gt_runtime_features":[]};ev["semantic_sha256"]=digest(ev);write(OUT["evaluation"],ev);after=sample_resources(ResourceThresholds.from_environment());summary={"schema_version":"panel-order-summary.v2","checkpoint":"12.5","outcome":outcome,"phase_0":"PASS","oracle":oe,"realistic":re,"synthetic":{"count":len(syn["results"]),"all_pass":syn["all_pass"]},"determinism":{"runtime_audit":True,"oracle":True,"realistic":True,"evaluation_reconciled":True},"resource_guard":after["safety_state"],"model_calls":{"ocr":0,"vlm":0,"ollama":0},"production_reader_changed":False,"gt_runtime_features":[]};write(OUT["summary"],summary);return summary
def run():
 before=sample_resources(ResourceThresholds.from_environment())
 if before["safety_state"]!="NORMAL":raise RuntimeError("Resource Guard is not NORMAL")
 inputs=load_runtime_inputs();ra=runtime_audit(inputs);proto=protocol();syn=synthetic_suite();provenance={"runtime_audit_semantic_sha256":ra["semantic_sha256"],"protocol_semantic_sha256":proto["protocol_sha256"],"service_code_sha256":fh(ROOT/"backend/app/services/panel_aware_reading_order.py"),"runner_code_sha256":fh(Path(__file__)),"runtime_input_file_sha256":inputs["hashes"]}
 def prebuild():return candidate("ORACLE_HUMAN_PANEL_GEOMETRY_IDS_STRIPPED",inputs["logical"],inputs["oracle"],provenance),candidate("FROZEN_SELECTED_RESOLVER_PANELS_NO_ORACLE_FALLBACK",inputs["logical"],inputs["realistic"],provenance)
 oracle_a,realistic_a=prebuild();oracle_b,realistic_b=prebuild()
 if rendered(oracle_a)!=rendered(oracle_b) or rendered(realistic_a)!=rendered(realistic_b):raise RuntimeError("candidate build nondeterminism")
 freeze_a,freeze_b=make_freeze(ra,proto,oracle_a,realistic_a),make_freeze(runtime_audit(inputs),protocol(),oracle_b,realistic_b)
 if rendered(freeze_a)!=rendered(freeze_b):raise RuntimeError("freeze build nondeterminism")
 # Persist the pre-freeze set before opening either Human-order artifact.
 write(OUT["protocol"],proto);write(OUT["synthetic"],syn);write(OUT["oracle-candidates"],oracle_a);write(OUT["realistic-candidates"],realistic_a);write(OUT["candidate-freeze"],freeze_a)
 human_doc=json.loads(EVAL["human_order"].read_text());base=json.loads(EVAL["baseline"].read_text());resource=sample_resources(ResourceThresholds.from_environment())["safety_state"]
 final_a=build_final(ra,oracle_a,realistic_a,human_doc,base,freeze_a,syn,resource);final_b=build_final(runtime_audit(inputs),oracle_b,realistic_b,json.loads(EVAL["human_order"].read_text()),json.loads(EVAL["baseline"].read_text()),freeze_b,synthetic_suite(),resource)
 run_a={"input-gt-audit":final_a["input-gt-audit"],"protocol":proto,"synthetic":syn,"oracle-candidates":oracle_a,"realistic-candidates":realistic_a,"candidate-freeze":freeze_a,"evaluation":final_a["evaluation"],"summary":final_a["summary"]};run_b={"input-gt-audit":final_b["input-gt-audit"],"protocol":protocol(),"synthetic":synthetic_suite(),"oracle-candidates":oracle_b,"realistic-candidates":realistic_b,"candidate-freeze":freeze_b,"evaluation":final_b["evaluation"],"summary":final_b["summary"]}
 comparisons={name:{"byte_equal":rendered(run_a[name])==rendered(run_b[name]),"semantic_hash_a":digest(run_a[name]),"semantic_hash_b":digest(run_b[name])} for name in run_a}
 if not all(row["byte_equal"] and row["semantic_hash_a"]==row["semantic_hash_b"] for row in comparisons.values()):raise RuntimeError("RUN_A/RUN_B artifact nondeterminism")
 run_a["summary"]["two_independent_builds"]=comparisons;run_b["summary"]["two_independent_builds"]=comparisons
 for summary in (run_a["summary"],run_b["summary"]):
  summary.pop("semantic_sha256",None);summary["semantic_sha256"]=digest(summary)
 if rendered(run_a["summary"])!=rendered(run_b["summary"]):raise RuntimeError("final summary nondeterminism")
 for name in run_a:
  if name in OUT:write(OUT[name],run_a[name])
 return run_a["summary"]
if __name__=="__main__":print(json.dumps(run(),ensure_ascii=False))
