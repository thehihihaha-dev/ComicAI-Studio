#!/usr/bin/env python3
"""Finite offline Checkpoint 12.7 PCPDAG experiment."""
from __future__ import annotations

import copy, hashlib, importlib.util, json, sys, tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from app.services.panel_aware_reading_order import (assign_regions, order_regions_in_panel,
    canonical_projection_panels, panel_aware_projection_order, projection_constraint_order)
from app.services.resource_safety import ResourceThresholds,sample_resources

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);assert spec and spec.loader
 sys.modules[name]=module;spec.loader.exec_module(module);return module
TOL=load("panel_relation_tolerance_12_6",ROOT/"scripts/panel_relation_tolerance_12_6.py");BASE=TOL.BASE
DAY12=ROOT/"benchmarks/day12";NAMES=("input-audit","control-reference","protocol","synthetic","oracle-candidates","candidate-freeze","structural-audit","evaluation","historical-audit","summary")
OUT={n:DAY12/f"panel-relation-model-{n}-12.7.json" for n in NAMES}
CONTROL={"candidate-freeze":"7d7e2f8f6a9ae15b0f6052ddcf7491d7a66bcddbe9e8cdfd5cd2e3399ea10188","control-reference":"e75acd0337e939b73ecd41ca1a96d9d43c709ea17d60ff49feb0b584a7c5af84","evaluation":"5981c218cebaa685efdbd978c8b87f3774c0b851c6acbcc12e8b5c5115371155","input-audit":"8e83de00ae062c63cfe2225dc853005dd060fcba4e44f8fe949de26a1030db2b","oracle-candidates":"5bc83174e3b040c9ca1ade4434b51cced24ce7e1a23748dc6376dfe20d57ed6d","protocol":"a937ddabc14c5ba4829311743aec9b73e543b92e4a88755e95c5081feb764d5d","realistic-candidates":"984adf961b1973b8c3c0dec0345e08c5955b44958db62c4131333db911946f9a","summary":"c0baf16a1af55021359a473394a61469743308a18ba259b55f69ae29cc9d2974","synthetic":"7d51e1055c796537f04d6c7cb36a23e4af4155c419c1b1c7bede130f75bc120f"}
LABEL="EXPERIMENT_PREDECLARED_PROJECTION_CONSTRAINT_DAG_V1"

canonical=TOL.canonical;digest=TOL.digest;rendered=TOL.rendered;stamp=TOL.stamp;file_hash=TOL.file_hash;verify_internal_hash=TOL.verify_internal_hash

@dataclass
class Barrier:
 generated:set[str]=field(default_factory=set);freeze_documents:set[str]=field(default_factory=set);frozen:set[str]=field(default_factory=set);active:bool=False;human_open:bool=False;events:list[str]=field(default_factory=list)
 def candidate(self,name):
  if self.human_open:raise RuntimeError("candidate generation forbidden after Human-order access")
  if self.frozen:raise RuntimeError("candidate generation forbidden after freeze begins")
  self.generated.add(name);self.events.append(f"{name}_GENERATED")
 def freeze(self,name):
  if self.generated!={"RUN_A","RUN_B"}:raise RuntimeError("both candidates must be generated before either freeze")
  if self.freeze_documents!={"RUN_A","RUN_B"}:raise RuntimeError("both freeze documents must be built before either freeze")
  self.frozen.add(name);self.events.append(f"{name}_FROZEN")
 def freeze_document(self,name):
  if self.generated!={"RUN_A","RUN_B"} or self.frozen:raise RuntimeError("freeze document requires both generated and neither frozen")
  self.freeze_documents.add(name);self.events.append(f"{name}_FREEZE_DOCUMENT_BUILT")
 def activate(self):
  if self.frozen!={"RUN_A","RUN_B"}:raise RuntimeError("global freeze requires both runs")
  self.active=True;self.events.append("GLOBAL_FREEZE_BARRIER_ACTIVE")
 def open(self,path,label):
  if not self.active:raise RuntimeError("Human-order/evaluation access forbidden before global freeze")
  if "HUMAN" in label or "EVALUATION" in label:self.human_open=True
  self.events.append(f"POST_FREEZE_OPEN:{label}");return json.loads(path.read_text())
 def assert_evaluation(self):
  if not self.active or self.frozen!={"RUN_A","RUN_B"}:raise RuntimeError("evaluation forbidden before global freeze")
  self.events.append("EVALUATION_ALLOWED")

def verify_control(paths=None):
 paths=paths or {n:DAY12/f"panel-relation-tolerance-{n}-12.6.json" for n in CONTROL}
 if set(paths)!=set(CONTROL):raise RuntimeError("12.6 control artifact set mismatch")
 rows=[]
 for name in sorted(paths):
  actual=file_hash(paths[name])
  if actual!=CONTROL[name]:raise RuntimeError(f"12.6 control fingerprint mismatch: {name}")
  rows.append({"artifact":name,"path":str(paths[name].relative_to(ROOT)) if paths[name].is_relative_to(ROOT) else str(paths[name]),"file_sha256":actual,"json_parse":"DEFERRED_UNTIL_GLOBAL_FREEZE"})
 return stamp({"schema_version":"panel-relation-model-control-reference.v1","checkpoint":"12.7","status":"FROZEN_12_6_ONE_PIXEL_ORACLE_CONTROL_RAW_BYTES_VERIFIED","artifacts":rows,"human_order_derived_provenance_dependencies":[],"gt_runtime_features":[]})

def pre_freeze_control():
 return stamp({"schema_version":"panel-relation-model-control-reference.v2","checkpoint":"12.7","status":"12.6_FULL_CONTROL_VERIFICATION_DEFERRED_UNTIL_GLOBAL_FREEZE","control_identity":"CHECKPOINT_12.6_ACCEPTED_ORACLE_ONE_PIXEL","artifacts":[],"artifact_hashes":[],"human_derived_pre_freeze_dependencies":[],"human_order_derived_provenance_dependencies":[],"gt_runtime_features":[]})

def verify_post_freeze_control(barrier):
 if not barrier.active or barrier.frozen!={"RUN_A","RUN_B"}:raise RuntimeError("control verification forbidden before global freeze")
 reference=verify_control();docs={}
 for name in sorted(CONTROL):
  label="CONTROL_EVALUATION" if name in {"evaluation","summary"} else "CONTROL_POST_FREEZE"
  value=barrier.open(DAY12/f"panel-relation-tolerance-{name}-12.6.json",f"{label}:{name}")
  if not verify_internal_hash(value):raise RuntimeError(f"12.6 post-freeze internal hash mismatch: {name}")
  docs[name]=value
 return reference,docs

def protocol():
 return stamp({"schema_version":"panel-relation-model-protocol.v1","checkpoint":"12.7","status":"FROZEN_BEFORE_HUMAN_ORDER","label":LABEL,"candidate_count":1,"track":"ORACLE_ONLY","realistic":"DIAGNOSTICS_ONLY_NO_CANDIDATE","formula":{"tau_x":"1/W","tau_y":"1/H","source_pixel_intrusion":1,"comparison":"<=","vertical_precedence":True},"relations":["ABOVE","RIGHT_OF"],"ambiguity":"UNIQUE_ACTIVE_TOPOLOGICAL_ORDER_REQUIRED","transitivity":"ACTIVE_NODES_ONLY","assignment":["UNIQUE_CONTAINMENT","UNIQUE_CENTER_AND_STRICT_AREA_MAJORITY_GT_0.50","AMBIGUOUS","UNASSIGNED"],"intra_panel":"ANY_PEER_NORMALIZED_VERTICAL_OVERLAP_GTE_0.50","taxonomy_precedence":["INVALID_OR_CONFLICTING_GEOMETRY","CYCLE_CONFLICT","INCOMPARABLE_ACTIVE_PAIR","MULTIPLE_TOPOLOGICAL_ORDERS","GUILLOTINE_DESCENDANT_PARTITION_FAILURE","NO_GUILLOTINE_ROOT","OTHER_EVIDENCED_STRUCTURE"],"gt_runtime_features":[]},"protocol_sha256")

def validate_protocol(p):
 if not verify_internal_hash(p) or p.get("label")!=LABEL or p.get("candidate_count")!=1 or p["formula"]!={"tau_x":"1/W","tau_y":"1/H","source_pixel_intrusion":1,"comparison":"<=","vertical_precedence":True}:raise RuntimeError("protocol mutation")

def input_audit(inputs):
 runtime=copy.deepcopy(BASE.runtime_audit(inputs));runtime.pop("expected_post_freeze_metric_region_count",None);runtime.pop("semantic_sha256",None);runtime["semantic_sha256"]=digest(runtime)
 return stamp({"schema_version":"panel-relation-model-input-audit.v1","checkpoint":"12.7","status":"PRE_CANDIDATE_NON_ORDER_INPUTS_VERIFIED","runtime_phase":runtime,"human_reading_order_loaded":False,"gt_runtime_features":[]})

def provenance(audit,control,proto):
 deps={"audit":audit,"control":control,"protocol":proto};bad=TOL.audit_provenance_dependency(deps)
 def hidden_human(value):
  if isinstance(value,dict):return any("human_derived" in str(k).lower() and v not in ([],False,None) or hidden_human(v) for k,v in value.items())
  if isinstance(value,list):return any(hidden_human(v) for v in value)
  return isinstance(value,str) and value.upper()=="HUMAN_DERIVED"
 if control.get("artifacts") or control.get("artifact_hashes") or hidden_human(deps):bad.append("transitive_human_derived_fingerprint")
 if bad:raise RuntimeError("Human-order-derived provenance dependency: "+", ".join(bad))
 return {"input_audit_semantic_sha256":audit["semantic_sha256"],"control_reference_semantic_sha256":control["semantic_sha256"],"protocol_sha256":proto["protocol_sha256"],"dependency_closure":[{"name":k,"human_order_derived":False} for k in sorted(deps)],"human_derived_pre_freeze_dependencies":[],"human_order_derived_provenance_dependencies":[],"gt_runtime_features":[]}

def candidate(inputs,prov):
 if sorted(inputs["logical"])!=BASE.PAGES or sorted(inputs["oracle"])!=BASE.PAGES:raise RuntimeError("unexpected candidate page set")
 dims={r["page_order"]:tuple(r["image_dimensions"]) for r in inputs["records"]};pages=[]
 for page in BASE.PAGES:
  regions=[{"id":r["logical_region_id"],"bbox":r["bbox"]} for r in inputs["logical"][page]["logical_regions"]]
  panels=canonical_projection_panels(inputs["oracle"][page]["panels"],dims[page])
  result=panel_aware_projection_order(regions,panels,dims[page])
  pages.append({"page_order":page,"source_hash":inputs["logical"][page]["source_hash"],"source_dimensions":list(dims[page]),"panel_source":"ORACLE_HUMAN_PANEL_GEOMETRY_IDS_STRIPPED","panel_nodes":panels,**result})
 return stamp({"schema_version":"panel-relation-model-oracle-candidates.v1","checkpoint":"12.7","track":"ORACLE_ONLY","representation":LABEL,"provenance":prov,"pages":pages,"gt_runtime_features":[],"model_calls":{"ocr":0,"vlm":0,"ollama":0}})

def validate_candidate_artifact(value):
 if not verify_internal_hash(value):raise RuntimeError("candidate artifact fingerprint mismatch")
 if value.get("track")!="ORACLE_ONLY" or [p["page_order"] for p in value.get("pages",[])]!=BASE.PAGES:raise RuntimeError("candidate artifact cohort mismatch")
 bad=TOL.audit_provenance_dependency(value.get("provenance",{}))
 if bad or value.get("gt_runtime_features")!=[]:raise RuntimeError("candidate provenance contamination")

def synthetic_suite():
 def ps(boxes):return [{"panel_id":f"p{i}","bbox":b} for i,b in enumerate(boxes)]
 layouts=[("empty",[],[]),("single",[[0,0,100,100]],["p0"]),("horizontal",[[0,0,40,100],[60,0,100,100]],["p1","p0"]),("vertical",[[0,0,100,40],[0,60,100,100]],["p0","p1"]),("2x2",[[0,0,40,40],[60,0,100,40],[0,60,40,100],[60,60,100,100]],["p1","p0","p3","p2"]),("tall_right",[[60,0,100,100],[0,0,40,40],[0,60,40,100]],["p0","p1","p2"]),("tall_left",[[0,0,40,100],[60,0,100,40],[60,60,100,100]],["p1","p2","p0"]),("span_top",[[0,0,100,30],[0,40,40,100],[60,40,100,100]],["p0","p2","p1"]),("span_bottom",[[0,0,40,60],[60,0,100,60],[0,70,100,100]],["p1","p0","p2"]),("offset",[[0,0,42,35],[58,5,100,40],[5,60,45,100],[55,55,95,95]],["p1","p0","p3","p2"]),("partial_row",[[0,0,40,45],[60,5,100,40]],["p1","p0"]),("partial_column",[[5,0,45,40],[0,60,40,100]],["p0","p1"]),("non_guillotine",[[60,0,100,100],[0,0,40,40],[0,60,40,100]],["p0","p1","p2"]),("multiple_trees",[[0,0,40,40],[60,0,100,40],[0,60,40,100],[60,60,100,100]],["p1","p0","p3","p2"]),("ambiguous",[[0,0,70,70],[30,30,100,100]],None),("overlap",[[0,0,80,60],[20,40,100,100]],None),("bridge",[[0,0,30,30],[40,0,70,70],[80,40,110,70]],None),("equal_1px",[[0,0,100,51],[0,50,100,100]],["p0","p1"]),("beyond_1px",[[0,0,100,51.1],[0,50,100,100]],None),("diagonal_same",[[60,0,100,40],[0,60,40,100]],["p0","p1"]),("diagonal_opposed",[[0,0,40,40],[60,60,100,100]],["p0","p1"]),("incomparable",[[0,0,70,70],[30,30,100,100]],None)]
 rows=[]
 for name,boxes,expected in layouts:
  trace=projection_constraint_order(ps(boxes),(120,120));observed=trace["order"] if trace["resolved"] else None
  rows.append({"fixture":name,"path":"projection_constraint_order","expected":expected,"observed":observed,"pass":observed==expected,"trace":trace})
 cycle=projection_constraint_order(ps([[61,3,75,65],[78,56,97,90],[23,52,56,54]]),(100,100));rows.append({"fixture":"explicit_cycle","path":"projection_constraint_order","expected":None,"observed":cycle["order"] or None,"pass":not cycle["resolved"] and bool(cycle["cycles"]),"trace":cycle})
 perm=ps([[0,0,40,100],[60,0,100,100]]);a=projection_constraint_order(perm,(100,100));b=projection_constraint_order(list(reversed(perm)),(100,100));rows.append({"fixture":"permutation","path":"projection_constraint_order","expected":a["order"],"observed":b["order"],"pass":canonical(a)==canonical(b),"trace":b})
 ap=ps([[0,0,40,100],[60,0,100,100]]);regions=[{"id":"contained","bbox":[5,5,10,10]},{"id":"majority","bbox":[35,10,42,20]},{"id":"outside","bbox":[110,0,120,10]}];ass=assign_regions(regions,ap);rows.append({"fixture":"assignment","path":"assign_regions","expected":"FROZEN","observed":ass,"pass":[r["region_id"] for r in ass["assignments"]]==["contained","majority"] and [r["region_id"] for r in ass["unassigned"]]==["outside"],"trace":ass})
 local=order_regions_in_panel([{"id":"right","bbox":[60,0,70,10]},{"id":"left","bbox":[10,0,20,10]}]);rows.append({"fixture":"intra_panel","path":"order_regions_in_panel","expected":["right","left"],"observed":local["order"],"pass":local["order"]==["right","left"],"trace":local})
 return stamp({"schema_version":"panel-relation-model-synthetic.v1","checkpoint":"12.7","fixture_group_count":len(rows),"results":rows,"all_pass":all(r["pass"] for r in rows),"gt_runtime_features":[]})

def freeze(audit,control,proto,syn,oracle):
 return stamp({"schema_version":"panel-relation-model-candidate-freeze.v1","checkpoint":"12.7","chronology":["INPUT_VERIFIED","STRUCTURAL_RUNTIME_READY","ORACLE_CANDIDATE_GENERATED","CANDIDATE_FROZEN_BEFORE_HUMAN_ORDER"],"artifacts":{"input-audit":audit["semantic_sha256"],"control-reference":control["semantic_sha256"],"protocol":proto["protocol_sha256"],"synthetic":syn["semantic_sha256"],"oracle-candidates":oracle["semantic_sha256"]},"candidate_count":1,"human_reading_order_artifacts_opened_before_freeze":[],"gt_runtime_features":[]},"freeze_sha256")

def structural(candidate_doc,control_doc):
 control={p["page_order"]:p for p in control_doc["pages"]};blocked=[p for p in control.values() if not p["panel_order"]["resolved"]]
 if len(blocked)!=7:raise RuntimeError("accepted control blocker count mismatch")
 cand={p["page_order"]:p for p in candidate_doc["pages"]};rows=[]
 for old in sorted(blocked,key=lambda x:x["page_order"]):
  page=cand[old["page_order"]];reasons=[r["reason"] for r in page["panel_order"]["unresolved"]]
  if "CONFLICTING_AXIS_EVIDENCE" in reasons:primary="INVALID_OR_CONFLICTING_GEOMETRY"
  elif "CYCLE" in reasons:primary="CYCLE_CONFLICT"
  elif "INCOMPARABLE_ACTIVE_PAIR" in reasons:primary="INCOMPARABLE_ACTIVE_PAIR"
  elif "MULTIPLE_TOPOLOGICAL_ORDERS" in reasons:primary="MULTIPLE_TOPOLOGICAL_ORDERS"
  elif old["panel_order"].get("partitions"):primary="GUILLOTINE_DESCENDANT_PARTITION_FAILURE"
  else:primary="NO_GUILLOTINE_ROOT"
  rows.append({"page_order":page["page_order"],"control_reason":[r["reason"] for r in old["panel_order"]["unresolved"]],"candidate_status":page["status"],"primary_reason":primary,"candidate_unresolved":page["panel_order"]["unresolved"],"geometry_only":True})
 return stamp({"schema_version":"panel-relation-model-structural-audit.v1","checkpoint":"12.7","chronology":"POST_GLOBAL_FREEZE_PRE_HUMAN_ORDER","population_derivation":"FROZEN_12.6_ORACLE_RELATION_UNRESOLVED","blocker_count":len(rows),"pages":rows,"human_order_loaded":False,"gt_runtime_features":[]})

def evaluate(oracle,human_doc,baseline,control_eval,freeze_doc,structural_doc,resource,barrier):
 barrier.assert_evaluation()
 humans={r["page_order"]:r for r in human_doc["pages"]};ref=BASE.reference(humans,oracle);result=BASE.score(oracle,humans,ref)
 base_pages=baseline["outputs"]["A_VERTICAL_OVERLAP"];known=[(r["page_order"],a,b) for r in base_pages for a,b in sorted(BASE.pairs(r["human"])-BASE.pairs(r["prediction"]))];by={r["page_order"]:r for r in result["pages"]}
 historical=[{"page_order":p,"human_before":a,"human_after":b,"status":"UNRESOLVED" if not by[p]["resolved"] else "REPAIRED" if by[p]["prediction"].index(a)<by[p]["prediction"].index(b) else "STILL_INVERTED"} for p,a,b in known]
 control=control_eval["candidate"]["oracle"];delta=TOL.delta(result,control);control_pages={p["page_order"]:p for p in control["pages"]};regressions=[p for p in result["pages"] if control_pages[p["page_order"]]["exact"] and not p["exact"]]
 def assignment_signature(page):
  boxes={p["panel_id"]:canonical(p["bbox"]).decode() for p in page["panel_nodes"]}
  assigned=sorted((r["region_id"],boxes[r["panel_id"]],r["method"],r["state"]) for r in page["assignment"]["assignments"])
  def unresolved(rows):return sorted((r["region_id"],r["reason"],tuple(sorted((boxes[c["panel_id"]],c["coverage"],c["contains"],c["center_inside"]) for c in r["competing_panels"]))) for r in rows)
  local=sorted((boxes[pid],tuple(value["order"]),value["rule"]) for pid,value in page["intra_panel"].items())
  return {"assigned":assigned,"ambiguous":unresolved(page["assignment"]["ambiguous"]),"unassigned":unresolved(page["assignment"]["unassigned"]),"local":local}
 control_candidate=json.loads((DAY12/"panel-relation-tolerance-oracle-candidates-12.6.json").read_text());assignment_same=all(canonical(assignment_signature(a))==canonical(assignment_signature(b)) for a,b in zip(oracle["pages"],control_candidate["pages"]))
 hard=[]
 if result["confident_inversions"]:hard.append("NEW_CONFIDENT_INVERSION")
 if regressions:hard.append("PREVIOUSLY_EXACT_PAGE_REGRESSION")
 if not assignment_same:hard.append("ASSIGNMENT_OR_INTRA_PANEL_MUTATION")
 if hard:outcome="D. UNSAFE RELATION REPRESENTATION"
 elif result["exact_pages"]==[10,10] and result["resolved_regions"]==[50,50] and result["population_pair_coverage"]==[124,124]:outcome="A. RELATION REPRESENTATION PASS"
 elif delta["resolved_pages"]>0 or delta["resolved_regions"]>0 or delta["resolved_pairs"]>0:outcome="B. PARTIAL RELATION RECOVERY"
 else:outcome="C. RELATION REPRESENTATION INSUFFICIENT"
 hist=stamp({"schema_version":"panel-relation-model-historical-audit.v1","checkpoint":"12.7","day11":historical,"previously_exact_regressions":[p["page_order"] for p in regressions],"gt_runtime_features":[]})
 ev=stamp({"schema_version":"panel-relation-model-evaluation.v1","checkpoint":"12.7","chronology":"POST_CANDIDATE_FREEZE_ONLY","freeze_sha256":freeze_doc["freeze_sha256"],"control":control,"candidate":result,"delta":delta,"structural_audit_sha256":structural_doc["semantic_sha256"],"assignment_and_intra_panel_unchanged":assignment_same,"hard_safety_failures":hard,"outcome":outcome,"gt_runtime_features":[]})
 summary=stamp({"schema_version":"panel-relation-model-summary.v1","checkpoint":"12.7","outcome":outcome,"control":{"resolved_pages":3,"resolved_regions":19,"population_pairs":55,"confident_inversions":0},"candidate":result,"delta":delta,"hard_safety_failures":hard,"structural_blockers":structural_doc["pages"],"resource_guard":resource,"model_calls":{"ocr":0,"vlm":0,"ollama":0},"realistic":"DIAGNOSTICS_ONLY_NO_CANDIDATE","production_changed":False,"gt_runtime_features":[]})
 return {"evaluation":ev,"historical-audit":hist,"summary":summary}

def prebuild(barrier,name):
 barrier.candidate(name);inputs=BASE.load_runtime_inputs();audit=input_audit(inputs);control=pre_freeze_control();proto=protocol();validate_protocol(proto);syn=synthetic_suite();prov=provenance(audit,control,proto);prov.update({"service_code_sha256":file_hash(ROOT/"backend/app/services/panel_aware_reading_order.py"),"runner_code_sha256":file_hash(Path(__file__))});oracle=candidate(inputs,prov);validate_candidate_artifact(oracle);return {"input-audit":audit,"control-reference":control,"protocol":proto,"synthetic":syn,"oracle-candidates":oracle}

def comparison_material(name,value):
 material=copy.deepcopy(value);material.pop("semantic_sha256",None);material.pop("protocol_sha256",None);material.pop("freeze_sha256",None)
 if name=="summary":material.pop("two_independent_builds",None)
 return material

def comparison_record(name,a,b):
 if name=="summary":
  ma,mb=comparison_material(name,a),comparison_material(name,b);raw_a,raw_b=hashlib.sha256(rendered(ma)).hexdigest(),hashlib.sha256(rendered(mb)).hexdigest();sem_a,sem_b=digest(ma),digest(mb);convention="SUMMARY_EXCLUDES_SELF_HASH_AND_DETERMINISM_ENVELOPE"
 else:
  raw_a,raw_b=hashlib.sha256(rendered(a)).hexdigest(),hashlib.sha256(rendered(b)).hexdigest();sem_a,sem_b=digest(a),digest(b);convention="FINAL_PERSISTED_ARTIFACT"
 return {"artifact":name,"path":str(OUT[name].relative_to(ROOT)),"schema_version":a.get("schema_version"),"raw_hash_convention":convention,"raw_byte_sha256_a":raw_a,"raw_byte_sha256_b":raw_b,"canonical_semantic_sha256_a":sem_a,"canonical_semantic_sha256_b":sem_b,"byte_equal":rendered(a)==rendered(b),"semantic_equal":sem_a==sem_b}

def run():
 if sample_resources(ResourceThresholds.from_environment())["safety_state"]!="NORMAL":raise RuntimeError("Resource Guard is not NORMAL")
 barrier=Barrier();a=prebuild(barrier,"RUN_A");b=prebuild(barrier,"RUN_B")
 for name in NAMES[:5]:
  if rendered(a[name])!=rendered(b[name]):raise RuntimeError(f"pre-freeze nondeterminism: {name}")
 barrier.freeze_document("RUN_A");a["candidate-freeze"]=freeze(a["input-audit"],a["control-reference"],a["protocol"],a["synthetic"],a["oracle-candidates"])
 barrier.freeze_document("RUN_B");b["candidate-freeze"]=freeze(b["input-audit"],b["control-reference"],b["protocol"],b["synthetic"],b["oracle-candidates"])
 if rendered(a["candidate-freeze"])!=rendered(b["candidate-freeze"]):raise RuntimeError("candidate-freeze nondeterminism")
 barrier.freeze("RUN_A");barrier.freeze("RUN_B");barrier.activate()
 control_a=barrier.open(DAY12/"panel-relation-tolerance-oracle-candidates-12.6.json","CONTROL_CANDIDATE");control_b=barrier.open(DAY12/"panel-relation-tolerance-oracle-candidates-12.6.json","CONTROL_CANDIDATE")
 a["structural-audit"]=structural(a["oracle-candidates"],control_a);b["structural-audit"]=structural(b["oracle-candidates"],control_b)
 post_freeze_control,post_freeze_docs=verify_post_freeze_control(barrier)
 human_a=barrier.open(BASE.EVAL["human_order"],"HUMAN_READING_ORDER");base_a=barrier.open(BASE.EVAL["baseline"],"HUMAN_BASELINE");eval_a=copy.deepcopy(post_freeze_docs["evaluation"])
 human_b=barrier.open(BASE.EVAL["human_order"],"HUMAN_READING_ORDER");base_b=barrier.open(BASE.EVAL["baseline"],"HUMAN_BASELINE");eval_b=copy.deepcopy(post_freeze_docs["evaluation"])
 resource=sample_resources(ResourceThresholds.from_environment())["safety_state"];a.update(evaluate(a["oracle-candidates"],human_a,base_a,eval_a,a["candidate-freeze"],a["structural-audit"],resource,barrier));b.update(evaluate(b["oracle-candidates"],human_b,base_b,eval_b,b["candidate-freeze"],b["structural-audit"],resource,barrier))
 for docs in (a,b):docs["evaluation"]["post_freeze_control_reference_semantic_sha256"]=post_freeze_control["semantic_sha256"];docs["evaluation"].pop("semantic_sha256");docs["evaluation"]["semantic_sha256"]=digest(docs["evaluation"]);docs["summary"]["global_freeze_chronology"]=barrier.events;docs["summary"]["determinism_contract"]={"semantic_material":"FINAL_ARTIFACT_EXCLUDING_SELF_HASH_AND_SUMMARY_DETERMINISM_ENVELOPE","raw_material":"RENDERED_FINAL_ARTIFACT_EXCEPT_SUMMARY_USES_SAME_EXCLUDED_MATERIAL","final_summary_raw_equality_verified":True};docs["summary"].pop("semantic_sha256");docs["summary"]["semantic_sha256"]=digest(docs["summary"])
 for docs in (a,b):docs["evaluation"]["post_freeze_control_internal_hashes_verified"]=sorted(post_freeze_docs);docs["evaluation"].pop("semantic_sha256");docs["evaluation"]["semantic_sha256"]=digest(docs["evaluation"])
 comparisons={n:comparison_record(n,a[n],b[n]) for n in NAMES}
 if not all(r["byte_equal"] and r["semantic_equal"] and r["raw_byte_sha256_a"]==r["raw_byte_sha256_b"] for r in comparisons.values()):raise RuntimeError("RUN_A/RUN_B artifact nondeterminism")
 for docs in (a,b):docs["summary"]["two_independent_builds"]=comparisons;docs["summary"].pop("semantic_sha256");docs["summary"]["semantic_sha256"]=digest(docs["summary"])
 if rendered(a["summary"])!=rendered(b["summary"]):raise RuntimeError("summary nondeterminism")
 with tempfile.TemporaryDirectory() as one,tempfile.TemporaryDirectory() as two:
  for n in NAMES:
   (Path(one)/n).write_bytes(rendered(a[n]));(Path(two)/n).write_bytes(rendered(b[n]))
   if (Path(one)/n).read_bytes()!=(Path(two)/n).read_bytes():raise RuntimeError("isolated output mismatch")
 for n in NAMES:OUT[n].write_bytes(rendered(a[n]))
 return a["summary"]

if __name__=="__main__":print(json.dumps(run(),ensure_ascii=False))
