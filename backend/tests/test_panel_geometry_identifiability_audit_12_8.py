import copy, hashlib, importlib.util, json, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("panel_geometry_identifiability_audit_12_8",ROOT/"scripts/panel_geometry_identifiability_audit_12_8.py")
AUDIT=importlib.util.module_from_spec(SPEC);assert SPEC and SPEC.loader;sys.modules[SPEC.name]=AUDIT;SPEC.loader.exec_module(AUDIT)


class PanelGeometryIdentifiability128Tests(unittest.TestCase):
    def test_invalidated_audit_cannot_rerun(self):
        self.assertTrue(AUDIT.AUDIT_INVALIDATED);self.assertEqual(AUDIT.INVALIDATION_REASON,"PHASE_A_RULE_FAMILY_CHANGED_AFTER_HUMAN_ORDER_EXPOSURE")
        with self.assertRaisesRegex(RuntimeError,"invalidated"):AUDIT.run()

    def test_frozen_cohort_and_protocol(self):
        self.assertEqual(AUDIT.COHORT,[1,2,3,15,18,38])
        protocol=AUDIT.protocol();self.assertEqual(protocol["tolerance"],{"tau_x":"1/W","tau_y":"1/H","inclusive_source_pixels":1})
        self.assertTrue(protocol["no_ordering_output"]);self.assertEqual(protocol["gt_runtime_features"],[])

    def test_frozen_inputs_and_internal_hashes(self):
        docs=AUDIT.frozen_docs();self.assertEqual(set(docs),set(AUDIT.FROZEN))
        self.assertTrue(all(AUDIT.verify_internal_hash(v) for v in docs.values()))

    def test_actual_frozen_artifact_mutation_fails(self):
        paths={n:AUDIT.DAY12/f"panel-relation-model-{n}-12.7.json" for n in AUDIT.FROZEN}
        with tempfile.TemporaryDirectory() as d:
            changed=dict(paths);p=Path(d)/"candidate.json";p.write_bytes(paths["oracle-candidates"].read_bytes()+b" ");changed["oracle-candidates"]=p
            with self.assertRaisesRegex(RuntimeError,"artifact mismatch"):AUDIT.frozen_docs(changed)

    def test_artifact_set_mutation_fails(self):
        with self.assertRaisesRegex(RuntimeError,"artifact set"):AUDIT.frozen_docs({})

    def test_barrier_fail_closed(self):
        barrier=AUDIT.Barrier()
        with self.assertRaisesRegex(RuntimeError,"before global"):barrier.open_human(AUDIT.BASE.EVAL["human_order"])
        barrier.generated_audit("RUN_A")
        with self.assertRaisesRegex(RuntimeError,"both Phase A"):barrier.freeze("RUN_A")
        barrier.generated_audit("RUN_B");barrier.freeze("RUN_A")
        with self.assertRaisesRegex(RuntimeError,"global freeze barrier"):barrier.open_human(AUDIT.BASE.EVAL["human_order"])
        barrier.freeze("RUN_B");barrier.activate();barrier.open_human(AUDIT.BASE.EVAL["human_order"])
        with self.assertRaisesRegex(RuntimeError,"forbidden"):barrier.generated_audit("RUN_C")

    def test_chronology(self):
        barrier=AUDIT.Barrier();barrier.generated_audit("RUN_A");barrier.generated_audit("RUN_B");barrier.freeze("RUN_A");barrier.freeze("RUN_B");barrier.activate();barrier.open_human(AUDIT.BASE.EVAL["human_order"])
        self.assertEqual(barrier.events,["INPUTS_VERIFIED","RUN_A_AUDIT_GENERATED","RUN_B_AUDIT_GENERATED","RUN_A_FROZEN","RUN_B_FROZEN","GLOBAL_FREEZE_BARRIER_ACTIVE","HUMAN_ORDER_ACCESS_ALLOWED"])

    def test_phase_a_enumerates_all_six_pages(self):
        barrier=AUDIT.Barrier();phase=AUDIT.build_phase_a(barrier,"RUN_A",AUDIT.frozen_docs())
        self.assertEqual([p["page_order"] for p in phase["pages"]],AUDIT.COHORT);self.assertGreater(phase["ready_set_count"],0)
        self.assertTrue(all(p["ready_set_count"] for p in phase["pages"]));self.assertEqual(phase["ordering_edges_emitted"],[])

    def test_phase_a_has_only_frozen_classification_inputs(self):
        barrier=AUDIT.Barrier();phase=AUDIT.build_phase_a(barrier,"RUN_A",AUDIT.frozen_docs())
        text=json.dumps(phase).lower();self.assertNotIn("expected_panel_post_freeze",text);self.assertNotIn("matches_human",text)
        self.assertEqual(phase["gt_runtime_features"],[]);self.assertEqual(phase["human_order_derived_provenance_dependencies"],[])

    def test_phase_a_provenance_and_frozen_mutations_fail(self):
        phase=AUDIT.build_phase_a(AUDIT.Barrier(),"RUN_A",AUDIT.frozen_docs());AUDIT.validate_phase_a(phase)
        contaminated=copy.deepcopy(phase);contaminated["nested"]={"human_order":["x"]};contaminated.pop("semantic_sha256");contaminated["semantic_sha256"]=AUDIT.digest(contaminated)
        with self.assertRaisesRegex(RuntimeError,"provenance contamination"):AUDIT.validate_phase_a(contaminated)
        mutated=copy.deepcopy(phase);mutated["pages"][0]["ready_set_count"]+=1
        with self.assertRaisesRegex(RuntimeError,"artifact mismatch"):AUDIT.validate_phase_a(mutated)

    def test_human_perturbation_cannot_change_phase_a(self):
        docs=AUDIT.frozen_docs();a=AUDIT.build_phase_a(AUDIT.Barrier(),"RUN_A",docs)
        human=json.loads(AUDIT.BASE.EVAL["human_order"].read_text())
        for page in human["pages"]: page["human"]=list(reversed(page["human"]))
        original=AUDIT.BASE.EVAL["human_order"]
        with tempfile.TemporaryDirectory() as d:
            changed=Path(d)/"reversed-human.json";changed.write_text(json.dumps(human));AUDIT.BASE.EVAL["human_order"]=changed
            try:b=AUDIT.build_phase_a(AUDIT.Barrier(),"RUN_A",copy.deepcopy(docs))
            finally:AUDIT.BASE.EVAL["human_order"]=original
        self.assertEqual(AUDIT.rendered(a),AUDIT.rendered(b));self.assertEqual(AUDIT.digest(a),AUDIT.digest(b))
        self.assertEqual(hashlib.sha256(AUDIT.rendered(a)).hexdigest(),hashlib.sha256(AUDIT.rendered(b)).hexdigest())

    def test_source_and_cohort_mutations_fail(self):
        docs=AUDIT.frozen_docs();bad=copy.deepcopy(docs);bad["input-audit"]["runtime_phase"]["pages"][0]["source_hash"]="0"*64
        with self.assertRaisesRegex(RuntimeError,"source identity"):AUDIT.input_audit(bad)
        missing=copy.deepcopy(docs);missing["input-audit"]["runtime_phase"]["pages"]=[p for p in missing["input-audit"]["runtime_phase"]["pages"] if p["page_order"]!=38]
        with self.assertRaisesRegex(RuntimeError,"cohort mismatch"):AUDIT.input_audit(missing)

    def test_panel_bbox_mutation_changes_phase_a_and_is_caught_by_frozen_gate(self):
        paths={n:AUDIT.DAY12/f"panel-relation-model-{n}-12.7.json" for n in AUDIT.FROZEN}
        with tempfile.TemporaryDirectory() as d:
            value=json.loads(paths["oracle-candidates"].read_text());value["pages"][0]["panel_nodes"][0]["bbox"][0]="1"
            p=Path(d)/"candidate.json";p.write_text(json.dumps(value));changed=dict(paths);changed["oracle-candidates"]=p
            with self.assertRaisesRegex(RuntimeError,"artifact mismatch"):AUDIT.frozen_docs(changed)

    def test_synthetic_real_audit_path(self):
        value=AUDIT.synthetic_suite();self.assertEqual(value["fixture_count"],31);self.assertTrue(value["all_pass"])
        inherited=[r for r in value["results"] if "signature_assertions_pass" in r]
        self.assertTrue(all(r["actual_audit_path"]=="ready_sets+complete_signature" for r in inherited))
        self.assertTrue(all(r["signature_assertions_pass"] for r in inherited))

    def test_complete_signature_vocabulary(self):
        docs=AUDIT.frozen_docs();phase=AUDIT.build_phase_a(AUDIT.Barrier(),"RUN_A",docs)
        pair=next(iter(phase["pages"][0]["ready_sets"][0]["signatures"].values()))["pair_predicates"][0]
        self.assertTrue(set(("containment","intersection","gaps","overlaps","shared_boundaries","row_column_membership","spanning","adjacency","relative_alignment")).issubset(pair))

    def test_dimensions_tolerance_assignment_and_transitive_provenance_fail(self):
        paths={n:AUDIT.DAY12/f"panel-relation-model-{n}-12.7.json" for n in AUDIT.FROZEN}
        with tempfile.TemporaryDirectory() as d:
            for name,mutate in (("input-audit",lambda v:v["runtime_phase"]["pages"][0]["image_dimensions"].__setitem__(0,1)),
                                ("protocol",lambda v:v["formula"].__setitem__("source_pixel_intrusion",2)),
                                ("protocol",lambda v:v["assignment"].__setitem__(0,"MUTATED"))):
                value=json.loads(paths[name].read_text());mutate(value);p=Path(d)/(name+str(len(list(Path(d).iterdir())))+".json");p.write_text(json.dumps(value));changed=dict(paths);changed[name]=p
                with self.assertRaisesRegex(RuntimeError,"artifact mismatch"):AUDIT.frozen_docs(changed)
        phase=AUDIT.build_phase_a(AUDIT.Barrier(),"RUN_A",AUDIT.frozen_docs());phase["nested"]={"dependency":{"human_order_sha256":"a"*64}};phase.pop("semantic_sha256");phase["semantic_sha256"]=AUDIT.digest(phase)
        with self.assertRaisesRegex(RuntimeError,"provenance contamination"):AUDIT.validate_phase_a(phase)

    def test_evaluation_requires_active_barrier(self):
        with self.assertRaisesRegex(RuntimeError,"Phase B forbidden"):AUDIT.evaluate(AUDIT.Barrier(),{}, {}, {})

    def test_artifacts_recompute_when_present(self):
        if not all(p.exists() for p in AUDIT.OUT.values()):self.skipTest("audit not executed")
        docs={n:json.loads(p.read_text()) for n,p in AUDIT.OUT.items()};rows=docs["summary"]["two_independent_runs"]
        self.assertTrue(all(AUDIT.verify_internal_hash(v) for v in docs.values()))
        self.assertEqual(len(rows),len(AUDIT.NAMES))
        for name,row in rows.items():
            material=AUDIT.comparison_material(name,docs[name]) if name=="summary" else docs[name]
            self.assertEqual(hashlib.sha256(AUDIT.rendered(material)).hexdigest(),row["raw_byte_sha256_a"])
            self.assertEqual(AUDIT.digest(material),row["canonical_semantic_sha256_a"])


if __name__=="__main__":unittest.main()
