# Checkpoint 12.3 — Containment-Aware Panel Conflict Resolution

## A. What changed

Implemented one isolated deterministic resolver over the immutable Checkpoint 12.2 `pages[].panels` universe. It builds a typed containment/conflict graph, preserves locked DETECTED controls, rejects duplicates and nested contour fragments, recognizes recursive guillotine-compatible contour tilings inside spanning whitespace candidates, and selects only existing candidate IDs/bboxes.

The official offline run selected outcome **A. CONFLICT RESOLUTION PASS — SAFE STRUCTURAL RECOVERY**. It promoted/retained 10 candidates, all matched Human panels, improved recall from 0.133333 to 0.666667 and F1 from 0.235294 to 0.80, reduced unresolved pages from 3/4 to 1/4, and introduced zero false promotions.

The first Coder handoff received Reviewer `FAIL` because the graph did not explicitly persist spanning-parent/sub-panel-set relations, the adjacent fixture duplicated the parent-split fixture, and executed frozen-input fail-closed plus behavioral GT-isolation tests were missing. This fix cycle closes only those four gaps. Selection behavior and Human metrics remain unchanged.

## B. Files changed

- Added pure resolver: `backend/app/services/panel_conflict_resolver.py`.
- Added one offline runner: `scripts/panel_conflict_resolution_12_3.py`.
- Added focused real/synthetic tests: `backend/tests/test_panel_conflict_resolver.py`.
- Added five new non-overwriting 12.3 artifacts under `benchmarks/day12/`.
- Updated this report and workflow handoff only; no production caller was added.

## C. Architecture/logic

The runner validates frozen file SHA-256 `80e46d5c6216e3d18e9686af149a0012911795a246d1323ae4bb74d516b4b735`, semantic SHA-256 `b52a3a7371b9e92542ae243db239f58d12bcefa284f90b538873102864fb051d`, schema, unique candidate IDs, bboxes, provenance, and empty GT runtime features. It writes the protocol first, builds graph/output twice without importing the database or Human GT modules, requires byte-equivalent semantic structures, then persists and fingerprints graph/output. Only afterward does it import/read Human GT for evaluation.

Graph edges record duplicate, contains, nested-internal, overlap, and compatible relations. The graph now also emits deterministic `SPANNING_PARENT_SUBPANEL_SET` relations containing a stable relation ID, parent ID, sorted member IDs, structural reason, provenance, and reused tolerance evidence. The resolver consumes these persisted graph relations and terminal parent/child decisions reference their relation IDs. The one resolver strategy still reuses only frozen `duplicate_iou=0.82` and `edge_join_fraction=0.02`. Existing DETECTED candidates are locked. Recursive guillotine tiling promotes aligned outer contour children and rejects their whitespace parent as `UNDER_SPLIT_SPANNER`. Selected outer contours suppress contained contour fragments as `NESTED_INTERNAL_FRAGMENT`. Unsupported conflict components remain `CONFLICT_NOT_RESOLVED`; no box is moved, resized, merged, split, or synthesized.

Reconciled output file SHA-256 is `7559e7560b0825fd5874306615bbe334465bd31e9c835077700448a4771da6c6`; semantic SHA-256 is `2a7cb3ce091cc60eb126949a4ba64e98d1519305e0b107f2ad8d913b999045b3`. Output froze before GT access. `gt_runtime_features` is empty and the resolver API accepts only `panels` and `config`, with no page/GT/pixel input. Graph semantic SHA-256 is `c7d58b4b58765f4947b304e2f6e7ef00c7a5700355ebd0688d32b81b36e0381d` and contains seven explicit spanning relations across the ten frozen pages.

## D. Tests

- New resolver suite: 18/18 PASS. The four new tests cover explicit deterministic spanning relations, true standalone adjacent multi-source panels, wrong-hash/mutated-semantic fail-closed input handling, and behavioral GT-change isolation through the real resolver path.
- Focused resolver/extractor/evaluator/GT/audit selection: 57/57 PASS.
- Eight embedded synthetic resolver fixtures: 8/8 PASS and excluded from Human metrics.
- Full backend suite: 392/392 PASS.
- Python compilation: PASS.
- Five-artifact JSON/hash/cross-metric reconciliation: PASS.
- Frozen prediction and Human GT before/after identity: PASS.
- Workflow validation in `REVIEW_FAILED`: PASS; `git diff --check`: PASS before final handoff.

The first reconciliation invocation was sandbox-blocked when it reached the read-only localhost PostgreSQL GT phase, after graph/output persistence. It made no model call or database write. The same fixed runner was immediately rerun with approved localhost access and completed successfully; the five artifacts now form one reconciled successful set.

## E. Benchmark if allowed

The fix reconciliation reran the same frozen-candidate resolver after the required graph evidence change. Each successful runner execution performed its second in-memory resolution solely for determinism before GT evaluation; it did not rerun extraction, inspect pixels, tune thresholds, or change selection behavior.

- Control: 2/15 matched, 13 missed, 0 false, precision 1.0, recall 0.133333, F1 0.235294, 3 unresolved pages.
- Candidate: 10/15 matched, 5 missed, 0 false, precision 1.0, recall 0.666667, F1 0.80, 1 unresolved page.
- Page 1: 0/3, unresolved; `human-1-9` remains an explicit generation limitation and no geometry was synthesized.
- Page 2: 2/2 preserved with the same candidate IDs/bboxes and no extra fragment.
- Page 15: 3/5; middle plus bottom tiling recovered, top conflict remains unresolved.
- Page 17: 5/5; two row-spanning parents were rejected and five clean candidates selected.
- Selected under-split/over-split relations: 0/0.
- Every predeclared Outcome A gate passed. The numerical gates remain `BENCHMARK_FITTED` evaluation decision gates, not resolver inputs or production calibration.
- Compared with the initial Coder result, selected IDs, rejection reason classes, per-page results, and aggregate metrics are unchanged. Artifact hashes changed only because explicit graph-relation evidence and supporting relation IDs were added.

## F. Regressions

No extractor, source pixels, production detector, Reader, Reading Order, OCR, Story, API, frontend, or database write ran. Frozen 12.2 predictions and Human GT remain unchanged. Page 2 remains exact. OCR/VLM/Ollama calls are 0/0/0; Resource Guard remained `NORMAL`.

## G. Remaining limitations

- Page 1 stays unresolved; candidate generation is missing at least one full panel and conflict resolution cannot repair that.
- Page 15 recovers only 3/5; its top conflict lacks a coherent safe subdivision under this rule.
- Results use 15 Human panels from four benchmark-observed pages. Outcome gates are benchmark-fitted and do not establish unseen-page precision.
- Safe panel selection does not validate panel ordering. Reader integration remains prohibited.
- The next justified action is separately approved unseen-page Human validation, not production integration; it was not started.

## H. Git diff summary

Checkpoint 12.3 changes are isolated to one offline resolver, one offline runner, one focused test module, five new artifacts, and workflow documentation. Historical/frozen artifacts and unrelated user changes were preserved. No commit or push was performed.
