# Checkpoint 12.4 — Unseen Panel Structure Generalization Validation

## Objective

Run the smallest rigorous two-phase validation answering: **Does the frozen Checkpoint 12.2 panel extractor plus the Human-approved Checkpoint 12.3 conflict resolver retain high precision and useful structural recovery on manga pages whose panel correctness was never used for calibration or evaluation?** This is validation, not tuning. Freeze predictions before any new Human Panel GT exists; stop for Human annotation; evaluate only after a separate completeness and trust gate.

## Background and fixed reference

Checkpoint 12.3 is Human-approved and archived at `ai-workflow/history/12.3-containment-aware-panel-conflict-resolution/`. Its reference result on Pages 1, 2, 15, and 17 is 10/15 matched, five missed, zero false promotions, precision 1.0, recall 0.666667, F1 0.800000, and 1/4 unresolved pages. Those four pages are excluded from 12.4.

The available frozen ten-page source/prediction universe contains exactly six remaining pages: **3, 4, 5, 7, 18, and 38**. Select all six, in ascending `page_order`, before correctness is known. This exhaustive complement rule prevents success-based cherry-picking. These pages had no Human Panel GT and were not part of 12.2/12.3 correctness metrics or resolver threshold decisions. Their historical prediction artifacts may be used only as identity/comparability evidence; the 12.4 run must be independently frozen before the new Human cohort is created or opened.

## Frozen unseen cohort

| Page | Asset ID | Source SHA-256 | Dimensions |
|---|---|---|---|
| 3 | `58ac011e-7a3a-44ba-a8c5-ba7977a78b95` | `ecc4798a1fd62c36af8e401b80a0ef67e36dfafbb69ac809f1f41e88f6b9676d` | 900×1280 |
| 4 | `dab0676a-07e3-4195-b20c-511f57e3ddc6` | `95cb90cb0c70a19b2f40401799a0ae5648e177fdde66690a580c80a831a824b4` | 900×1280 |
| 5 | `69f9acdd-e51f-4be2-90dd-cbc7e5882aa7` | `8a44656d3dc2eef04c0bb3c9daf758373a2b0d12cc1669c63937ebdb4c333067` | 900×1280 |
| 7 | `b2b89e05-fb47-4b90-877c-6ced851bc7de` | `05f78f1eba0068e0c787185864a7764a3c8d20c265c94344ee897e26a7dc8309` | 900×1280 |
| 18 | `23ab72f6-0910-49d0-a167-3bd170ea3b23` | `8cac650842de985ede0be45715eed9ebb48f842e7a5def7bc5203b8ceff2c240` | 900×1280 |
| 38 | `522c50f5-5934-40be-9cc2-f452deeeff35` | `969152a0288a5680d74205f90226a0164523fc82fb66cdc145eba0f25ab07e30` | 900×1280 |

The cohort must collectively exercise ordinary neighboring panels, horizontal/vertical divisions, spanning-row opportunities, tall-beside-stacked structure, nested/internal-contour opportunities, page-edge structure, and at least one difficult/irregular or unresolved page. Record a source-only structural rationale before prediction execution. Do not use selected/resolved counts, IoUs, or correctness to replace pages.

## Files or modules likely involved

- Read-only approved extractor/resolver: `backend/app/services/deterministic_panel_extractor.py`, `backend/app/services/panel_conflict_resolver.py`.
- Read-only frozen protocols/source audit and new non-overwriting 12.4 artifacts under `benchmarks/day12/`.
- One isolated 12.4 pre-Human runner under `scripts/`.
- Cohort-safe Panel GT model/service/router under `backend/app/` and the existing `frontend/app/panel-ground-truth/` UI/helpers/tests.
- `ai-workflow/REPORT.md`, review/fix handoffs, and focused tests.

Preserve unrelated work. Prefer cohort-scoped queries over destructive replacement. The four authoritative 12.2 GT rows must remain byte/semantic unchanged and excluded from the 12.4 queue.

## Scope and phase ordering

### Phase 0 — immutable selection and input gate

1. Persist `panel-unseen-selection-12.4.json` first with the exact six rows above, exhaustive-complement rationale, source paths, actual byte hashes, dimensions, source-audit hash, exclusions `[1,2,15,17]`, and source-only structural coverage.
2. Fail closed unless all sources and identities match, approved extractor/resolver code and configuration hashes match archived evidence, Resource Guard is `NORMAL`, and no 12.4 Human GT rows exist.
3. Freeze outcome thresholds, matching rules, failure taxonomy, and phase order before prediction. Never update them from new GT.

### Phase 1 — prediction before Human GT

4. Run the approved frozen extractor sequentially on only Pages 3, 4, 5, 7, 18, and 38 using the 12.2 configuration, plus one identical in-memory pass solely for determinism. Do not overwrite 12.2 artifacts.
5. Require raw-candidate semantics to equal the corresponding six-page subset of frozen 12.2 `pages[].panels`. Any mismatch stops as incomparable; never select the better-looking run.
6. Run the approved 12.3 resolver/config on those raw candidates, plus one identical in-memory pass. Freeze graphs, spanning relations, selections, reasons, unresolved states, ordering, bbox-subset proof, semantic hashes, and code/config hashes.
7. Persist/fingerprint graph/output before importing, querying, creating, or opening 12.4 Human GT. Record `gt_runtime_features: []`, phase order, zero GT-derived fields, and zero rule changes.
8. No selected bbox may be moved, resized, merged, split, or synthesized.

### Phase 1B — isolated Human queue and UI

9. Only after a valid prediction-freeze manifest exists, create cohort `12.4-unseen` containing exactly the six pages, initially `0 VERIFIED / 6 PENDING`.
10. Preserve all four 12.2 GT rows, boxes, states, revisions, flags, hashes, and snapshot `5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3`. Never delete, reset, reuse, or reinterpret them.
11. The cohort API may return only source identity, image URL/dimensions, persisted Human boxes/state/revision, and resource metadata. It must never return candidates, predictions, resolver selections, unresolved/ambiguity predictions, reasons, confidence, IoUs, predicted counts, or expected panel counts. Test serialized keys and network payloads.
12. Reuse the corrected object-contain coordinate mapping. Before opening UI, rerun letterbox exclusion, pointer→source, source→display, roundtrip, resize invariance, reload persistence, bounds, and outside-image rejection tests.
13. Show exactly: **“Vẽ một khung quanh từng ô truyện thật. Nếu ranh giới panel thực sự không rõ, đánh dấu Mơ hồ.”** Drawing order is not Reading Order. Request no OCR, bubbles, dialogue, or ordering.
14. After freeze, isolation, tests, and Reviewer verification pass, stop with `HUMAN TESTING REQUIRED`, exact URL, `0 VERIFIED / 6 PENDING`, and prediction hashes. Do not evaluate or reveal predictions.

### Mandatory Human boundary

15. Human manually annotates all six pages. Agents must not auto-fill, transform predictions into GT, infer ambiguity, or derive Human boxes from screenshots/heuristics.
16. Do not continue automatically. A later explicit Human message must report completion and authorize post-Human validation. This is an annotation gate, not final checkpoint approval.

### Phase 2 — post-Human trust gate and evaluation

17. Require exactly six cohort rows, `6 VERIFIED / 0 PENDING`, unchanged identities/hashes, positive in-bounds source geometry, reload persistence, coordinate roundtrip/resize invariance, semantic full-panel sanity, and persisted Human-provided ambiguity. Any failure returns outcome D and stops for correction without evaluation.
18. Freeze a new Human-GT snapshot; confirm old GT snapshot unchanged and predictions independently predate GT.
19. Only then evaluate the already-frozen selections with unchanged one-to-one IoU `0.50`. Never rerun extraction/resolution after GT opens.
20. Report total/per-page Human count, selected, matched, missed, false, precision, recall, F1, unresolved count/rate, IoUs, under/over-splitting, ambiguity behavior, raw DETECTED control versus resolved output, and comparison with 12.3.
21. Audit every false promotion individually with page/candidate/relation/reason/evidence. Never hide false confidence in aggregates.
22. Give every failure one primary class: `MISSING_CANDIDATE_GENERATION`, `CONFLICT_RESOLUTION`, `UNDER_SPLITTING`, `OVER_SPLITTING`, `CONTOUR_NOISE`, `BORDERLESS_PANEL`, `PAGE_EDGE_STRUCTURE`, `IRREGULAR_GEOMETRY`, `AMBIGUITY_POLICY`, or `OTHER_EVIDENCE_SUPPORTED`. Do not tune during analysis.

## Predeclared outcome rules

These validation gates are frozen before GT and are not production thresholds.

### A. UNSEEN GENERALIZATION PASS — READY FOR PANEL ORDERING VALIDATION

Valid complete GT plus: zero false and precision `1.0`; recall ≥ `0.60`; F1 ≥ `0.75`; unresolved pages ≤ `2/6`; no selected duplicate/internal fragment/spanning under-split; resolver matches not below raw DETECTED control; no identity, geometry, determinism, leakage, resource, or production regression. This only justifies a separately planned ordering validation.

### B. HIGH-PRECISION PARTIAL GENERALIZATION — PANEL RECOVERY NEEDS MORE WORK

Valid complete GT, no hard safety/data regression, precision ≥ `0.90`, at most one false promotion, recall ≥ `0.35`, and resolver matches not below raw DETECTED control, but at least one A recall/F1/unresolved/zero-false gate fails. Name dominant failure classes and do not proceed to ordering.

### C. GENERALIZATION FAIL — STRUCTURAL APPROACH REQUIRES REVISION

Valid GT but neither A nor B holds, including precision < `0.90`, at least two false promotions, recall < `0.35`, regression below raw control, systematic unsafe splitting, leakage, bbox mutation, nondeterminism, identity mismatch, non-`NORMAL` resource state, or forbidden execution.

### D. UNSEEN HUMAN GT INSUFFICIENT / INVALID

Correctness is not evaluable because the cohort is incomplete/pending/source-incompatible, geometry/persistence/semantic sanity or ambiguity provenance fails, GT was exposed before prediction freeze, or source identity cannot be proved. Do not fabricate/correct GT or convert D into A/B/C.

## Artifacts

Create without overwriting prior files:

- `benchmarks/day12/panel-unseen-selection-12.4.json`
- `benchmarks/day12/panel-unseen-protocol-12.4.json`
- `benchmarks/day12/panel-unseen-raw-candidates-12.4.json`
- `benchmarks/day12/panel-unseen-conflict-graph-12.4.json`
- `benchmarks/day12/panel-unseen-resolution-output-12.4.json`
- `benchmarks/day12/panel-unseen-prediction-freeze-12.4.json`
- post-Human only: `panel-unseen-human-gt-validation-12.4.json`, `panel-unseen-evaluation-12.4.json`, `panel-unseen-summary-12.4.json`.

Synthetic evidence stays separate from unseen metrics. Prediction artifacts must never be exposed through Human UI/API.

## Out of scope

- Any extractor/resolver rule or threshold change, page replacement, or Pages 1/2/15/17.
- Fake/prediction-assisted GT, OCR/bubble/dialogue annotation, Reading Order annotation/evaluation/integration, Reader, Story, production behavior, or model shopping.
- OCR/VLM/Ollama, unrelated benchmarks, commit, push, or another checkpoint.

## Safety constraints

- Sequential, fail-closed execution; `gt_runtime_features = []` everywhere in prediction/runtime.
- Human prediction visibility is zero; test backend serialization and frontend rendering/network contracts.
- Preserve every 12.2/12.3 artifact and old GT. New files are cohort-scoped and non-overwriting.
- OCR/VLM/Ollama `0/0/0`; Resource Guard `NORMAL`.
- Any unavoidable database change must be additive/migration-backed; prefer strict cohort queries without schema change.

## Acceptance criteria

- Exact six-page correctness-blind selection and identities freeze first.
- Extraction exactly reproduces frozen 12.2 subset; approved resolver is deterministic and unchanged.
- Prediction artifacts demonstrably freeze before any 12.4 GT access/creation.
- Selections are byte-identical candidate subsets with auditable relations/reasons.
- UI/API exposes exactly six sources and zero prediction-derived information; old GT is unchanged.
- Coordinate/persistence safety passes, then mandatory stop occurs at `0 VERIFIED / 6 PENDING`.
- Post-Human work starts only after explicit authorization and valid `6/6` GT, uses frozen predictions, audits all failures, and mechanically applies predeclared outcomes.
- Required tests, reconciliation, resources, workflow validation, and `git diff --check` pass.

## Required tests

- Selection exclusion/exhaustiveness/order; identity/hash/dimension; missing/mutated source; no-preexisting-12.4-GT fail closed.
- Extractor code/config gates, two-run determinism, exact 12.2 subset equivalence.
- Resolver code/config gates; two-run/permutation determinism; relation/reason/order stability; bbox subset/no mutation.
- Phase-order persistence-before-GT and behavioral GT-isolation tests.
- Cohort isolation proving legacy snapshot unchanged; six-page API and prediction-field absence tests.
- Coordinate mapping, letterbox, bounds, outside drag, reload, persistence, and resize tests.
- Post-Human only: completeness/identity/snapshot/geometry/ambiguity/semantic sanity/evaluator/reconciliation/false-audit/taxonomy/outcome tests.
- Relevant panel regressions, frontend lint/typecheck/build, canonical backend, compile, JSON, workflow validation, `git diff --check`.

## Benchmark permission

**ALLOWED with exact phase limits.** Pre-Human: frozen extractor on exactly Pages 3, 4, 5, 7, 18, 38 once plus one identical in-memory determinism pass; approved resolver once plus one identical pass; isolated unit/synthetic tests. No sweep, alternate strategy, model, OCR, Reading Order, replacement, or other page. Post-Human: evaluate already-frozen output once plus one reconciliation that never reruns extraction/resolution. If predictions were exposed to the annotating Human outside the hidden UI contract, stop for a new Architect decision.

## Stop condition and workflow boundary

Coder implements only Phase 0/1/1B first, writes pre-Human artifacts/tests/report, and advances `PLANNED -> IMPLEMENTED`. Reviewer verifies freeze ordering, immutability, cohort/UI/GT isolation, coordinate safety, and tests. On PASS, stop at `HUMAN TESTING REQUIRED`; do not evaluate.

After Human explicitly reports all six pages complete and authorizes continuation, the same checkpoint may execute only Phase 2 under a fresh workflow handoff and must receive another independent Reviewer review before final Human approval. Do not archive 12.4 at the intermediate annotation boundary. Do not start Reading Order or another checkpoint.
