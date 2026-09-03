# Checkpoint 12.6 — Review Failure Fix #2

## A. What changed

Removed the final Human-derived provenance dependency without changing tolerance or ordering behavior. The pre-freeze control integrity manifest now contains only checkpoint/schema identity, artifact path/identity, approved raw SHA-256, deferred internal-verification state, and empty GT/provenance dependency declarations. Human-derived control metrics exist only in legally opened post-freeze evaluation artifacts.

The clean rerun mechanically produces **B. TOLERANCE HELPS BUT REMAINS INCOMPLETE**.

## B. Files changed

- `scripts/panel_relation_tolerance_12_6.py`: removed pre-freeze control metrics, sanitized the pre-freeze input audit, added recursive provenance-closure validation, and persisted explicit empty Human-derived dependency evidence.
- `backend/tests/test_panel_relation_tolerance_12_6.py`: added direct manifest leakage, nested/transitive dependency rejection, and Human-metric perturbation isolation tests.
- Regenerated only the same nine 12.6 artifacts with the unchanged one-pixel formula.
- Updated workflow report/state only. Geometry/relation/assignment code was not changed by Fix #2.

## C. Architecture/logic

`verify_control()` still reads historical 12.5 files only as raw bytes before freeze. Its returned manifest no longer contains resolved pages, regions, pairs, coverage, correctness, inversions, Human sequences, outcomes, or hashes of metric objects. It records only opaque approved artifact identities and raw fingerprints. The manifest internal fingerprint is `ace5f6c1cf6655f74cb498ecb310c1e505332644b105308c5f2d282cd306d06d`.

The 12.6 pre-freeze input audit also removes `expected_post_freeze_metric_region_count`; its runtime semantic hash is recomputed after sanitization. Human panel geometry remains allowed only for Oracle, while Human Reading Order remains unavailable.

`build_provenance()` receives exactly three dependency objects: sanitized non-order input audit, opaque raw-byte control integrity manifest, and frozen tolerance protocol. It recursively walks their actual dict/list graph and rejects forbidden Human sequence, metric, pair, position, inversion, correctness, outcome, or post-freeze population keys. Candidate provenance persists the three dependency fingerprints, `human_order_derived_provenance_dependencies=[]`, `gt_runtime_features=[]`, and a closure row marking every dependency `human_order_derived=false`.

A deliberately nested `{evaluation: {resolved_pages: 2}}` dependency fails closed. With the clean manifest, closure succeeds. Mutating mock post-freeze control metrics from valid values to `999` cannot alter provenance or candidate bytes for RUN_A/RUN_B Oracle/Realistic because those metrics are not accepted by the pre-freeze builder.

Post-freeze `load_post_freeze_evidence()` remains behind the corrected global barrier. It opens and internally verifies all 12.5 artifacts only after both runs freeze, then derives control metrics for evaluation. Chronology remains:

`RUN_A_FROZEN → RUN_B_FROZEN → GLOBAL_FREEZE_BARRIER_ACTIVE → POST_FREEZE_OPEN`.

## D. Tests

- Actual generated pre-freeze manifest forbidden-field inspection: PASS.
- Nested/transitive contaminated provenance rejection: PASS.
- Clean provenance closure and empty Human-derived dependency list: PASS.
- Human-metric perturbation across four real relation candidate paths: byte-identical PASS.
- Pre-freeze parser spy, global barrier, early GT/evaluation rejection, and post-GT candidate rejection: PASS.
- Existing actual source/logical/Realistic/page-set/contamination/control/config mutation suite: PASS.
- Synthetic real-service fixtures: 20/20 PASS.
- Focused 12.6 plus retained 12.5: 38/38 PASS.
- Canonical backend: 444/444 PASS.
- Nine JSON/internal hashes: PASS.
- RUN_A/RUN_B raw-byte equality: 9/9 PASS.
- RUN_A/RUN_B semantic equality: 9/9 PASS.
- Independent closure, chronology, metrics, Day 11 audit, and 12.5 byte reconciliation: PASS.
- Python compile, workflow validation, and `git diff --check`: PASS after final handoff.
- Frontend was not touched.

## E. Benchmark if allowed

Clean candidate generation used only frozen `τx=1/W`, `τy=1/H`, exactly one source pixel inclusive. No alternate value, sweep, page rule, relation change, or assignment change occurred.

### Oracle

- Candidate: 3/10 resolved/exact pages; 19/50 resolved regions/positions; 55/55 resolved pairs and `55/124` population coverage; zero confident/cross-panel/intra-panel inversion.
- Control post-freeze: 2/10 pages, 11/50 regions, 27/27 pairs and `27/124` coverage, zero inversion.
- Delta: `+1` page, `+8` regions, `+28` pairs, `-1` unresolved page, `0` inversion.
- Page 5 is newly exact. Seven pages remain relation-construction blocked; assignments are 50 contained/reference-agreeing with no ambiguity/unassigned region.

### Realistic

- Candidate/control: 6/10 pages, 24/50 regions/positions, 47/47 pairs and `47/124` population coverage, zero inversion.
- All deltas are zero.
- Pages 1/3/5/15 retain `4/3/8/3` missing-panel-coverage unassigned regions, total 18; no Oracle fallback or assignment/intra-panel failure is introduced.

Day 11: Page 15 inversion 1 and 2 remain unresolved in both tracks; Page 17 is repaired in both; Page 38 is Oracle unresolved and Realistic repaired. New confident inversions and previously correct regressions are zero.

Outcome A fails because Realistic does not improve. Outcome B applies because Oracle safely increases exact page/region/pair coverage with no metric decrease or hard-gate violation.

## F. Regressions

The isolation fix does not change relation graphs, assignments, panel orders, final sequences, tolerance boundaries, synthetic behavior, or metrics. All eight historical 12.5 bytes remain exact. Production Reader/Reading Order, extractor, resolver, Human GT, frozen predictions, source assets, and archives are unchanged.

Resource Guard is `NORMAL`. OCR/VLM/Ollama calls are `0/0/0`.

## G. Remaining limitations

Seven Oracle relation-representation/construction blockers remain. Realistic separately lacks selected-panel coverage for 18 regions. No new Human GT is required. The proposed future target remains relation-model representation for the seven Oracle blockers, not a larger tolerance; it was not started.

## H. Git diff summary

Fix #2 is confined to offline provenance construction/audit, focused tests, regenerated nine 12.6 artifacts, and workflow documents/state. No production or frozen historical artifact was modified. No commit or push was performed.
