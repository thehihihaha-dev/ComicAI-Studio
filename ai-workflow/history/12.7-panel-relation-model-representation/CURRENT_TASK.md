# Checkpoint 12.7 — Panel Relation-Model Representation

## Objective

Run one deterministic, geometry-only offline experiment answering: **Can a Projection-Constraint Panel DAG (PCPDAG) resolve the seven Oracle relation-construction failures left by the accepted Checkpoint 12.6 one-pixel recursive-guillotine model, without increasing tolerance, adding page-specific behavior, or introducing any confident Reading Order inversion or regression?**

This checkpoint changes only relation representation. Checkpoint 12.6 is Human-approved and archived at `ai-workflow/history/12.6-source-normalized-panel-relation-tolerance/`; its artifacts are immutable.

## Frozen inputs and accepted control

Use exactly Pages `1, 2, 3, 4, 5, 7, 15, 17, 18, 38`, the same 50 logical regions, 36 authoritative Human panel boxes, source bytes/SHA-256/dimensions, ambiguity flags, and frozen 12.6 evidence. Verify all identities, artifact raw hashes, and internal hashes before candidate construction. Do not regenerate or reinterpret the control.

Primary control is the accepted 12.6 **Oracle 1px** candidate: `3/10` resolved/exact pages, `19/50` resolved regions/positions, `55/55` resolved pairs (`55/124` population coverage), and zero confident/cross-panel/intra-panel inversion. All 50 Oracle regions were contained/reference-agreeing; seven pages were blocked only by relation construction.

The frozen Realistic result (`6/10`, `24/50`, `47/47`, zero inversion, 18 missing-coverage regions) remains diagnostics-only. Generate and score no new Realistic candidate: incomplete panels cannot answer the representation question. Oracle fallback is forbidden.

## Exactly one representation: PCPDAG V1

Freeze one model named `EXPERIMENT_PREDECLARED_PROJECTION_CONSTRAINT_DAG_V1`. It replaces recursive guillotine construction only in the isolated candidate. No alternate model, fallback, weight, threshold sweep, or result-based selection is permitted.

### Nodes and identity

Each Oracle panel rectangle is a node. Strip Human drawing order and opaque GT identifiers; normalize `(x1,y1,x2,y2)` to `(x1/W,y1/H,x2/W,y2/H)`; validate positive, in-bounds geometry; derive stable geometry IDs from the canonical normalized rectangle plus deterministic duplicate ordinal. Input order and page/source/asset/GT IDs cannot influence relation behavior.

Build the complete panel graph before unchanged region assignment. Then project it onto **active panels** containing at least one confidently assigned logical region. Preserve empty panels in structural evidence, but they cannot output text or be the sole transitive bridge between active panels.

### Geometric evidence and precedence

Keep exactly inclusive `tau_x=1/W`, `tau_y=1/H`, implemented by exact integer/rational cross-multiplication without floating epsilon.

For distinct panels `A`, `B`:

- `A ABOVE B` is supported iff `A.y2 - B.y1 <= 1` source pixel and the reverse vertical predicate is false.
- `A RIGHT_OF B` is supported iff `B.x2 - A.x1 <= 1` source pixel and the reverse horizontal predicate is false.
- Positive gaps, equality, and at most 1px intrusion qualify; `>1px` does not.
- If vertical evidence exists in exactly one direction, upper-before-lower is the edge and dominates diagonally opposed horizontal evidence. This preserves the frozen manga hierarchy.
- Only when no vertical relation exists may a unique horizontal relation emit right-before-left precedence.
- Same-direction vertical and horizontal support produces one edge with both evidence labels.
- Neither axis supporting a unique relation means `INCOMPARABLE`; stable IDs cannot order it.
- Opposite predicates simultaneously true on one axis, or duplicate geometry without justified separation, means `CONFLICTING_AXIS_EVIDENCE` and no confidence.

Persist every unordered pair's source/normalized evidence, predicate results, selected relation/unresolved reason, direction, and active-projection status.

### Graph, transitivity, ambiguity, and failure

Direct edges come only from the predicates above. Transitive closure may prove precedence through a directed active-panel path; it cannot invent a direct relation or use an empty-panel-only bridge. Detect cycles/conflicting paths deterministically; any occurrence makes the page `UNRESOLVED`.

Run Kahn topological analysis. Stable geometry IDs may serialize evidence/ready sets, never choose semantics. If more than one active node is ready at any step, return `MULTIPLE_TOPOLOGICAL_ORDERS`. Zero/single-active-panel pages resolve trivially. Otherwise confidence requires an acyclic active graph with exactly one topological order and every active pair comparable after closure. Final region order uses that unique panel order plus the frozen intra-panel rule.

No confidence score, weighted vote, gap-ranking, area/distance constant, extra rounding tolerance, or benchmark-derived value may be introduced.

## Seven-blocker structural audit

After RUN_A/RUN_B cross the global candidate-freeze barrier, but **before Human Reading Order is opened**, derive the audit population mechanically from pages marked relation-construction `UNRESOLVED` in the frozen 12.6 Oracle control. Assert exactly seven; mismatch invalidates the run. Do not hardcode those page IDs into relation logic.

Use only source dimensions, Oracle panel geometry, frozen 12.6 guillotine traces, and frozen PCPDAG traces. Persist all applicable tags and one primary reason under this fixed precedence:

1. `INVALID_OR_CONFLICTING_GEOMETRY`;
2. `CYCLE_CONFLICT`;
3. `INCOMPARABLE_ACTIVE_PAIR`;
4. `MULTIPLE_TOPOLOGICAL_ORDERS`;
5. `GUILLOTINE_DESCENDANT_PARTITION_FAILURE`;
6. `NO_GUILLOTINE_ROOT`;
7. `OTHER_EVIDENCED_STRUCTURE` only with a machine-readable predicate/trace.

Supplemental tags (spanning-envelope interaction, tall-panel/stack interaction, partial projection alignment, offset boundary, multiple partition trees) are allowed only when defined as exact interval/envelope predicates in the frozen protocol. They are descriptive and cannot alter candidate behavior. No Human-order, correctness, expected result, or inversion label may enter this audit.

## Assignment and intra-panel freeze

Preserve 12.6 assignment exactly: unique containment; otherwise center in exactly one panel plus strictly `>0.50` region-area coverage; otherwise `AMBIGUOUS` for tied/crossing support; otherwise `UNASSIGNED`. Candidate assignment records must be byte-equivalent to 12.6 Oracle after excluding artifact-envelope fields.

Preserve the `BENCHMARK_FITTED` Day 11 intra-panel rule: normalized vertical overlap `>=0.50`, top-to-bottom tiers, right-to-left peers, and existing stable region-ID serialization. No tuning is allowed.

## GT isolation and chronology

Pre-freeze inputs are limited to source bytes/hashes/dimensions, fixed cohort, logical-region geometry, Oracle Human **panel rectangles/ambiguity only** with order/IDs stripped, opaque verified 12.6 artifact raw hashes, frozen PCPDAG protocol/taxonomy/synthetic schemas, and isolated relation/assignment code.

Pre-freeze forbidden inputs include Human Reading Order/sequences, positions, correctness, pair/inversion labels, expected outcomes, 12.6 Human-derived metrics/outcome, OCR/text/confidence, identity fields as runtime relation features, and transitive Human-derived provenance. Require recursive rejection, `human_order_derived_provenance_dependencies=[]`, and `gt_runtime_features=[]`.

Mandatory order:

1. Verify immutable inputs and opaque control hashes.
2. Freeze/hash sanitized control manifest, the single protocol, taxonomy predicates, synthetic expectations, and artifact schema without Human order/metrics.
3. Independently build RUN_A and RUN_B graphs, assignments, unresolved reasons, and sequences.
4. Require pre-freeze raw/semantic equality; freeze both and activate one global barrier.
5. Build the geometry-only seven-blocker audit before Human order.
6. Only then open/verify 12.6 post-freeze metrics and Human Reading Order; candidate builders are permanently disabled.
7. Independently evaluate/reconcile/serialize both runs.

Static inspection, loader spies, recursive forbidden-key tests, and behavioral perturbation must prove mock Human-order/metric changes cannot alter candidate/provenance bytes, graph IDs, or unresolved reasons.

## Synthetic suite

Freeze expectations before real candidates. Call the real PCPDAG plus unchanged assignment/intra-panel code for: empty/single panel; horizontal pair; vertical pair; 2x2 RTL; tall-right/stacked-left; tall-left/stacked-right; spanning top; spanning bottom; offsets; partial row alignment; partial column alignment; non-guillotine uniquely orderable; multiple guillotine trees with one order; genuine ambiguity; genuine overlap; bridge/non-transitivity including empty bridge; explicit cycle/conflict; equality at 1px on both axes; immediately `>1px`; diagonal same-direction and opposed-axis vertical dominance; incomparable active pair; multiple topological orders; input permutation/opaque-ID mutation; all frozen assignment cases; and intra-panel threshold/order boundaries.

Synthetic results remain separate from Human metrics. Incorrect fixture assumptions invalidate the run; expectations cannot be edited after results.

## Metrics and audits

Recompute per-page control/candidate/delta for resolved/unresolved and exact pages; regions over 50; positions over 50; direct/transitive panel relations; unresolved relation pairs and closure-incomparable active pairs; correct/resolved pairs and population coverage over 124; confident/cross-panel/intra-panel inversions; conflicts/cycles/multiple-topology events; taxonomy counts; assignment origins/equivalence; newly resolved/still unresolved/changed/regressed items; and every new relation's geometry/path and post-freeze correctness.

Coverage and correctness stay separate. A newly resolved page counts only with its complete logical-region population, exact final order, and zero inversion.

After freeze, audit the exact four historical Day 11 pairs (Page 15 #1/#2, Page 17, Page 38) as `REPAIRED`, `UNRESOLVED`, `UNCHANGED_INVERTED`, or `REGRESSED`; enumerate every new inversion. Audit every previously correct 12.6 Oracle page/pair. Candidate code may not branch on page ID.

## Hard safety gates

Any item forces Outcome D: one new confident inversion or previously correct regression; unsupported edge/path; forced incomparable pair; stable-ID ambiguity resolution; empty-panel bridge; suppressed cycle/conflict/non-unique order; tolerance other than inclusive 1px; undeclared predicate/constant/second model/page rule; assignment/intra-panel change; pre-freeze Human leakage or post-GT candidate construction; identity/hash/provenance mismatch; Oracle/Realistic contamination; nondeterminism/artifact inconsistency; frozen/production/Human-data mutation; or failed mandatory synthetic/mutation/isolation test. Coverage cannot compensate.

## Predeclared outcomes

Evaluate D first, then A/B/C:

- **D. UNSAFE RELATION REPRESENTATION:** any hard gate fails.
- **A. RELATION REPRESENTATION PASS:** all gates pass and all seven blockers safely resolve: `10/10` exact pages, `50/50` regions/positions, `124/124` correct/resolved population pairs, zero inversion, and no unresolved active pair/cycle/conflict.
- **B. PARTIAL RELATION RECOVERY:** all safety/non-regression gates pass but A does not; at least one blocked page becomes fully resolved/exact, or regions/pair coverage strictly rises above `19/50` or `55/124`; all new comparable pairs are correct; no tracked metric decreases; remaining blockers are classified.
- **C. RELATION REPRESENTATION INSUFFICIENT:** safety passes but neither A nor B holds; no strict useful page/region/pair gain beyond 12.6.

Identity/evidence failure stops as invalid/incomparable rather than being mislabeled performance. Do not tune after any outcome.

## Determinism and artifacts

RUN_A/RUN_B must independently parse inputs and build into isolated temporary directories, with no object/output reuse. Require stable graph/relation IDs, reasons, sequences, **10/10 raw-byte equality**, **10/10 canonical semantic equality**, valid internal hashes, and independent metric reconciliation.

Create exactly these non-overwriting files under `benchmarks/day12/`:

1. `panel-relation-model-input-audit-12.7.json`
2. `panel-relation-model-control-reference-12.7.json`
3. `panel-relation-model-protocol-12.7.json`
4. `panel-relation-model-synthetic-12.7.json`
5. `panel-relation-model-oracle-candidates-12.7.json`
6. `panel-relation-model-candidate-freeze-12.7.json`
7. `panel-relation-model-structural-audit-12.7.json`
8. `panel-relation-model-evaluation-12.7.json`
9. `panel-relation-model-historical-audit-12.7.json`
10. `panel-relation-model-summary-12.7.json`

Artifact 7 is post-freeze but pre-Human-order; 8–10 are post-freeze evaluation artifacts. RUN_B proves determinism, not another trial.

## Mutation/isolation tests

Mutate actual temporary loader inputs and require pre-candidate failure for source bytes/dimensions, logical geometry, Oracle panel geometry/ambiguity, cohort, 1px protocol, relation precedence/predicates, control bytes/internal hash, direct/nested Human-order contamination, and transitive contaminated provenance.

Also prove identity fields/input permutations do not alter geometry results; mock Human-order/control-metric perturbation leaves candidates unchanged; early GT access and post-GT candidates fail; Oracle fallback is impossible; and authoritative sources, Human GT, frozen predictions, 12.6 evidence/archive, extractor/resolver data, and production files retain before/after hashes.

## Files likely involved

- Read-only 12.6 archive/artifacts and frozen source/logical/Human-panel inputs.
- `backend/app/services/panel_aware_reading_order.py`, extended only with an explicit offline PCPDAG strategy while preserving guillotine behavior.
- New finite runner `scripts/panel_relation_model_12_7.py`.
- New focused tests `backend/tests/test_panel_relation_model_12_7.py`, plus unchanged 12.5/12.6 regressions.
- Only the ten new artifacts and later role-owned workflow report/review files.

## Scope, production isolation, and Human boundary

In scope: one PCPDAG, geometry-only blocker audit, Oracle-only candidate comparison to accepted 12.6 1px control, deterministic evidence, frozen assignment/intra-panel logic, and post-freeze scoring.

Out of scope: larger/alternate tolerance or sweep; weighted/alternate relation models; panel extractor/resolver tuning/rerun; Realistic candidate; Oracle fallback; OCR/VLM/Ollama/model inference; Human GT changes; production Reader/Reading Order integration; frozen/source/archive changes; other pipeline work; next checkpoint; commit/push.

No new Human GT is required. Existing Human panel geometry is the declared Oracle structural input; Human Reading Order is evaluation-only after global freeze. Do not modify production wiring/defaults, detector/extractor/resolver, Human GT, frozen predictions, or historical artifacts. Experimental code must require explicit offline invocation.

## Benchmark permission and required validation

**ALLOWED only** for one geometry-only 12.7 Oracle experiment: exactly independent RUN_A/RUN_B builds of PCPDAG V1 on the fixed ten-page/50-region cohort and one post-freeze evaluation per run. No Realistic candidate, alternate model/tolerance, sweep, changed retry, extractor/resolver rerun, OCR, VLM, Ollama, or model call.

Run focused PCPDAG graph/synthetic/taxonomy/mutation/chronology/isolation/assignment/artifact tests; retained 12.5/12.6 focused regressions; canonical backend unit tests; compile changed Python; validate ten JSON/internal hashes and 10/10 determinism; independently reconcile metrics/historical audit; workflow validation; and `git diff --check`. Frontend lint/build is not required because frontend is untouched.

Require Resource Guard `NORMAL` and OCR/VLM/Ollama `0/0/0`; otherwise abort before candidate generation.

## Acceptance, Reviewer, and stop condition

Reviewer must independently verify control/input identities; representation isolation; exact predicates/precedence with no hidden constants/page branches; geometry-derived post-freeze/pre-Human audit; assignment/intra-panel equivalence; edge/path support; fail-closed cycles/incomparability/non-uniqueness; `gt_runtime_features=[]`; chronology/provenance; metric/outcome arithmetic; deterministic artifacts; tests/resources; and zero production/frozen/Human mutation.

Coder stops after the one authorized offline result, artifacts, tests, and `ai-workflow/REPORT.md`, advancing only to `IMPLEMENTED`. On any safety/isolation/identity/determinism/resource failure, stop fail-closed and report it without tuning, altered rerun, GT edit, production integration, commit, push, or next-checkpoint planning.
