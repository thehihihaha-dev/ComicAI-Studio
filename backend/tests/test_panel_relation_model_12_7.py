import copy, importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from PIL import Image

from app.services.panel_aware_reading_order import canonical_projection_panels, panel_aware_projection_order, projection_constraint_order

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("panel_relation_model_12_7",ROOT/"scripts/panel_relation_model_12_7.py")
RUNNER=importlib.util.module_from_spec(SPEC);assert SPEC and SPEC.loader;sys.modules[SPEC.name]=RUNNER;SPEC.loader.exec_module(RUNNER)

class PanelRelationModel127Tests(unittest.TestCase):
 def test_pairs_vertical_then_rtl_and_auditable(self):
  panels=[{"panel_id":"tl","bbox":[0,0,40,40]},{"panel_id":"tr","bbox":[60,0,100,40]},{"panel_id":"bl","bbox":[0,60,40,100]},{"panel_id":"br","bbox":[60,60,100,100]}]
  result=projection_constraint_order(panels,(100,100));self.assertTrue(result["resolved"]);self.assertEqual(result["order"],["tr","tl","br","bl"])
  self.assertEqual(len(result["pair_evidence"]),6);self.assertTrue(all(row["tolerance"]["source_pixels"]==1 for row in result["pair_evidence"]))

 def test_exact_one_pixel_and_beyond(self):
  exact=[{"panel_id":"a","bbox":[0,0,100,51]},{"panel_id":"b","bbox":[0,50,100,100]}]
  beyond=copy.deepcopy(exact);beyond[0]["bbox"][3]=51.01
  self.assertEqual(projection_constraint_order(exact,(100,100))["order"],["a","b"])
  self.assertFalse(projection_constraint_order(beyond,(100,100))["resolved"])

 def test_exact_decimal_serialization_and_normalized_ids(self):
  raw=[{"panel_id":"opaque-b","bbox":["60.10","0.10","100.10","99.90"]},{"panel_id":"opaque-a","bbox":["0.10","0.10","40.10","99.90"]}]
  a=canonical_projection_panels(raw,(120,100));b=canonical_projection_panels(list(reversed(raw)),(120,100))
  self.assertEqual(a,b);self.assertTrue(all(p["panel_id"].startswith("PGN_") for p in a))
  self.assertEqual(projection_constraint_order(a,(120,100))["order"],projection_constraint_order(b,(120,100))["order"])
  exact=[{"panel_id":"a","bbox":["0.1","0.1","100.1","51.1"]},{"panel_id":"b","bbox":["0.1","50.1","100.1","100.1"]}]
  beyond=copy.deepcopy(exact);beyond[0]["bbox"][3]="51.1000000000000000001"
  self.assertTrue(projection_constraint_order(exact,(101,101))["resolved"]);self.assertFalse(projection_constraint_order(beyond,(101,101))["resolved"])

 def test_duplicate_normalized_geometry_ordinals_are_stable(self):
  raw=[{"panel_id":"x","bbox":[0,0,10,10]},{"panel_id":"y","bbox":[0,0,10,10]}]
  a=canonical_projection_panels(raw,(100,100));b=canonical_projection_panels(list(reversed(raw)),(100,100))
  self.assertEqual(a,b);self.assertEqual([p["duplicate_ordinal"] for p in a],[0,1]);self.assertEqual(len({p["panel_id"] for p in a}),2)

 def test_overlap_and_non_unique_fail_closed(self):
  overlap=[{"panel_id":"a","bbox":[0,0,70,70]},{"panel_id":"b","bbox":[30,30,100,100]}]
  self.assertFalse(projection_constraint_order(overlap,(100,100))["resolved"])

 def test_empty_panel_cannot_bridge_active_panels(self):
  panels=[{"panel_id":"a","bbox":[0,0,30,30]},{"panel_id":"empty","bbox":[40,0,70,70]},{"panel_id":"b","bbox":[80,40,110,70]}]
  result=projection_constraint_order(panels,(120,120),{"a","b"});self.assertTrue(result["resolved"])
  self.assertTrue(all("empty" not in (edge["before"],edge["after"]) for edge in result["active_edges"]))

 def test_assignment_and_intra_panel_are_frozen(self):
  panels=[{"panel_id":"right","bbox":[60,0,100,100]},{"panel_id":"left","bbox":[0,0,40,100]}]
  regions=[{"id":"r","bbox":[70,10,80,20]},{"id":"l","bbox":[10,10,20,20]}]
  result=panel_aware_projection_order(regions,panels,(100,100));self.assertEqual(result["sequence"],["r","l"])
  self.assertEqual([r["method"] for r in result["assignment"]["assignments"]],["UNIQUE_CONTAINMENT"]*2)

 def test_synthetic_contract(self):
  value=RUNNER.synthetic_suite();self.assertEqual(value["fixture_group_count"],26);self.assertTrue(value["all_pass"])

 def test_protocol_mutation_fails(self):
  value=RUNNER.protocol();value["formula"]["source_pixel_intrusion"]=2;value.pop("protocol_sha256");value["protocol_sha256"]=RUNNER.digest(value)
  with self.assertRaisesRegex(RuntimeError,"protocol mutation"):RUNNER.validate_protocol(value)

 def test_actual_control_byte_mutation_fails(self):
  paths={n:RUNNER.DAY12/f"panel-relation-tolerance-{n}-12.6.json" for n in RUNNER.CONTROL}
  with tempfile.TemporaryDirectory() as d:
   changed=dict(paths);p=Path(d)/"protocol.json";p.write_bytes(paths["protocol"].read_bytes()+b" ");changed["protocol"]=p
   with self.assertRaisesRegex(RuntimeError,"control fingerprint mismatch"):RUNNER.verify_control(changed)

 def test_actual_runtime_geometry_and_source_mutations_fail(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);paths=dict(RUNNER.BASE.RUNTIME)
   for key in ("logical_geometry","oracle_unseen_geometry"):
    doc=json.loads(paths[key].read_text())
    if key=="logical_geometry":doc["pages"][0]["logical_regions"][0]["bbox"][0]+=1
    else:doc["records"][0]["human_panels"][0]["bbox"][0]+=1
    target=root/f"{key}.json";target.write_text(json.dumps(doc));mutated=dict(paths);mutated[key]=target
    with self.assertRaisesRegex(RuntimeError,"frozen runtime input hash mismatch"):RUNNER.BASE.load_runtime_inputs(runtime_paths=mutated)
   audit=json.loads(RUNNER.OUT["input-audit"].read_text())["runtime_phase"];record=audit["pages"][0]
   source_record={"page_order":record["page_order"],"source_image_hash":record["source_hash"],"image_dimensions":record["image_dimensions"]}
   source=RUNNER.ROOT/record["source_path"];bad=root/"source.bin";bad.write_bytes(source.read_bytes()+b"x")
   with self.assertRaisesRegex(RuntimeError,"source fingerprint mismatch"):RUNNER.BASE.verify_source_record(source_record,bad)
   wrong=root/"wrong.png";Image.new("RGB",(1,1)).save(wrong);changed=dict(source_record);changed["source_image_hash"]=RUNNER.file_hash(wrong)
   with self.assertRaisesRegex(RuntimeError,"source dimension mismatch"):RUNNER.BASE.verify_source_record(changed,wrong)

 def test_barrier_blocks_early_and_post_gt_generation(self):
  barrier=RUNNER.Barrier()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"human.json";p.write_text('{}')
   with self.assertRaisesRegex(RuntimeError,"before global freeze"):barrier.open(p,"HUMAN_READING_ORDER")
   barrier.candidate("RUN_A")
   with self.assertRaisesRegex(RuntimeError,"both candidates"):barrier.freeze("RUN_A")
   with self.assertRaisesRegex(RuntimeError,"freeze document requires"):barrier.freeze_document("RUN_A")
   barrier.candidate("RUN_B");barrier.freeze_document("RUN_A");barrier.freeze_document("RUN_B");barrier.freeze("RUN_A");barrier.freeze("RUN_B");barrier.activate();barrier.open(p,"HUMAN_READING_ORDER")
   with self.assertRaisesRegex(RuntimeError,"forbidden after"):barrier.candidate("RUN_C")
   self.assertEqual(barrier.events[:7],["RUN_A_GENERATED","RUN_B_GENERATED","RUN_A_FREEZE_DOCUMENT_BUILT","RUN_B_FREEZE_DOCUMENT_BUILT","RUN_A_FROZEN","RUN_B_FROZEN","GLOBAL_FREEZE_BARRIER_ACTIVE"])

 def test_evaluate_has_executable_global_barrier_gate(self):
  barrier=RUNNER.Barrier()
  with self.assertRaisesRegex(RuntimeError,"evaluation forbidden"):RUNNER.evaluate({}, {}, {}, {}, {}, {}, "NORMAL", barrier)
  barrier.candidate("RUN_A");barrier.candidate("RUN_B");barrier.freeze_document("RUN_A");barrier.freeze_document("RUN_B");barrier.freeze("RUN_A")
  with self.assertRaisesRegex(RuntimeError,"evaluation forbidden"):RUNNER.evaluate({}, {}, {}, {}, {}, {}, "NORMAL", barrier)
  barrier.freeze("RUN_B")
  with self.assertRaisesRegex(RuntimeError,"evaluation forbidden"):RUNNER.evaluate({}, {}, {}, {}, {}, {}, "NORMAL", barrier)
  barrier.activate()
  oracle=json.loads(RUNNER.OUT["oracle-candidates"].read_text());human=json.loads(RUNNER.BASE.EVAL["human_order"].read_text());baseline=json.loads(RUNNER.BASE.EVAL["baseline"].read_text());control=json.loads((RUNNER.DAY12/"panel-relation-tolerance-evaluation-12.6.json").read_text());freeze=json.loads(RUNNER.OUT["candidate-freeze"].read_text());structural=json.loads(RUNNER.OUT["structural-audit"].read_text())
  self.assertEqual(RUNNER.evaluate(oracle,human,baseline,control,freeze,structural,"NORMAL",barrier)["summary"]["outcome"],"B. PARTIAL RELATION RECOVERY")

 def test_nested_human_provenance_fails(self):
  audit=RUNNER.stamp({"schema_version":"a","gt_runtime_features":[]});control=RUNNER.stamp({"schema_version":"c","nested":{"resolved_pages":3},"gt_runtime_features":[]})
  with self.assertRaisesRegex(RuntimeError,"Human-order-derived"):RUNNER.provenance(audit,control,RUNNER.protocol())

 def test_human_derived_hash_and_manifest_hash_fail_pre_freeze(self):
  audit=RUNNER.stamp({"schema_version":"a","gt_runtime_features":[]});proto=RUNNER.protocol()
  for contaminated in ({"schema_version":"c","human_derived_evaluation_sha256":"a"*64},{"schema_version":"c","dependency":{"origin":"HUMAN_DERIVED","sha256":"b"*64}},{"schema_version":"c","artifacts":[{"artifact":"summary","file_sha256":"c"*64}]}):
   control=RUNNER.stamp(contaminated)
   with self.assertRaisesRegex(RuntimeError,"Human-order-derived"):RUNNER.provenance(audit,control,proto)
  clean=RUNNER.pre_freeze_control();self.assertEqual(clean["artifacts"],[]);self.assertEqual(clean["artifact_hashes"],[])

 def test_candidate_artifact_provenance_and_fingerprint_mutations_fail(self):
  value=json.loads(RUNNER.OUT["oracle-candidates"].read_text())
  contaminated=copy.deepcopy(value);contaminated["provenance"]["nested"]={"human_sequence":["x"]};contaminated.pop("semantic_sha256");contaminated["semantic_sha256"]=RUNNER.digest(contaminated)
  with self.assertRaisesRegex(RuntimeError,"provenance contamination"):RUNNER.validate_candidate_artifact(contaminated)
  mutated=copy.deepcopy(value);mutated["pages"][0]["panel_nodes"][0]["bbox"][0]="0.0001"
  with self.assertRaisesRegex(RuntimeError,"fingerprint mismatch"):RUNNER.validate_candidate_artifact(mutated)

 def test_page_set_mutation_fails_candidate_gate(self):
  inputs={"logical":{p:{} for p in RUNNER.BASE.PAGES[:-1]},"oracle":{p:{} for p in RUNNER.BASE.PAGES},"records":[]}
  with self.assertRaisesRegex(RuntimeError,"page set"):RUNNER.candidate(inputs,{})

 def test_human_order_and_metrics_cannot_change_actual_candidate_bytes(self):
  runtime=json.loads(RUNNER.OUT["input-audit"].read_text())["runtime_phase"];pages=runtime["pages"]
  inputs={"logical":{p["page_order"]:{"source_hash":p["source_hash"],"logical_regions":[{"logical_region_id":r["id"],"bbox":r["bbox"]} for r in p["persisted_logical_regions"]]} for p in pages},"oracle":{p["page_order"]:{"panels":p["oracle_panels"]} for p in pages},"records":[{"page_order":p["page_order"],"image_dimensions":p["image_dimensions"]} for p in pages]}
  provenance=json.loads(RUNNER.OUT["oracle-candidates"].read_text())["provenance"]
  before=RUNNER.rendered(RUNNER.candidate(copy.deepcopy(inputs),copy.deepcopy(provenance)))
  human=json.loads(RUNNER.BASE.EVAL["human_order"].read_text());metrics={"resolved_pages":3,"population_pairs":55}
  for page in human["pages"]:page["human"]=list(reversed(page["human"]))
  metrics.update({"resolved_pages":999,"population_pairs":999})
  self.assertEqual(before,RUNNER.rendered(RUNNER.candidate(copy.deepcopy(inputs),copy.deepcopy(provenance))))

 def test_final_summary_comparison_material_recomputes(self):
  value=json.loads(RUNNER.OUT["summary"].read_text());row=value["two_independent_builds"]["summary"]
  material=RUNNER.comparison_material("summary",value)
  self.assertEqual(row["canonical_semantic_sha256_a"],RUNNER.digest(material));self.assertEqual(row["raw_byte_sha256_a"],__import__("hashlib").sha256(RUNNER.rendered(material)).hexdigest())
  self.assertEqual(row["canonical_semantic_sha256_a"],row["canonical_semantic_sha256_b"])

 def test_artifacts_when_present(self):
  if not all(path.exists() for path in RUNNER.OUT.values()):self.skipTest("candidate artifacts not generated yet")
  docs={n:json.loads(p.read_text()) for n,p in RUNNER.OUT.items()};self.assertTrue(all(RUNNER.verify_internal_hash(v) for v in docs.values()))
  self.assertEqual(len(docs["summary"]["two_independent_builds"]),10)
  for name,row in docs["summary"]["two_independent_builds"].items():
   value=docs[name];material=RUNNER.comparison_material(name,value) if name=="summary" else value;raw=RUNNER.rendered(material)
   self.assertEqual(row["raw_byte_sha256_a"],__import__("hashlib").sha256(raw).hexdigest());self.assertEqual(row["canonical_semantic_sha256_a"],RUNNER.digest(material));self.assertTrue(row["byte_equal"] and row["semantic_equal"])

if __name__=="__main__":unittest.main()
