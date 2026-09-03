# Checkpoint 12.8 — Frozen Panel-Geometry Identifiability Audit

## Objective and Day 12 exit question

Run one deterministic, offline audit answering: **Given only already-frozen panel geometry and PCPDAG-compatible geometric information, is correct precedence for the six remaining `MULTIPLE_TOPOLOGICAL_ORDERS` pages deterministically identifiable, or has geometry alone reached an information/representation limit?**

This checkpoint is an audit, not an ordering implementation or heuristic search. It is explicitly intended to determine whether Day 12 can stop geometry-based ordering work. Outcome C closes Day 12 geometry work with the known limitation. Outcome A or B may justify at most one later, separately Human-approved, narrowly defined implementation experiment; 12.8 must not create it automatically.

## Background and fixed cohort

Human-approved Checkpoint 12.7 produced Outcome B: control `3/10`, `19/50`, `55/124`, zero inversion; PCPDAG V1 `4/10`, `21/50`, `56/124`, zero inversion. Page 7 became exact. The only audit targets are Pages **1, 2, 3, 15, 18, and 38**, each acyclic with at least two valid topological orders and a fail-closed `MULTIPLE_TOPOLOGICAL_ORDERS` result.

The cohort is frozen before execution. Resolved pages from the accepted ten-page cohort may be used only as contradiction and regression controls. They are not optimization targets, and no page may be added after results are observed.

## Frozen inputs and identity gate

Before Phase A, verify and freeze:

- the six source page identities, bytes/SHA-256 values, and dimensions;
- authoritative Human panel rectangles and ambiguity flags with drawing order and opaque GT identities stripped;
- normalized panel geometry and the frozen logical-region geometry required to reproduce active-panel graph state;
- accepted 12.7 PCPDAG V1 protocol, graph/candidate, freeze, structural-audit, and deterministic artifact identities;
- inclusive `tau_x=1/W`, `tau_y=1/H` configuration and frozen assignment/intra-panel configuration;
- applicable accepted 12.6/12.7 historical controls, supplied to Phase A only through a sanitized non-Human-derived identity declaration.

Do not regenerate panel extraction, panel resolution, OCR, VLM, model Reading Order output, Human GT, frozen predictions, or any accepted artifact. Full Human-derived control/evaluation manifests and their hashes are forbidden before the Phase A global freeze barrier and may be verified only afterward.

## Two-phase isolation architecture

### Phase A — geometry identifiability analysis

Human Reading Order, Human sequences, correctness/inversion labels, evaluation outcomes, page-specific expected order, and any direct or transitive hash/manifest derived from them must be inaccessible. Require recursive provenance validation, loader enforcement, `human_order_derived_provenance_dependencies=[]`, and `gt_runtime_features=[]`.

Phase A may read only frozen source dimensions/identity, stripped panel and logical geometry, normalized coordinates, deterministic geometric relations, PCPDAG graph structure/evidence, containment/intersection geometry, and sanitized protocol/control identities. RUN_A and RUN_B must independently load inputs and build all geometry-audit outputs in isolated temporary directories. All Phase A artifacts must be byte/semantically equal, freeze documents must be built only after both runs finish, both runs must freeze, and one global barrier must activate before any Human-derived input is opened. Candidate/audit builders become permanently disabled once freezing begins.

### Phase B — post-freeze evaluation

Only after the active global barrier with both runs frozen may the runner open and verify Human Reading Order and full accepted control evidence. Phase B labels each already-frozen ambiguity/signature result, checks Human precedence and contradictions, reconciles outcomes, and cannot mutate/rebuild Phase A output. Evaluation functions must themselves assert the barrier rather than relying on orchestration comments.

## Ready-set and geometry-signature audit

Mechanically enumerate every Kahn/topological state in each target page where two or more active nodes are simultaneously ready. Persist the ready set, already-emitted nodes, active ancestors/descendants, direct/transitive PCPDAG evidence, and every allowable per-node and pairwise signature.

The frozen signature vocabulary may contain only exact/source-normalized values derivable without preference: normalized bbox and width/height; centers; horizontal/vertical projection intervals, gaps, and overlaps; containment/intersection; shared geometric boundaries; deterministically derived row/column membership; spanning relationships; adjacency and relative alignment; source-edge contact; graph ancestors/descendants; and existing `ABOVE`/`RIGHT_OF` predicates. Define every field and equivalence rule in the protocol before real target analysis. Stable IDs may serialize evidence but may not resolve precedence.

No preference or new PCPDAG edge is emitted in Phase A. Each ready-set is an observation over alternatives, not a forced order.

## Identifiability, equivalence, and contradiction method

Predeclare a finite set of relation/signature predicates from the vocabulary before target results and Human order are visible. The audit asks whether **one** deterministic, page-independent, source-normalized distinction can separate an ambiguous precedence choice. An admissible distinction must use only frozen geometry, contain no fitted constant/page ID/source hash/content signal, preserve existing PCPDAG relations, and produce no contradiction on any applicable frozen control structure.

For each ambiguity, compare alternatives under the complete allowed representation. If alternatives have identical relevant signatures, or the same signature requires different Human precedence across the frozen post-barrier dataset, label `GEOMETRY_NOT_IDENTIFIABLE`. Absence of a qualifying distinction without a proof of equivalence is `INSUFFICIENT_EVIDENCE`. A distinction contradicted by any control is `CONTRADICTED_BY_CONTROL`. A distinction is `IDENTIFIABLE_BY_EXISTING_GEOMETRY` only when it was frozen before Human access, uniquely separates the choice, agrees post-freeze, and passes every applicable control.

Every Phase A ready-set must receive exactly one of those four labels during Phase B. No result may create an edge, candidate order, fallback, or production rule.

## No-threshold and no-search rule

Tolerance remains exactly inclusive `tau_x=1/W`, `tau_y=1/H`. No tolerance sweep, optimized/fitted constant, weighting, ranking score, gap/area threshold, result-driven predicate edit, alternate representation, page exception, or post-Human signature design is allowed. The run is invalid rather than retryable if a frozen predicate assumption is wrong.

## Predeclared checkpoint outcomes

Evaluate D first, then A/B/C:

- **D. AUDIT INVALID / SAFETY FAILURE:** any GT/provenance leakage, Human access before global freeze, post-hoc fitting, input/archive mutation, unsupported inference, invalid chronology, nondeterminism, model call, or artifact inconsistency.
- **A. GEOMETRY IDENTIFIABILITY FOUND:** one frozen, deterministic, page-independent existing-geometry distinction resolves all relevant remaining ambiguities post-freeze without contradiction or safety regression. This only justifies considering a future implementation checkpoint.
- **B. PARTIAL GEOMETRY IDENTIFIABILITY:** at least one but not all relevant ambiguities is safely identifiable by one admissible frozen distinction, with all other findings honestly classified and no contradiction/safety failure.
- **C. GEOMETRY REPRESENTATION LIMIT CONFIRMED:** the allowed frozen representation proves the remaining required precedence is not uniquely identifiable from geometry alone. Recommend closing Day 12 geometry work and moving forward with the known limitation.

Do not convert `INSUFFICIENT_EVIDENCE` alone into Outcome C; C requires an explicit equivalence/cross-case non-identifiability demonstration. Do not implement any discovered distinction in 12.8.

## Synthetic contract

Freeze expectations before real inputs and exercise the actual audit implementation for: uniquely identifiable precedence; geometrically equivalent alternatives; symmetric layout; 2x2 RTL; spanning row; tall-beside-stacked; offset panels; ambiguous ready set; bridge/non-transitivity; real cycle; contradiction control; exact inclusive 1px boundary; and immediately greater-than-1px overlap. Synthetic evidence is separate from Human evaluation and cannot be edited after results.

## Determinism and artifacts

RUN_A and RUN_B independently parse inputs and construct Phase A outputs with no object/output reuse. Both complete before either freeze document is built. Require raw-byte and canonical-semantic equality for every deterministic artifact, stable ready-set/signature IDs, valid internal hashes, and independently recomputable final persisted hashes. For any self-referential summary envelope, predeclare its exact excluded material and separately verify final byte equality.

Plan a small non-overwriting 12.8 artifact family under `benchmarks/day12/` covering: sanitized input/control identity, frozen protocol/signature vocabulary/outcomes, synthetic results, RUN_A/RUN_B Phase A ready-set/signature audit, candidate-freeze/global chronology evidence, post-freeze identifiability/contradiction evaluation, and final summary/determinism envelope. The Coder must enumerate exact filenames and schemas before execution and may not add artifacts after seeing results.

## Mutation and isolation tests

Use actual temporary loader inputs to require fail-closed behavior for source identity/bytes/dimensions mutation; panel bbox/ambiguity mutation; six-page cohort mutation; PCPDAG artifact/internal hash mutation; tolerance/assignment/protocol mutation; direct, nested, and transitive Human-derived provenance; Human-order hash/manifest contamination; early Human/control evaluation access; incomplete/ inactive barrier evaluation; and mutation or regeneration after freeze.

Prove that input permutation and opaque identity mutation do not change geometry semantics. Perturb actual Human Reading Order and Human-derived metrics and prove every Phase A byte/hash, ready set, signature, equivalence class, and frozen classification input remains unchanged. Validate that post-freeze labeling changes only evaluation evidence and cannot alter Phase A.

## Files or modules likely involved

- Read-only accepted evidence in `benchmarks/day12/` and `ai-workflow/history/12.6-source-normalized-panel-relation-tolerance/` plus `ai-workflow/history/12.7-panel-relation-model-representation/`.
- Read-only frozen service behavior in `backend/app/services/panel_aware_reading_order.py`; do not change production/default paths.
- One new finite offline runner, likely `scripts/panel_geometry_identifiability_audit_12_8.py`.
- One focused test module, likely `backend/tests/test_panel_geometry_identifiability_audit_12_8.py`, plus retained 12.6/12.7 regression suites.
- Only the predeclared new 12.8 JSON artifacts and role-owned workflow documents.

## Scope and production isolation

In scope: the six-page frozen ready-set enumeration; a predeclared geometry-signature/equivalence representation; contradiction checks on frozen controls; strict Phase A/Phase B isolation; deterministic evidence; and one A/B/C/D audit outcome.

Out of scope: adding an ordering heuristic or edge; modifying PCPDAG; increasing/sweeping tolerance; fitting thresholds; rerunning/tuning extractor, resolver, detector, assignment, OCR, VLM, Ollama, or Reading Order; generating a Realistic/Oracle ordering candidate; editing Human Panel GT or Human Reading Order GT; production Reader/Reading Order integration; modifying frozen predictions/sources/accepted archives; creating Checkpoint 12.9; commit or push.

## Safety and data-integrity gates

- Preserve all authoritative, Human-approved, frozen, production, and historical files byte-for-byte.
- Human order and all transitive Human-derived fingerprints remain unavailable until global freeze.
- No page/source/GT identity may act as an audit distinction.
- No unsupported relation, forced order, or stable-ID tie-break may be presented as identifiable geometry.
- Any isolation, chronology, mutation, determinism, resource, or artifact failure forces Outcome D and stops without altered rerun.
- Resource Guard must be `NORMAL`; OCR/VLM/Ollama/model calls must remain `0/0/0`.
- No new Human GT is expected. If genuinely missing Human evidence is discovered, stop and request only that exact evidence without fabricating or modifying GT.

## Acceptance criteria

- The target cohort is exactly Pages 1, 2, 3, 15, 18, 38 and every 12.7 unresolved ready-set is exhaustively represented.
- Frozen input identities, PCPDAG evidence, protocol, tolerance, and archives verify before analysis; Phase A provenance closure contains no Human-derived content or hash.
- The signature vocabulary/equivalence rules, synthetic expectations, classifications, and A/B/C/D gates are frozen before real Phase A output and Human access.
- RUN_A/RUN_B Phase A outputs are independent and deterministic; both freeze before Human/control evaluation access.
- Each ambiguity receives exactly one justified allowed label, with machine-readable equality or distinction evidence and all applicable contradiction-control results.
- No candidate order/edge is emitted, no threshold is searched, and no rule is implemented or integrated.
- Final outcome follows the predeclared gates; Outcome C is claimed only with affirmative information-limit evidence.
- Production/GT/archive before-and-after hashes match; Resource Guard is NORMAL and model calls are zero.
- Required synthetic, mutation/isolation, retained regression, full backend, compile, JSON/internal/hash reconciliation, workflow validation, and diff-hygiene checks pass.

## Benchmark permission

**ALLOWED only for one finite geometry-only 12.8 audit:** exactly two independent Phase A builds (RUN_A and RUN_B) on the frozen six-page cohort, one global freeze, and one post-freeze Phase B evaluation per run. Resolved frozen pages may be read only for the predeclared contradiction/regression controls. No retry with changed predicates, alternate signature vocabulary, second representation, tolerance/threshold sweep, ordering candidate, extractor/resolver/detector rerun, OCR/VLM/Ollama/model call, or additional page is allowed.

## Required validation

- Focused ready-set/signature/equivalence/contradiction/synthetic/chronology/provenance/mutation/determinism tests and retained 12.6/12.7 regressions.
- Canonical backend unit tests and compile of changed Python.
- JSON/schema/internal-hash validation, exact artifact-set validation, RUN_A/RUN_B raw and semantic reconciliation, and independent metric/classification reconciliation.
- Before/after hashes for production, GT, frozen inputs/predictions, and accepted archives.
- Workflow validation and `git diff --check`.
- Frontend lint/build is not required unless frontend is unexpectedly touched; such a touch is out of scope and must be investigated.

## Stop condition

Coder stops after the single authorized audit, artifacts, tests, and `REPORT.md`, advancing only to `IMPLEMENTED` for independent review. Stop immediately with Outcome D on any hard gate and do not tune or rerun. Do not implement a geometry distinction, alter production/GT/tolerance, create another checkpoint, commit, or push.
