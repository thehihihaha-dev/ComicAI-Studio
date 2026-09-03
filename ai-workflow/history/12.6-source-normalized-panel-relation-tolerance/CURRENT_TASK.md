# Checkpoint 12.6 — Source-Normalized Panel Relation Tolerance

## Objective and checkpoint question

Run the smallest deterministic offline experiment answering: **Can exactly one predeclared, source-normalized panel-separation tolerance increase useful panel-order relation coverage over the frozen zero-tolerance Checkpoint 12.5 control without introducing any new confident Reading Order inversion?**

This checkpoint tests relation construction only. It does not redesign panel extraction, panel resolution, text-to-panel assignment, intra-panel ordering, or production Reader behavior.

Checkpoint 12.5 is Human-approved and archived at `ai-workflow/history/12.5-panel-aware-reading-order-validation/`. Its artifacts under `benchmarks/day12/panel-order-*12.5.json` are immutable control evidence and must not be overwritten.

## Frozen control and cohort

The cohort remains exactly Pages `1, 2, 3, 4, 5, 7, 15, 17, 18, 38`, with the same 50 Human-ordered logical regions, 36 authoritative Human panel boxes, source identities/hashes/dimensions, and frozen Realistic selected panels used by 12.5. It is a frozen regression/evidence cohort, not an unseen cohort.

The authoritative zero-tolerance control is the validated 12.5 artifact set. Before candidate construction, verify every 12.5 control artifact byte hash and internal semantic hash against a new immutable control-reference manifest. Do not regenerate, mutate, or reinterpret the control after scoring.

Frozen control observations:

| Track | Resolved pages | Resolved regions | Resolved pairs | Confident inversions |
|---|---:|---:|---:|---:|
| Oracle | 2/10 | 11/50 | 27/27 (27/124 population coverage) | 0 |
| Realistic | 6/10 | 24/50 | 47/47 (47/124 population coverage) | 0 |

Historical inversion control: Page 15 inversion 1 and 2 are unresolved in both tracks; Page 17 is repaired in both; Page 38 is unresolved in Oracle and repaired in Realistic.

The observed overlap values from Pages 1/2/3/7/15/38 are diagnostic evidence only. They may be reported after freeze but must never determine, revise, or select the tolerance.

## Exactly one frozen tolerance model

Convert every source-coordinate panel rectangle `(x1, y1, x2, y2)` on a source image of width `W` and height `H` to normalized edges:

`u1=x1/W, v1=y1/H, u2=x2/W, v2=y2/H`.

Freeze the axis-specific tolerance as:

`τx = 1/W` and `τy = 1/H`.

Thus the only tolerated intrusion is exactly one source-image pixel on the tested split axis. Boundary equality is accepted: `intrusion_axis <= τaxis`. Use exact decimal/rational comparison derived from serialized source coordinates and integer source dimensions so equality does not depend on an undeclared floating-point epsilon.

For an existing candidate left/right group partition `(L,R)`, define normalized horizontal intrusion:

`Ix(L,R) = max(0, max(u2 for L) - min(u1 for R))`.

The horizontal split is geometrically separated only when `Ix <= τx`. For an existing upper/lower partition `(U,D)`, define:

`Iy(U,D) = max(0, max(v2 for U) - min(v1 for D))`.

The vertical split is geometrically separated only when `Iy <= τy`.

Tolerance modifies only this clean-separation predicate inside the existing recursive guillotine relation construction. Existing partition membership, projection/span checks, incompatible-relation handling, and graph validation remain required. It must not expand boxes, move edges, assign a panel to both sides, create direct pairwise ordering outside an otherwise valid partition, or override a spanning/genuinely overlapping/conflicting layout.

The constant `1` is justified by raster edge quantization: two independently persisted representations of the same image boundary can differ by one source pixel because source pixels have finite support and edge coordinates are serialized independently. It is not selected from benchmark overlap magnitudes. There is no alternate constant, scale factor, minimum/maximum clamp, threshold sweep, or post-score selection.

Label the model `EXPERIMENT_PREDECLARED_SOURCE_PIXEL_QUANTIZATION_V1`. Persist and hash its formula, constant, comparison inclusivity, numeric representation, and scope before Human Reading Order can be accessed.

## Relation semantics frozen except separation tolerance

Retain the 12.5 hierarchy and service path:

1. `PAGE → PANELS` from the named track adapter.
2. `PANELS → PANEL RELATION DAG/ORDER` using recursive geometry partitions.
3. `PANEL → LOGICAL REGIONS` using the frozen assignment policy.
4. `LOGICAL REGIONS → INTRA-PANEL ORDER` using the frozen Day 11 local rule.

Preserve upper-before-lower and manga right-before-left, deterministic stable geometry IDs, explicit DAG edges, transitive closure, cycle/conflict evidence, and the unique-topological-order requirement. Cycles, incompatible equally supported relations, multiple materially distinct text-bearing orders, or unsupported partitions return `UNRESOLVED`; no stable-ID tie-break may convert semantic ambiguity into a confident order.

No other predicate, relation strength, fallback, ordering rule, or assignment threshold may change. The zero-tolerance mode must remain available solely to reproduce/verify the frozen control, not as a second candidate.

## Assignment and intra-panel policy freeze

Do not tune assignment. Preserve exactly:

1. `ASSIGNED_CONTAINED` through unique containment using the existing rounding behavior.
2. `ASSIGNED_INTERSECTION` only when containment fails, the center lies in exactly one panel, and that panel covers strictly more than `0.50` of region area.
3. `AMBIGUOUS` for tied/multiple strongest support or boundary crossing without unique majority.
4. `UNASSIGNED` when no panel has justified support.

Oracle and Realistic use identical assignment code/config. Preserve the Day 11 normalized vertical-overlap `>=0.50`, top-to-bottom tiers, right-to-left peers, and stable region-ID fallback inside a confidently assigned panel, labeled `BENCHMARK_FITTED`. Report relation-construction blockage separately from missing selected-panel coverage and genuine assignment ambiguity.

## Allowed and forbidden inputs

### Pre-freeze allowed inputs

- Actual source bytes plus frozen source SHA-256 and dimensions.
- The exact 12.5 cohort and persisted logical-region geometry.
- Oracle track: authoritative Human **panel rectangles and ambiguity flags only**, with drawing order/opaque identifiers stripped and geometry IDs regenerated.
- Realistic track: only approved frozen selected resolver panels from 12.3 and 12.4.
- Frozen 12.5 control candidate/protocol/freeze artifacts and their expected hashes for read-only control verification.
- The predeclared tolerance protocol and real relation/assignment service code.

### Pre-freeze forbidden inputs

- Human Reading Order, ordered region sequences, inversion labels, evaluation metrics, expected page outcomes, and 12.0 failure labels.
- Page IDs, source hashes, GT IDs, asset IDs, OCR text/confidence, region text, or known-page flags as runtime relation features.
- Oracle geometry/fallback in the Realistic track.
- Diagnostic overlap magnitudes as configuration inputs.
- Any second tolerance, adaptive tolerance, sweep, optimization, or result-based selection.

Require recursive structural contamination rejection and `gt_runtime_features = []` in every runtime/candidate/freeze artifact.

## Tracks

### Track O — Oracle geometry

Use only authoritative Human panel geometry with ambiguity flags, stripped of Human drawing order and opaque IDs. Apply the one-pixel normalized separation model to relation construction. Human final region order remains inaccessible until both candidate runs and freeze are complete.

### Track R — Realistic frozen geometry

Use only the already-approved frozen 12.3/12.4 selected resolver panels. Do not rerun extractor/resolver, supplement missing panels, borrow Oracle boxes, promote unresolved candidates, or reinterpret source states. Apply the identical tolerance and assignment code. Missing panel coverage must stay `UNASSIGNED`/`UNRESOLVED` rather than becoming a fabricated order.

## Mandatory chronology and GT isolation

Enforce this executable boundary:

1. Load and verify frozen non-order input bytes, source identities/dimensions, cohort, snapshots, and 12.5 control hashes.
2. Materialize the immutable zero-tolerance control-reference manifest from verified 12.5 artifacts without opening Human Reading Order.
3. Materialize and hash the single tolerance protocol/configuration.
4. Generate Oracle and Realistic relation graphs, assignments, panel orders, unresolved reasons, and final candidate sequences for independent RUN_A and RUN_B.
5. Require candidate and pre-freeze artifact raw-byte/semantic equality and freeze their fingerprints.
6. Only after both freezes exist, open the existing Human Reading Order and frozen 12.5 post-freeze evaluation evidence.
7. Evaluate candidate versus Human order and compare candidate metrics with the frozen control.
8. Independently build evaluation/summary artifacts twice and require raw-byte/semantic equality.

Static chronology inspection, forbidden-key tests, and behavioral Human-order perturbation must prove that modifying a mock Human order cannot change either track's candidate bytes or semantic hashes.

## Metrics and reconciliation

For control and candidate, report Oracle and Realistic independently. Recompute from per-page records rather than copying summary fields:

- resolved/unresolved pages and exact resolved pages;
- resolved regions over 50 and per-page IDs;
- resolved correct/total pairs plus population pair coverage over 124;
- exact positions over 50;
- confident inversions, separated into cross-panel and intra-panel;
- assignment-origin, missing-panel-coverage, and relation-construction unresolved causes;
- panels/relations newly resolved, still unresolved, or changed;
- every candidate relation enabled specifically by tolerance, including normalized/source intrusion and supporting partition;
- regressions on every previously correct resolved control page;
- new confident inversions relative to both Human order and frozen control.

Coverage and correctness must never be merged. Missing/unresolved output is coverage loss, not silently correct output. A newly resolved page counts as useful only when its complete predicted region population matches the page's Human population and its post-freeze order is exact with zero inversion.

## Hard safety and regression gates

Any of the following forces Outcome D regardless of aggregate coverage:

- at least one new confident inversion versus Human order or the 12.5 control;
- a previously exact resolved control page becomes confidently non-exact;
- an unsupported confident relation, genuine-overlap relation, forced assignment, Oracle fallback, cycle/conflict suppression, or non-unique order is emitted;
- assignment/intra-panel behavior changes;
- Human-order leakage before freeze, candidate nondeterminism, input/hash mismatch, artifact/hash mismatch, or production/frozen-data mutation;
- any required synthetic safety case fails.

No coverage gain may compensate for a hard-gate failure.

## Day 11 inversion audit

After freeze only, audit exactly four historical inversions: Page 15 inversion 1, Page 15 inversion 2, Page 17, and Page 38. For each, preserve the exact region pair and report for Oracle and Realistic both control and candidate status as `REPAIRED`, `UNRESOLVED`, `UNCHANGED_INVERTED`, or `REGRESSED`. Also enumerate every new inversion on all ten pages. No page-specific behavior may exist in candidate code.

## Synthetic contract

All fixtures must call the real relation implementation with normalized source dimensions and the single frozen tolerance:

1. exact clean horizontal separation;
2. exact clean vertical separation;
3. horizontal intrusion strictly below one normalized source pixel accepted;
4. vertical intrusion strictly below one normalized source pixel accepted;
5. intrusion exactly equal to one normalized source pixel accepted deterministically;
6. intrusion immediately beyond one normalized source pixel rejected/unresolved;
7. manga right-before-left;
8. upper-before-lower;
9. 2×2 RTL grid;
10. tall-right beside stacked-left;
11. tall-left beside stacked-right;
12. offset panels;
13. top and bottom spanning-panel cases;
14. genuine overlapping panels rejected;
15. ambiguous relation returns unresolved;
16. explicit cycle/conflict returns unresolved;
17. bridge/non-transitivity does not invent a relation;
18. permutation/stable-ID determinism;
19. tolerance cannot create a relation outside an otherwise valid guillotine partition;
20. unchanged assignment fixtures for contained, majority, boundary tie, ambiguous, and unassigned regions.

Synthetic expectations are geometry-derived and frozen before real candidate/Human scoring. Synthetic output never counts as Human accuracy.

## Fail-closed and integrity tests

Reuse and retain all corrected 12.5 protections. Tests must mutate actual temporary copies consumed by the runtime loader and separately prove failure before candidate generation for:

- source bytes/fingerprint and actual source dimensions;
- logical-region bbox JSON;
- frozen Realistic panel JSON;
- page cohort membership;
- Human-order contamination at any nesting level;
- 12.5 control artifact bytes/internal semantic hash;
- tolerance protocol/config hash, including any attempt to change the constant or introduce a second candidate.

Authoritative source assets, Human GT, frozen predictions, 12.5 artifacts, extractor/resolver inputs, and historical workflow archives remain read-only. Verify their before/after hashes.

## Determinism protocol

RUN_A and RUN_B must be independent builder executions from newly parsed copies of the same frozen inputs. Neither may copy or reuse the other's produced objects/files. Each independently generates the complete deterministic 12.6 artifact set in isolated temporary output directories. Compare every corresponding artifact as raw bytes and by a canonical semantic hash derived from content.

The required non-overwriting artifacts are:

1. `panel-relation-tolerance-input-audit-12.6.json`;
2. `panel-relation-tolerance-control-reference-12.6.json`;
3. `panel-relation-tolerance-protocol-12.6.json`;
4. `panel-relation-tolerance-synthetic-12.6.json`;
5. `panel-relation-tolerance-oracle-candidates-12.6.json`;
6. `panel-relation-tolerance-realistic-candidates-12.6.json`;
7. `panel-relation-tolerance-candidate-freeze-12.6.json`;
8. post-freeze `panel-relation-tolerance-evaluation-12.6.json`;
9. post-freeze `panel-relation-tolerance-summary-12.6.json`.

Require 9/9 raw-byte equality, 9/9 semantic-hash equality, valid internal hashes, and independent metric reconciliation. Candidate generation occurs exactly once per independent determinism run; RUN_B is a determinism proof, not a second parameter trial.

## Predeclared outcomes

Evaluate hard gates first, then choose exactly one outcome mechanically:

### D. TOLERANCE CAUSES UNSAFE ORDERING

Any hard safety/regression gate fails, including one new confident inversion, one confidently regressed previously exact page, or one unsupported confident relation. Stop; no tuning or production integration.

### A. SAFE TOLERANCE IMPROVEMENT

All safety, identity, isolation, synthetic, and determinism gates pass; assignments and intra-panel behavior are byte-equivalent to control wherever panel inputs are identical; **both** Oracle and Realistic strictly increase useful fully resolved exact pages above `2/10` and `6/10` respectively; neither track decreases resolved regions, population pair coverage, exact positions, or any previously resolved correctness measure; all newly resolved pages are exact; and candidate confident inversions remain zero.

### B. TOLERANCE HELPS BUT REMAINS INCOMPLETE

All A safety/non-regression conditions pass, A's two-track page-improvement condition is not met, but at least one track has a strict safe increase in at least one of: useful fully resolved exact pages, resolved regions, or population pair coverage; no tracked coverage/correctness metric decreases; every newly confident comparable pair is correct; and relation or missing-panel/assignment blockage remains explicitly reported.

### C. TOLERANCE DOES NOT SOLVE THE BOTTLENECK

All safety gates pass, but neither A nor B holds: there is no strict useful coverage increase, or any apparent structural change fails to produce additional fully supported correct regions/pairs/pages. Record the failure without changing the formula or running another tolerance.

Outcome D has precedence over A/B/C. A has precedence over B, and B over C. Existing Human evidence is sufficient; an identity/evidence failure stops fail-closed and is reported as an invalid/incomparable run rather than being mislabeled as tolerance performance.

## Files/modules likely involved

- Read-only 12.5 archive and eight `benchmarks/day12/panel-order-*12.5.json` control artifacts.
- Read-only source images, logical geometry, Human panel geometry adapters, and frozen 12.3/12.4 Realistic selected-panel artifacts already named by 12.5.
- The isolated offline service `backend/app/services/panel_aware_reading_order.py`, changed only to accept the frozen relation-separation configuration while preserving zero-tolerance behavior.
- One new finite offline runner such as `scripts/panel_relation_tolerance_12_6.py`.
- One focused test module such as `backend/tests/test_panel_relation_tolerance_12_6.py`, plus unchanged 12.5 regression tests.
- Only the nine new non-overwriting 12.6 JSON artifacts under `benchmarks/day12/` and workflow report/review files during later roles.

## Scope and out of scope

In scope: one source-normalized one-pixel separation predicate, relation-only candidate generation on the fixed ten pages, frozen control comparison, synthetic validation, two-track post-freeze evaluation, deterministic evidence, and fail-closed tests.

Out of scope: any tolerance sweep; alternate formula; value tuning; page/source/GT-specific constants; panel bbox expansion/mutation; assignment tuning; extractor/resolver rerun or fallback; OCR/VLM/Ollama; Human GT creation/editing; production Reader/Reading Order integration; Story/Dialogue/OCR changes; new pages; deployment; next-checkpoint planning; commit or push.

## Acceptance criteria

- The one-pixel axis-normalized formula/config is persisted and hashed before Human order access and cannot be changed after scoring.
- All frozen 12.5 control and non-order input identities reconcile fail-closed without mutation.
- Oracle/Realistic remain isolated and use identical generic relation/assignment code except the named geometry-source adapter.
- Tolerance changes only the clean-separation decision and every enabled relation has complete geometric evidence.
- Assignment, intra-panel rule, DAG/conflict/unique-order behavior, and GT isolation remain unchanged.
- All synthetic, mutation, contamination, integrity, chronology, and deterministic-build tests pass.
- Candidate versus control metrics, all ten pages, four historical inversions, newly resolved relations/pages, regressions, and A/B/C/D selection reconcile from underlying records.
- Resource Guard is NORMAL; OCR/VLM/Ollama calls are `0/0/0`; production and frozen evidence hashes are unchanged.

## Required validation

- Focused 12.6 relation-tolerance and retained 12.5 regression tests.
- Canonical backend suite using `backend/.venv/bin/python -m unittest discover -s backend/tests -t backend`.
- Python compile for touched Python files.
- Nine JSON schema/internal-hash and 9/9 independent byte/semantic comparisons.
- Independent metric, inversion, assignment-isolation, control-hash, and before/after authoritative-input reconciliation.
- Workflow validation and `git diff --check`.
- Frontend lint/build only if frontend is touched; frontend changes are not authorized by this plan.

## Benchmark permission

**ALLOWED with exact limits.** On only the frozen ten-page cohort: verify/load the frozen 12.5 zero-tolerance control; generate exactly one candidate using `EXPERIMENT_PREDECLARED_SOURCE_PIXEL_QUANTIZATION_V1` for Oracle and Realistic; repeat the identical build once as RUN_B solely for deterministic comparison; run the finite frozen synthetic suite; then, after candidate freeze, open existing Human order once for evaluation plus one independent deterministic evaluation rebuild. No threshold sweep, alternative formula, extractor/resolver/OCR/model run, new page, or production integration is allowed.

## Resources, Human boundary, and stop condition

Resource Guard must be `NORMAL`. OCR/VLM/Ollama calls must remain `0/0/0`; no model service may be started or invoked.

No new Human GT or annotation is required. If frozen identity/reference evidence is missing or mismatched, stop before candidate execution and request only correction of the named provenance defect; never reconstruct or fabricate GT.

Coder stops after one finite experiment, artifacts, report, required validation, and transition to `IMPLEMENTED` for Independent Reviewer. Reviewer PASS stops at `AWAITING_HUMAN_APPROVAL`. No result authorizes production integration, another tolerance, the next checkpoint, commit, or push.
