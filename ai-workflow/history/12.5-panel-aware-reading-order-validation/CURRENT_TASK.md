# Checkpoint 12.5 — Panel-Aware Reading Order Validation

## Objective and checkpoint question

Run the smallest deterministic, geometry-only experiment answering: **Given trustworthy panel structure when available, can Reader produce the correct manga hierarchy `panel order → logical text-region order within panel` without benchmark-page rules?** Reading correctness and fail-closed uncertainty take priority over coverage or speed. This checkpoint validates an offline structural ordering layer; it does not integrate production Reader or Story.

Checkpoint 12.4 is Human-approved and archived at `ai-workflow/history/12.4-unseen-panel-structure-generalization-validation/`. Its authoritative result is 16/21 unseen panels matched, zero false promotion, precision 1.0, recall 0.761905, F1 0.864865, and 1/6 unresolved pages. Frozen panel artifacts remain immutable inputs.

## Fixed baseline and prior evidence

Preserve the Day 11 `reader-order-control-11.16.json` baseline exactly: 7/10 exact pages, 43/50 exact positions, 120/124 correct pairs, and four inversions. The local rule is normalized vertical overlap `>= 0.50`, top-to-bottom tiers and right-to-left peers, labeled **BENCHMARK_FITTED**, never production-calibrated.

Checkpoint 12.0 established all four inversions as cross-panel group-construction failures. Page 15 requires the bottom-right panel's `LR_0856a888b8df` and `LR_5bdd1160b3a0` before the bottom-left phone-panel `LR_f3054b9c1820`; Page 17 requires the top-right panel before the top-left panel. These relationships and all Human sequences are evaluation-only evidence. They must not select runtime parameters, create page rules, or enter features.

The benchmark cohort is exactly the frozen ten pages `1, 2, 3, 4, 5, 7, 15, 17, 18, 38`, with 50 ordered logical regions. It is a **frozen regression/evidence cohort**, not a new unseen Reading Order cohort: all ten Human sequences participated in prior Day 11 evaluation, and Pages 15/17 are known failures.

## Required reading hierarchy

Keep four explicit levels and preserve their provenance in every trace:

1. `PAGE → PANELS`: oracle or realistic panel structure, never silently mixed.
2. `PANELS → PANEL READING ORDER`: generic manga RTL precedence graph.
3. `PANEL → LOGICAL TEXT REGIONS`: geometry-only assignment with uncertainty.
4. `LOGICAL REGIONS → INTRA-PANEL READING ORDER`: frozen Day 11 local policy.

The runtime path is `Page → panel structure → panel relation DAG/order → assigned logical regions → intra-panel order → final page sequence`. Never flatten all text regions globally before panel hierarchy.

## Phase 0 — immutable evidence and GT-coverage audit

Before implementing or executing a candidate:

1. Persist an input/GT audit containing actual file hashes, source identities, exact cohort, 50 Human-ordered logical-region IDs, logical bboxes, 36 authoritative Human panel boxes (15 from Pages 1/2/15/17 snapshot `5ac1383f...5fd3`, 21 from Pages 3/4/5/7/18/38 snapshot `f62e38d...16ea`), and frozen realistic panel-output hashes from 12.3/12.4.
2. Verify the Day 11 Human sequence artifact hash/identity, both panel-GT snapshots, logical-region geometry, source hashes/dimensions, no duplicate IDs, and no excluded/unverifiable region entering metrics. Fail closed on mismatch.
3. Derive an **evaluation reference only** for text-bearing panels by joining authoritative Human panel geometry with the independent Human final-region sequence. Panel drawing order and panel IDs are never treated as reading order. A panel precedence is authoritative only when the Human sequence plus unambiguous region-to-panel containment establishes it. Empty panels are reported but excluded from text-order-derived panel-order accuracy.
4. Report how many of 50 regions and 36 panels support unambiguous derived assignment/order truth. Do not fabricate missing precedence. If known Page 15/17 relations or the finite outcome decision cannot be grounded, stop before candidate execution with Outcome D and request only the exact missing panel-order or region→panel labels.

The current repository audit indicates no immediate Human task: the exact ten pages have both Human final sequences and Human Panel GT. Coder must prove the deterministic join is sufficient. New Human GT is forbidden unless this Phase 0 artifact proves a named ambiguity blocks a required decision.

## Panel-order representation and policy

Implement one isolated deterministic panel-order module using panel rectangles only. No OCR text, region text, confidence, source hash, asset/page/GT ID, Human sequence, or Page 15/17 flag may be accepted by its API.

Represent each page as an explicit relation DAG with stable panel-node IDs and auditable edges such as `ABOVE`, `BELOW`, `LEFT_OF`, `RIGHT_OF`, `SAME_ROW`, `SAME_COLUMN`, `SPANS_ROW`, `SPANS_COLUMN`, and `ADJACENT`. `CONTAINS_REGION` belongs only to the later assignment trace, not panel precedence.

Use a generic manga RTL hierarchy:

- recursively recognize strict geometry-separated guillotine partitions;
- horizontal partitions order upper before lower;
- vertical partitions order right before left;
- recurse within each partition, naturally handling rows, columns, tall-right beside stacked-left, tall-left beside stacked-right, top/bottom spanning panels, and page-edge panels;
- use source-normalized geometry and stable IDs only;
- for offset/non-guillotine structure, emit only precedence supported by strict separation/projection relations frozen in the protocol before Human sequence access.

Do not use a pairwise comparator as the sorter. Build edges first, compute transitive closure/cycle evidence, then perform deterministic topological processing. If evidence creates a cycle, incompatible equally supported relations, or multiple materially distinct orders for text-bearing panels, return `UNRESOLVED`; never break semantic ambiguity with page ID or arbitrary geometry merely to score.

All predicates, tolerances, edge strengths, conflict rules, and stable fallbacks must be declared and hashed before real Human order GT is opened. They may be developed only from geometry definitions and the required synthetic fixtures. Any non-universal parameter must be labeled `EXPERIMENT_PREDECLARED`; anything inherited from Day 11 remains `BENCHMARK_FITTED`.

## Text-to-panel assignment policy

Assign each persisted logical-region bbox using panel geometry only, recording region coverage and competing panels:

1. `ASSIGNED_CONTAINED`: uniquely contained in one panel, allowing only a declared numeric rounding tolerance.
2. `ASSIGNED_INTERSECTION`: not contained, but its center lies in exactly one panel and that panel covers a strict majority (`> 0.50`) of region area; label `EVALUATION_PREDECLARED_GEOMETRIC_MAJORITY`.
3. `AMBIGUOUS`: multiple panels satisfy the same strongest rule, the best evidence ties, or overlap crosses a panel boundary without unique majority support.
4. `UNASSIGNED`: no panel has justified geometric support.

Never force assignment. Oracle and realistic tracks use the identical assignment code/config. Report assigned-contained, assigned-intersection, ambiguous, unassigned, and coverage separately. Human GT/reference assignments may be joined only in the scoring layer after candidate assignment output is frozen; `gt_runtime_features = []`.

## Intra-panel ordering

Within each confidently assigned panel, reuse the frozen Day 11 manga local rule unchanged: normalized vertical overlap `>= 0.50`, top-to-bottom tiers, right-to-left peers, stable region-ID tie-break. Keep it labeled `BENCHMARK_FITTED`. Do not tune it or use Human panel/order GT inside runtime.

Cross-panel precedence is determined solely by the panel DAG; intra-panel ordering is applied only after assignment. Evaluation must classify every inversion as cross-panel, intra-panel, assignment-origin, or unresolved-structure-origin.

## Two-track experiment

### Track O — Oracle structure

Input only authoritative Human panel rectangles and ambiguity flags. Strip Human panel drawing order and opaque IDs before ordering; replace them with deterministic geometry IDs. This asks: **if panel structure is correct, does the generic hierarchy and assignment policy recover Human final region order?** Human final sequence remains unavailable until candidate traces are frozen.

### Track R — Realistic structure

Input only already-frozen selected resolver panels: approved 12.3 outputs for Pages 1/2/15/17 and 12.4 outputs for Pages 3/4/5/7/18/38. Never rerun extractor/resolver, supplement misses with oracle boxes, or reinterpret unresolved candidates as selected. This asks: **with current panel coverage, which pages/regions can be ordered safely end-to-end?** Incomplete structure must become `AMBIGUOUS`, `UNASSIGNED`, or `UNRESOLVED`, not oracle-assisted output.

Freeze both tracks' panel graph, assignment, panel order, intra-panel order, final sequence, statuses, and semantic hashes before opening Human order GT. Run each track twice in memory and require byte/semantic equality. Candidate code/config must be identical across pages and tracks except the explicitly named panel-source adapter.

## Benchmark and evidence partition

- Known failure evidence: Pages 15 and 17. Use only after freeze to verify the four specified cross-panel inversions; never tune from them.
- Frozen regression controls: Pages 1, 2, 3, 4, 5, 7, 18, 38. They verify no regression. They are not claimed unseen because their sequences were used historically.
- Full reporting population: all ten pages and all 50 Human-ordered regions, with exclusions/ambiguity explicitly reconciled.
- Synthetic development fixtures: `2×2 RTL grid`, horizontal pair, vertical pair, tall-right + stacked-left, tall-left + stacked-right, spanning top, spanning bottom, offset panels, ambiguous overlap, and bridge/non-transitivity. Add permutation/stable-ID variants, cycle/conflict, empty panel, cross-border region, and unassigned region. Synthetic results never count as Human accuracy.

## Metrics and mandatory reconciliation

Report both tracks independently and never merge coverage with correctness.

Panel order on text-bearing panels with authoritative derived precedence:

- exact evaluable-page order accuracy;
- exact position accuracy;
- pairwise relation accuracy and inversion count;
- unresolved/evidence-insufficient pages;
- total/evaluable/excluded panels and relations.

Text-to-panel assignment:

- contained assigned, intersection assigned, ambiguous, unassigned;
- assignment coverage over all 50 regions;
- reference-agreement count where Phase 0 establishes an authoritative derived mapping;
- uncovered/ambiguous IDs per page.

Final text order:

- exact page accuracy;
- exact position accuracy;
- correct/total pairwise relations and inversion count;
- cross-panel, intra-panel, assignment-origin, and unresolved-structure-origin inversions;
- resolved/unresolved pages and resolved-region coverage.

Reproduce the baseline 7/10, 43/50, 120/124, four inversions unchanged. For each track report whether all four known Page 15/17 inversions are repaired, every new inversion, and every regression on the seven formerly exact pages. No regression may be hidden in aggregate values. For unresolved output, report correctness on resolved comparable pairs and coverage; never score missing output as silently correct.

## Predeclared outcomes

Choose mechanically after both tracks are frozen and evaluated:

### A. PANEL-AWARE ORDERING PASS

- Phase 0 GT/reference is sufficient and identities/determinism/isolation pass.
- Oracle Track: all 10 pages final-order exact, all 50 positions exact, all 124 comparable pairs correct, zero inversion, all four known inversions repaired, zero new inversion/regression, 50/50 justified assignments, and no unresolved page.
- Realistic Track: zero confident inversion, zero regression among resolved outputs, every resolved page exact, all four known inversions repaired wherever required panels/regions are structurally available, no unsafe forced assignment, and no fewer than 7/10 pages fully and confidently resolved. Coverage/unknowns remain explicitly reported.
- Synthetic fixtures all satisfy declared order or correctly return `UNRESOLVED`; no cycle, permutation, determinism, leakage, resource, or production regression.

### B. PANEL HIERARCHY HELPS BUT ORDERING REMAINS INCOMPLETE

- Valid GT and no confident new inversion, unsafe assignment, leakage, nondeterminism, or production regression.
- Oracle Track repairs at least one known inversion and strictly improves baseline pairwise/position correctness, but misses any A completeness requirement; or Oracle passes while Realistic Track safely remains below A coverage/repair requirements because panel structure is incomplete.
- Name cross-panel, intra-panel, assignment, and structural-coverage blockers; do not integrate production ordering.

### C. PANEL STRUCTURE/ASSIGNMENT STILL BLOCKS ORDERING

- Valid sufficient GT, but Oracle fails to improve the four known inversions, introduces any confident new inversion/regression, forms unresolved/cyclic relations on otherwise supported ordinary layouts, forces unsupported assignments, or realistic output creates confident wrong order; or neither A nor B holds.
- Stop for a new architecture decision. Do not tune during analysis.

### D. HUMAN ORDER GT INSUFFICIENT

- Source/identity mismatch, missing logical geometry, non-authoritative panel/order evidence, or ambiguous derived mapping prevents evaluation of a required decision.
- Do not fabricate panel order or assignment. Stop at a Human boundary requesting only exact missing panel-order edges and/or region→panel labels for named pages/IDs.

## Files/modules likely involved

- Read-only baseline/evidence: `benchmarks/day11/reader-order-control-11.16.json`, `reader-order-summary-11.16.json`, `reader-order-inversion-audit-11.16.json`, and Checkpoint 12.0 artifacts/history.
- Read-only logical geometry: `benchmarks/day12/panel-data-audit-12.1.json`, `panel-structural-metrics-12.2.json`, and their frozen source artifacts.
- Read-only oracle structure: persisted/authoritative 12.2 GT snapshot plus `panel-unseen-human-gt-post-correction-validation-12.4.json`.
- Read-only realistic structure: `panel-conflict-resolution-output-12.3.json` and `panel-unseen-resolution-output-12.4.json`, with freeze manifests/graphs.
- One new isolated backend service for panel relation DAG, assignment, and hierarchical ordering; one finite offline runner; one focused test module.
- New non-overwriting `panel-order-*12.5.json` audit, protocol, synthetic, candidate-freeze, evaluation, and summary artifacts under `benchmarks/day12/`.

## Scope and artifacts

The Coder may implement only the isolated offline geometry/order experiment and tests. Required finite artifacts:

1. `panel-order-input-gt-audit-12.5.json`.
2. `panel-order-protocol-12.5.json`, persisted before real Human sequence access.
3. `panel-order-synthetic-12.5.json`.
4. `panel-order-oracle-candidates-12.5.json`.
5. `panel-order-realistic-candidates-12.5.json`.
6. `panel-order-candidate-freeze-12.5.json`, proving both candidates predate Human sequence access.
7. Post-freeze only: `panel-order-evaluation-12.5.json` and `panel-order-summary-12.5.json`.

Candidate artifacts include complete nodes/edges/cycles, component/topological traces, assignments and evidence, panel order/status, intra-panel tiers, final region sequence/status, code/config/input hashes, `gt_runtime_features: []`, and zero model calls. Evaluation artifacts include both tracks, all metrics, four-inversion audit, all regressions/new inversions, failure taxonomy, baseline comparison, and mechanically selected A/B/C/D outcome.

## Out of scope

- Panel extraction/resolver rerun or tuning; new detector rules; panel-box mutation; threshold sweep; benchmark-page/source/GT-ID runtime rules.
- Production Reader integration, replacing the Day 11 rule, OCR recognition/transcription, VLM/Ollama, Story/Page Understanding/Scene/Carry-over, speaker/dialogue semantics, or new source pages.
- Treating synthetic output as Human accuracy; inferring unsupported GT; automatic Human annotation; commit, push, deployment, or Checkpoint 12.6.

## Safety constraints

- Resource Guard must be `NORMAL`; OCR/VLM/Ollama calls `0/0/0` and no expensive Reader recognition.
- Use persisted logical geometry and frozen panels only. Sequential execution; no database writes or mutation of Human GT/frozen artifacts.
- Candidate generation freezes before Human final sequence or 12.0 inversion evidence is loaded for evaluation. Static import and behavioral perturbation tests must prove `gt_runtime_features = []` and candidate invariance to changed mock GT.
- Fail closed on identity/hash/config/code mismatch, cycle, nondeterminism, unsupported assignment, or insufficient evidence.

## Acceptance criteria

- Phase 0 reconciles all 10 pages, 50 ordered regions, 36 Human panels, both panel snapshots, logical geometry, source identity, and existing GT sufficiency without requesting redundant Human work.
- The four-level hierarchy is explicit; oracle and realistic tracks are isolated and use identical generic ordering/assignment code.
- Relation DAG handles every required real/synthetic layout deterministically without non-transitive comparator behavior or page-specific branches.
- Candidate outputs and hashes freeze before Human sequence access; two runs and input permutations are identical; GT perturbation cannot change candidates.
- Assignment never forces ambiguity; coverage and correctness are separated.
- Evaluation exactly reconciles baseline, per-page/pair/position metrics, four known inversions, new inversions, regressions, unresolved coverage, and outcome gates.
- Frozen panel artifacts, Human GT, production Reader, OCR, and historical artifacts remain unchanged.

## Required tests

- Input cohort/order/identity/hash/count reconciliation; missing/mutated source/artifact fail closed; legacy and unseen GT snapshot verification.
- DAG relation unit tests for every synthetic fixture, transitive closure, cycle/conflict, multiple-topological-order unresolved behavior, stable IDs, permutation invariance, and deterministic serialization.
- Assignment containment, rounding boundary, unique-majority intersection, tie/multi-panel ambiguity, cross-border, empty-panel, and unassigned tests.
- Hierarchical composition tests separating cross-panel and intra-panel order; frozen `>=0.50` inclusivity and `BENCHMARK_FITTED` label.
- Oracle/realistic source isolation, no oracle fallback in realistic track, no panel mutation, candidate-before-GT ordering, static `gt_runtime_features: []`, and behavioral mock-GT invariance.
- Metric/pairwise/inversion/coverage reconciliation; Page 15/17 four-inversion audit; all seven prior-exact page regressions; mechanical A/B/C/D selection.
- Two-run and permutation byte/semantic determinism; JSON/file/hash reconciliation.
- Relevant Day 11/12 Reading Order and panel regressions, canonical backend suite, Python compile, frontend only if touched, workflow validation, and `git diff --check`.

## Benchmark permission

**ALLOWED with exact limits.** One geometry-only candidate generation plus one identical in-memory determinism pass for Track O and Track R on exactly Pages 1, 2, 3, 4, 5, 7, 15, 17, 18, and 38; the finite synthetic suite; then, only after both candidate artifacts/freeze exist, one Human-sequence evaluation plus one reconciliation pass that does not regenerate candidates. No extractor/resolver/OCR/Reader recognition/model run, threshold sweep, alternate candidate selection after GT, new pages, or production integration.

## Stop conditions and Human boundary

- If Phase 0 proves existing evidence insufficient, stop before real candidate execution with Outcome D and `HUMAN TESTING REQUIRED`, naming only missing panel-order edges or region→panel labels. Do not request full reannotation.
- Otherwise complete both frozen tracks and evaluation, write the report, advance to `IMPLEMENTED`, and stop for Independent Reviewer.
- Reviewer PASS stops at `AWAITING_HUMAN_APPROVAL`. It does not start Panel Ordering integration, Story, another checkpoint, commit, or push.
