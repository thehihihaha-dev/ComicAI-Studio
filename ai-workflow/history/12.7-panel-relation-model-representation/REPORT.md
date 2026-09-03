# Checkpoint 12.7 — Review Failure Fix #2

## A. What changed

Corrected only the remaining pre-freeze provenance, freeze-document chronology, evaluation gate, and raw/semantic determinism evidence. PCPDAG behavior is unchanged. Clean regeneration still produces **B. PARTIAL RELATION RECOVERY**.

## B. Files changed

- `scripts/panel_relation_model_12_7.py`: sanitized pre-freeze control identity, post-freeze full control verification, freeze-document state, evaluation gate, and recomputable determinism records.
- `backend/tests/test_panel_relation_model_12_7.py`: Human-derived hash contamination, freeze/evaluation state-machine, and on-disk raw/semantic recomputation tests.
- Regenerated only the same ten `panel-relation-model-*12.7.json` artifacts.
- Workflow report/state only. Relation service code was not changed by Fix #2.

## C. Architecture/logic

Pre-freeze candidate provenance now depends on a sanitized `control-reference.v2` containing only the declared checkpoint/control identity and explicit empty fields:

- `artifacts=[]`
- `artifact_hashes=[]`
- `human_derived_pre_freeze_dependencies=[]`
- `human_order_derived_provenance_dependencies=[]`
- `gt_runtime_features=[]`

It contains no 12.6 file fingerprint, manifest fingerprint, metric, outcome, or transitive Human-derived hash. Full raw-byte and internal-hash verification of all nine accepted 12.6 artifacts runs only after the global barrier. The post-freeze evaluation records that verified artifact set and its reference semantic hash.

`prebuild()` now returns only input audit, sanitized control identity, protocol, synthetic evidence, and Oracle candidate. It cannot construct a freeze document. Both candidates are generated and compared first; then the state machine records RUN_A/RUN_B freeze-document construction, freezes A/B, and activates the global barrier.

Enforced chronology is:

`RUN_A_GENERATED -> RUN_B_GENERATED -> RUN_A_FREEZE_DOCUMENT_BUILT -> RUN_B_FREEZE_DOCUMENT_BUILT -> RUN_A_FROZEN -> RUN_B_FROZEN -> GLOBAL_FREEZE_BARRIER_ACTIVE -> structural audit -> post-freeze control verification -> Human order -> EVALUATION_ALLOWED`.

`evaluate()` now receives the barrier and calls `assert_evaluation()` itself before reading its supplied evidence. Calls before both freezes or before activation fail closed. Human/control loaders also reject access before activation. Candidate generation remains forbidden after freeze begins or GT access.

Every determinism record now persists artifact name/path/schema, raw-byte convention, RUN_A/RUN_B raw SHA-256, RUN_A/RUN_B canonical semantic SHA-256, and equality flags. For nine non-summary artifacts the raw digest covers final rendered persisted bytes and semantic digest covers the final canonical object. Summary uses the declared non-self-referential material excluding only its self-hash and determinism envelope for both rendered/raw and canonical/semantic hashes; final enveloped RUN_A/RUN_B summary bytes are separately asserted identical.

## D. Tests

- Fixed 12.7 plus retained focused suites: **44/44 PASS**.
- Canonical backend: **464/464 PASS**.
- Synthetic real PCPDAG: **26/26 PASS**.
- Pre-freeze Human-derived evaluation/summary hash, manifest hash, and nested/transitive provenance contamination: rejected.
- Clean pre-freeze reference proven to contain zero artifact hashes/dependencies.
- Freeze document before both generations, early freeze, early Human access, incomplete-freeze evaluation, pre-activation evaluation, and post-GT candidate generation: rejected.
- Valid post-barrier direct evaluation: PASS.
- Actual runtime/source/panel/control/candidate mutation and Human-order/metric perturbation coverage retained: PASS.
- Normalized rational IDs, exact arithmetic, duplicate ordinals, and real PCPDAG cycle retained: PASS.
- All nine 12.6 raw hashes and internal hashes verified after barrier: PASS.
- Ten 12.7 JSON/internal stamps: PASS.
- On-disk recomputation of all declared raw/semantic hashes: **10/10 PASS**.
- Independent RUN_A/RUN_B raw and semantic equality: **10/10 PASS**.
- Python compile, workflow validation, and `git diff --check`: PASS after handoff.

## E. Benchmark if allowed

Corrected clean RUN_A/RUN_B preserves the frozen behavioral control:

- 12.6 Oracle control: `3/10`, `19/50`, `55/124`, zero inversion.
- 12.7 candidate: `4/10` exact pages, `21/50` regions/positions, `56/56` correct resolved pairs and `56/124` population coverage, zero inversion.
- Delta: `+1` page, `+2` regions, `+1` pair, `+0` inversion.
- Page 7 remains newly exact; Pages 4, 5, 17 remain exact.
- Pages 1, 2, 3, 15, 18, 38 remain acyclic and fail closed with `MULTIPLE_TOPOLOGICAL_ORDERS`.
- Evaluation assignment: 50 contained/reference-agreeing, 0 ambiguous, 0 unassigned.
- Historical audit: Page 15 #1/#2 unresolved, Page 17 repaired, Page 38 unresolved.
- Hard failures: none. Outcome: **B. PARTIAL RELATION RECOVERY**.

## F. Regressions

No relation type, edge predicate, tolerance, threshold, tie-break, assignment rule, intra-panel behavior, page/source branch, or Realistic candidate was added. Production Reader/Reading Order, extractor, resolver, Human GT, frozen predictions, sources, frontend, and archived 12.6 evidence remain unchanged.

## G. Remaining limitations

Six pages still lack unique geometry-only precedence under PCPDAG V1. Fix #2 changes only evidence/isolation mechanics and provides no justification for stronger confidence or production integration. No new Human GT is required.

Resource Guard NORMAL. OCR/VLM/Ollama `0/0/0`.

## H. Git diff summary

Fix #2 is confined to the offline runner, focused tests, regeneration of the same ten artifacts, and workflow handoff. No commit or push occurred.
