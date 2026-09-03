# Checkpoint 12.3 — Containment-Aware Panel Conflict Resolution

## Objective

Run one controlled offline geometry-only experiment answering: **Can a deterministic containment-aware resolver recover useful full-panel structure from the already frozen Checkpoint 12.2 candidate set, without rerunning panel extraction?** Resolve candidate conflicts only; do not change candidate generation or integrate Reading Order.

## Background

Human-approved Checkpoint 12.2 established legitimate GT on Pages 1, 2, 15, and 17: 15 panels with snapshot `5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3`. Frozen prediction file SHA-256 is `80e46d5c6216e3d99bfdf894a0012911795a246d1323ae4bb74d516b4b735`; semantic SHA-256 is `b52a3a7371b9e92542ae243db239f58d12bcefa284f90b538873102864fb051d`.

The frozen control has 2/15 matched DETECTED panels, 13 misses, zero false detections, precision 1.0, recall 0.133333, F1 0.235294, and 3/4 unresolved pages. Twelve Human panels have IoU-eligible AMBIGUOUS candidates; ten are structurally clean full-panel candidates with mean IoU 0.934281. Five under-split events and seven over-split/internal-fragment relations explain most suppression. Page 2 is already correct. Page 15 contains useful contour evidence obscured by spanning and nested candidates. Page 17 has five clean candidates but row-spanning conflicts suppress them. Page 1 lacks a valid candidate for one Human panel; resolution cannot create missing geometry.

## Files or modules likely involved

- Read-only frozen input: `benchmarks/day12/panel-predictions-12.2.json`.
- Read-only freeze/protocol/evaluation evidence under `benchmarks/day12/`, especially `panel-extraction-protocol-12.2.json`, `panel-correctness-evaluation-protocol-12.2.json`, and `panel-correctness-evaluation-12.2.json`.
- One new isolated resolver, likely `backend/app/services/panel_conflict_resolver.py`.
- One new offline runner, likely `scripts/panel_conflict_resolution_12_3.py`.
- One focused test module, likely `backend/tests/test_panel_conflict_resolver.py`.
- New non-overwriting 12.3 artifacts under `benchmarks/day12/`.
- `ai-workflow/REPORT.md` and workflow state during handoff.

Inspect actual schemas before implementation. The frozen emitted `pages[].panels` collection is the candidate universe. Suppressed candidates not persisted in 12.2 cannot be recreated or inferred.

## Scope

### 1. Input gate and freeze

1. Load candidates only from the frozen prediction artifact; fail closed unless both approved hashes, all page/source identities, candidate IDs, bboxes, states, provenance, and configuration match.
2. Never call the extractor, open source pixels for runtime resolution, regenerate contours/gutters, or derive new candidate boxes.
3. Persist the 12.3 protocol before resolution. Resolve all frozen pages without loading Human GT. Persist and fingerprint graph/output artifacts before opening GT for evaluation.
4. Record `gt_runtime_features: []`, frozen input hashes, resolver code/config hash, and explicit phase ordering proving output freeze precedes Human evaluation.

### 2. Candidate conflict graph

5. Create one deterministic per-page graph whose nodes are the frozen emitted candidates. Use only existing bbox/normalized geometry, state, provenance, heuristic evidence, overlap-conflict IDs, page-edge metadata, and adjacency.
6. Emit typed, symmetric or directed edges as appropriate:
   - strict containment;
   - near-duplicate/duplicate relation using only the already frozen duplicate convention;
   - positive-area overlap/conflict;
   - compatible disjoint adjacency;
   - spanning-parent to plausible sub-panel set;
   - nested/internal-fragment relation.
7. Stable-sort nodes/edges by geometry then candidate ID. Every selection/rejection must include deterministic reason codes and supporting node/edge IDs.

### 3. One resolution strategy

8. Implement exactly one strategy: **recursive guillotine-compatible outer-contour tiling with locked safe controls**.
9. Preserve existing non-conflicting `DETECTED` candidates as locked selections. A locked candidate may only lose a frozen duplicate, never be demoted because of a new score. This protects Page 2.
10. Collapse exact/near duplicates deterministically using the frozen duplicate convention and a fixed provenance preference; record the winner and rejected IDs.
11. Treat a contour candidate strictly contained by another compatible outer contour candidate as an internal fragment, not an extra panel. Do not maximize candidate count or blindly prefer smaller rectangles.
12. Recognize a spanning whitespace candidate only when two or more outer contour-supported candidates form a coherent non-overlapping recursive guillotine subdivision inside it. Alignment/join tolerance must reuse the frozen extractor's existing scale-normalized edge/join tolerance; do not select a new real-page threshold.
13. A coherent subdivision may be a simple row/column split or a recursive tall-panel-beside-stacked layout. Its children must have mutually compatible interiors and aligned shared/outer boundaries; arbitrary scattered boxes do not qualify.
14. When such a subdivision exists, reject the whitespace-only spanning parent as `UNDER_SPLIT_SPANNER` and select the compatible outer children. Multi-source contour-plus-whitespace candidates may remain/select as atomic panels when not contradicted by a coherent subdivision.
15. Reject nested fragments as `NESTED_INTERNAL_FRAGMENT`, duplicates as `DUPLICATE`, and incompatible alternatives as `CONFLICT_NOT_RESOLVED`. Leave a component AMBIGUOUS/UNRESOLVED when structural evidence cannot choose safely.
16. The resolver may change only resolution status/selection and rejection metadata. It must never move, resize, merge, split, or synthesize a bbox.

### 4. Control and post-freeze evaluation

17. Evaluate only after the resolution output hash freezes. Use the validated 15-panel GT only through the unchanged 12.2 one-to-one evaluation protocol (bbox IoU 0.50, evaluation-only convention, DETECTED/promoted primary; unresolved and structural relations reported separately).
18. Compare candidate output directly with the frozen control: matched/missed/false, precision/recall/F1, IoUs, resolved pages, under/over-splitting, and rejection taxonomy.
19. Page 2 is a hard regression control: retain both correct panels, zero misses, zero false promotions, and the same bboxes/IoUs (0.918092 and 0.978158).
20. Evaluate Pages 15 and 17 without page-ID branches. Report exact promoted candidates and whether generic tiling resolution recovers their panels. Page 17's five clean candidates are a central target; Page 15 may remain partially unresolved where no coherent structural choice exists.
21. Report Page 1 honestly: conflict resolution cannot recover `human-1-9` because no valid full-panel candidate exists. Do not synthesize it or count this generation miss as a resolver regression.

## Success and regression criteria

These are offline 15-panel experiment gates, not production thresholds.

Primary PASS gate for Outcome A requires all of:

- at least 10/15 matched promoted/DETECTED panels;
- zero false promoted panels and precision 1.0;
- recall at least 0.666667 and F1 at least 0.80;
- unresolved pages at most 1/4;
- Page 2 remains exactly 2/2 with unchanged geometry and zero false promotion;
- Page 17 recovers 5/5 clean full-panel candidates;
- Page 15 recovers at least 3/5 without false promotion;
- no selected under-split spanner, nested internal fragment, duplicate, or bbox mutation;
- deterministic byte-equivalent semantic output across two clean runs.

The numerical outcome gates above are **BENCHMARK_FITTED evaluation decision gates** derived after observing the validated four-page evidence. They are not runtime resolver inputs and must never be presented as production calibration.

Hard regressions, regardless of aggregate recall:

- any false promoted panel;
- any Page 2 miss, bbox/status regression, or additional selected fragment;
- any Human GT/runtime feature in graph construction or selection;
- any modified/synthesized bbox or changed frozen artifact;
- any page-specific condition, threshold sweep, extractor rerun, model call, or Reading Order execution;
- Resource Guard other than `NORMAL`.

Secondary measures: total rejection reasons, structurally clean candidates retained/rejected, remaining under/over-split relations, component-level unresolved reasons, IoU distribution, and candidate-oracle ceiling. They cannot override a hard regression.

## Synthetic test plan

Keep synthetic candidate sets separate from real-page metrics and cover at minimum:

1. One large whitespace under-split candidate containing two aligned valid contour panels: select children, reject parent.
2. Nested internal contour fragment inside a legitimate outer panel: retain outer, reject fragment.
3. Exact/near duplicate candidates: stable single winner with provenance reason.
4. Two legitimate adjacent panels: retain both in deterministic order.
5. Legitimate large single panel with locked or multi-source support: retain it; do not fragment it.
6. Tall panel beside two stacked panels: recover a recursive guillotine tiling of three.
7. Scattered/ambiguous overlap without coherent subdivision: promote none and remain unresolved.
8. Page 2-like locked DETECTED pair plus internal fragment: preserve pair and reject/do not promote fragment.

Also test input hash failure, stable graph edges, no bbox mutation, stable reason codes/order, no GT-shaped resolver argument, and identical semantic hashes across candidate permutations and two runs.

## Artifacts

Create without overwriting any 12.2 artifact:

- `benchmarks/day12/panel-conflict-resolution-protocol-12.3.json`
- `benchmarks/day12/panel-conflict-graph-12.3.json`
- `benchmarks/day12/panel-conflict-resolution-output-12.3.json`
- `benchmarks/day12/panel-conflict-resolution-evaluation-12.3.json`
- `benchmarks/day12/panel-conflict-resolution-summary-12.3.json`

The graph/output artifacts must freeze before Human GT is read. Separate nondeterministic timing/resource observations from semantic hashes.

## Out of scope

- Candidate generation, pixels, gutter/contour extraction, page-edge completion, threshold tuning/sweeps, or detector rerun.
- Production detector/Reader/Reading Order/OCR/Story/API/frontend/database changes.
- Reading Order integration, scoring, repair claims, or page-specific rules.
- New Human GT, modification of existing GT, OCR/VLM/Ollama/model inference, model shopping, commit, push, or another checkpoint.
- Automatic recovery of Page 1's missing candidate.

## Safety constraints

- Human GT is evaluation-only and unavailable until output freeze; `gt_runtime_features = []` everywhere in runtime artifacts.
- Preserve Human GT snapshot `5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3` and frozen prediction bytes/hash exactly.
- No selected output may contain geometry absent from the frozen candidate universe.
- Reuse only frozen structural tolerances. Any unavoidable new numeric rule observed from the four pages must be labeled `BENCHMARK_FITTED` in protocol, code, artifacts, report, and verdict limitations.
- Run sequentially, fail closed on identity/hash/schema/resource mismatch, and never promote uncertainty merely to improve recall.
- OCR/VLM/Ollama calls = 0/0/0; Resource Guard must remain `NORMAL`.

## Acceptance criteria

- Input gate proves frozen bytes, schema, candidate universe, and zero extractor invocation.
- One documented graph and one resolver strategy implement the exact rules above without Human/runtime leakage or page IDs.
- Every candidate has a stable terminal state and reason; all selections are a subset of frozen candidate IDs with byte-identical bboxes.
- Graph/output freezes before GT access, and the freeze hash is recorded in evaluation artifacts.
- Synthetic fixtures and real evaluation are isolated; required fixtures pass.
- Control/candidate metrics reconcile per page and aggregate, including Page 2, Pages 15/17, Page 1 ceiling, under/over-splitting, ambiguity, and regression gates.
- Two clean runs produce identical graph, output, rejection metadata, ordering, and semantic hashes.
- Frozen predictions, Human GT, production state, Reader, and Reading Order remain unchanged.
- Summary chooses exactly one defined outcome and recommends no implementation beyond this checkpoint.

## Possible outcomes

- **A. CONFLICT RESOLUTION PASS — SAFE STRUCTURAL RECOVERY**: every primary PASS gate is met and no hard regression occurs.
- **B. PARTIAL RECOVERY — ADDITIONAL DETERMINISTIC STRUCTURE REQUIRED**: matched recovery improves beyond the 2-panel control and remains evidence-useful, but one or more A gates are missed without a hard safety/data/leakage violation; exact remaining structural class is named.
- **C. CONFLICT RESOLUTION DOES NOT SOLVE THE BOTTLENECK**: matched panels do not improve beyond 2/15, or apparent recall requires false promotions/Page 2 regression/unsafe ambiguity lowering. Unsafe output is rejected, not accepted as progress.
- **D. EXISTING FROZEN CANDIDATES ARE INSUFFICIENT**: before or after fail-closed oracle analysis, the immutable candidate universe lacks enough full-panel geometry to reach the minimum 10/15 ceiling, or required candidate relation/provenance fields are absent, so conflict resolution cannot answer the checkpoint question without rerunning generation.

## Required tests

- Focused resolver unit/synthetic suite covering all fixtures and invariants above.
- Frozen input/hash/schema and candidate-subset tests.
- Graph containment/overlap/compatibility symmetry/direction and stable ordering tests.
- Duplicate, nested-fragment, under-split, recursive tiling, legitimate-large-panel, ambiguity fail-closed, and locked Page 2 tests.
- GT isolation test proving identical graph/output with no GT access and after GT changes in an isolated fixture.
- Two-run artifact semantic reproducibility and cross-artifact reconciliation.
- Frozen prediction and Human GT before/after hashes; production/Reader/Reading Order unchanged.
- Relevant Checkpoint 12.2 evaluator regressions, canonical backend suite, Python compilation, JSON validation, workflow validation, and `git diff --check`.

## Benchmark permission

**ALLOWED**, exactly once for the one predeclared resolver strategy over the unchanged frozen 12.2 emitted candidate universe, plus a second identical run solely for determinism and the separate synthetic fixtures. Human GT may be loaded only after graph/output freeze for evaluation. No extractor/pixel run, configuration sweep, candidate regeneration, Reader/Reading Order run, OCR/VLM/Ollama/model inference, database mutation, production change, or unseen-page benchmark is permitted.

## Stop condition

The Coder implements the isolated resolver/runner/tests, writes the five new artifacts and `REPORT.md`, selects exactly one A/B/C/D outcome, advances `PLANNED -> IMPLEMENTED`, and stops for independent review. If hashes/schema/resource safety fail, candidate data cannot support the graph, or any forbidden inference/rerun would be required, stop honestly without changing state or artifacts beyond a failure record. Do not integrate Reader, begin another experiment, commit, or push.
