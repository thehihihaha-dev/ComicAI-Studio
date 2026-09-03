# Checkpoint 12.1 — Panel-Aware Reading Order Prototype

## Objective

Run the smallest controlled offline experiment that can answer whether explicit non-Human panel structure materially improves manga Reading Order over the frozen text-region geometry baseline. Audit available panel geometry first. Only if the audit passes a predeclared usability gate may the Coder build and evaluate one hierarchical panel-aware prototype on the existing ten-page Human click-order set.

## Background

Human-approved Checkpoint 12.0 concluded **C. CURRENT GEOMETRY INSUFFICIENT**. All four residual inversions are cross-panel failures on Pages 15, 17, and 38: panel containment/order and text-to-panel assignment are absent from the `PAGE_FALLBACK` representation. The immutable control is normalized vertical overlap `>= 0.50`, `BENCHMARK_FITTED`: 7/10 exact pages, 43/50 exact positions, 120/124 correct pairs (96.77%), four inversions, 3 pages improved, 7 unchanged, 0 regressed, and Page 3 exact.

The current ten-page logical-region artifact appears to expose only `PAGE_FALLBACK`; this observation is not permission to fabricate panels. The panel-data audit is a hard gate and may legitimately end the checkpoint with outcome B or D.

## Files or modules likely involved

- `backend/app/services/reader_v2_fast_pass.py` (read-only reference for existing panel containment/order behavior)
- `backend/app/services/reading_order_geometry_experiment.py` and `backend/app/services/reader_v2_final_contract.py` (read-only frozen control references)
- persisted Day 11/12 artifacts under `benchmarks/day11/` and `benchmarks/day12/`
- source/prediction artifacts that contain non-Human panel geometry, if any are discovered
- one isolated offline prototype/helper under `backend/app/services/` or `scripts/`, only after the audit gate passes
- focused tests under `backend/tests/`
- new checkpoint artifacts under `benchmarks/day12/`
- `ai-workflow/REPORT.md`, `ai-workflow/REVIEW.md`, and workflow state files

## Scope

### Phase 1 — mandatory panel-data audit and hard gate

1. Reproduce the frozen control exactly before evaluating any candidate.
2. Inventory every legitimate non-Human panel source for each of the ten pages. Distinguish persisted predicted panel geometry, source-derived deterministic geometry, `PAGE_FALLBACK`, Human-authored labels, and 12.0 benchmark-only manual visual audit evidence.
3. For every page report: asset/source hash, logical text-region count, predicted panel count excluding `PAGE_FALLBACK`, geometry source/version, panel bbox/polygon availability, confidently assignable regions, unassigned regions, multi-panel/ambiguous regions, and whether the evidence can be replayed without inference.
4. Human click order and any Human-authored or 12.0 manual panel annotations are evaluation/audit-only. They must not construct, tune, select, repair, or order candidate panels. Hash/record all runtime candidate inputs before reading Human order for scoring.
5. The audit gate passes only if replayable non-Human panel geometry exists for all three known-failure pages (15, 17, 38), includes enough coordinates to test containment/assignment and panel order, and is available for enough control pages to measure regressions rather than only the known failures.
6. If the gate fails, stop candidate implementation. Produce the audit and summary artifacts, select outcome **B. PANEL DETECTION/ASSIGNMENT IS THE BOTTLENECK** or **D. EVIDENCE INSUFFICIENT**, explain the exact missing input, and recommend the smallest separately approved structural-extraction experiment. Do not derive panel boxes from Human order or the 12.0 manual failure audit.

### Phase 2 — permitted only after a passing audit gate

7. Implement one offline hierarchical candidate with the minimum representation:
   - `panel_id`
   - panel `bbox` or polygon and its non-Human source/provenance
   - assigned logical region IDs
   - assignment state/confidence (`ASSIGNED`, `UNASSIGNED`, `AMBIGUOUS`)
   - deterministic panel order and ambiguity reasons
   Do not add semantic or story fields.
8. Use a narrowly justified deterministic assignment policy declared before scoring:
   - full containment is confident;
   - otherwise use one fixed intersection-over-region ratio only if justified independently of Human order;
   - multiple qualifying panels produce `AMBIGUOUS`;
   - no qualifying panel produces `UNASSIGNED`;
   - cross-panel/overlapping-panel regions are preserved and flagged, never discarded.
   Any numeric value observed or chosen from these ten pages must be labeled `BENCHMARK_FITTED`; no parameter sweep is allowed.
9. Construct panel order separately from text order. Generic geometry forms stable top-to-bottom panel tiers and exposes unclear relationships; `MANGA_RTL_POLICY` orders peers right-to-left. Stable coordinate/ID keys resolve exact ties. Do not use Human sequence at runtime.
10. For each confidently assigned panel, reuse the frozen `A_VERTICAL_OVERLAP` intra-panel text rule rather than redesigning it. If Panel A precedes Panel B, all confidently assigned text in A must precede confidently assigned text in B.
11. Preserve `UNASSIGNED` and `AMBIGUOUS` regions. Use one declared deterministic fallback based only on frozen page-level geometry, append explicit ambiguity metadata, and report whether fallback placement affects a scored pair. Do not claim confident correctness for forced fallback order.
12. Freeze candidate output and its input/config hashes before attaching Human GT for scoring. Evaluate only afterward.

### Artifacts

Create at minimum:

- `benchmarks/day12/panel-data-audit-12.1.json`
- `benchmarks/day12/panel-aware-protocol-12.1.json`
- `benchmarks/day12/panel-aware-comparison-12.1.json`
- `benchmarks/day12/panel-aware-structural-errors-12.1.json`
- `benchmarks/day12/panel-aware-summary-12.1.json`

If the Phase 1 gate fails, protocol/comparison/error artifacts may be explicit `NOT_RUN_PANEL_DATA_GATE_FAILED` records rather than fabricated candidate results. Synthetic fixtures must be stored separately, labeled `SYNTHETIC`, and excluded from Human metrics.

## Out of scope

- No production Reader or routing integration and no complete Reader rewrite.
- No panel detection/extraction implementation if the Phase 1 audit finds usable predicted panel geometry absent; that becomes a separately approved checkpoint.
- No use of Human click order, Human panel labels, or 12.0 manual visual panel evidence as candidate runtime input.
- No OCR, R2, Repair Boundary, Reader text reliability, Story, Page Understanding semantics, scene/chunk, or Human GT changes.
- No OCR/VLM/Ollama/model inference, model loading, threshold sweep, page-specific patch, unseen Human validation, Webtoon/Western policy work, commit, push, or next-checkpoint implementation.

## Safety constraints

- Human GT is immutable and evaluation-only; candidate generation must be demonstrably independent of it.
- Preserve all Day 11 and 12.0 historical artifacts and persisted user-approved data.
- Candidate artifacts must record input hashes, geometry provenance, source policy, config, code/version identity, and `gt_runtime_features: []`.
- OCR calls = 0, VLM calls = 0, Ollama calls = 0. Stop before model inference if persisted structure is insufficient.
- Resource Guard must remain `NORMAL`; only lightweight deterministic geometry replay is allowed.
- Never silently assign uncertain text to a panel, discard a region, or turn ambiguity into correctness.
- The frozen control definition and `BENCHMARK_FITTED` label cannot change.

## Acceptance criteria

### Common criteria

- Frozen control reproduces exactly: 7/10 pages, 43/50 positions, 120/124 pairs, four inversions, 3 improved/7 unchanged/0 regressed, Page 3 exact.
- The per-page panel-data audit is complete, source/provenance-backed, deterministic, and explicitly separates non-Human predicted inputs from Human/manual evaluation evidence.
- Human order is absent from panel construction, assignment, ordering, candidate fingerprints, and pre-score outputs; hashes demonstrate prediction freezing before evaluation.
- Required artifacts are parseable, internally consistent, and honest about `RUN` versus `NOT_RUN_PANEL_DATA_GATE_FAILED`.
- No production/unrelated subsystem or authoritative data changes; zero model calls; Resource Guard `NORMAL`.

### If the audit gate fails

- No candidate is implemented or scored as panel-aware.
- The exact missing panel detection/assignment evidence is reported per page.
- Final outcome is exactly **B. PANEL DETECTION/ASSIGNMENT IS THE BOTTLENECK** or **D. EVIDENCE INSUFFICIENT** and follows from the audit.

### If the audit gate passes

- The candidate implements `PAGE → PANELS → PANEL ORDER → TEXT ASSIGNMENT → INTRA-PANEL ORDER → FINAL ORDER` with the cross-panel guarantee.
- Structural outputs report assignment coverage, confident/unassigned/ambiguous counts, cross-panel errors, intra-panel errors, and panel-order errors; unavailable oracle-dependent metrics remain explicitly `N/A` rather than inferred.
- Candidate comparison reports exact pages, exact positions, correct/total pairs and accuracy, inversions, improved/unchanged/regressed pages, the four known failures repaired/unchanged, and every new inversion.
- No existing exact page regresses and no new inversion is introduced for outcome A.
- Final outcome is exactly one:
  - **A. PANEL-AWARE STRUCTURE HELPS**
  - **B. PANEL DETECTION/ASSIGNMENT IS THE BOTTLENECK**
  - **C. PANEL-AWARE ORDERING DOES NOT HELP**
  - **D. EVIDENCE INSUFFICIENT**
- Benchmark improvement alone remains `BENCHMARK_FITTED`; it never implies deployment or production calibration.

## Required tests

- Focused audit tests: provenance classification, ten-page completeness, gate pass/fail behavior, GT exclusion, deterministic hashes, and honest `NOT_RUN` artifacts.
- If Phase 2 runs: panel containment, partial/intersection assignment, multi-panel ambiguity, `UNASSIGNED` fallback, manga RTL panel order, upper-before-lower tiers, cross-panel hierarchy guarantee, frozen intra-panel order, deterministic output, Page 3, Page 15, and Page 17 regressions.
- Synthetic behavior, when used: right-before-left panels, upper-before-lower panels, tall/cross-panel text interference, unassigned text, and overlapping panels; label `SYNTHETIC` and exclude from Human metrics.
- Preserve existing Reading Order/12.0 regression tests.
- Canonical full backend suite: `backend/.venv/bin/python -m unittest discover -s backend/tests -t backend`.
- Python compilation for changed Python files.
- JSON parsing plus cross-artifact, hash, gate-state, metric, GT-isolation, and Human/synthetic separation validation.
- `python3 scripts/agent_workflow.py validate`.
- `git diff --check`.

## Benchmark permission

`ALLOWED` only for read-only inventory and deterministic offline replay of persisted non-Human panel/text geometry on the existing ten pages, followed—only after the panel-data gate passes—by one predeclared panel-aware candidate and clearly separate synthetic fixtures. Human GT may be loaded only after prediction artifacts/hashes are frozen for scoring. OCR calls = 0, VLM calls = 0, Ollama calls = 0. No panel/model inference, image-based panel extraction, broad parameter search, unseen Human set, database mutation, production integration, or expensive benchmark is allowed.

## Stop condition

The Coder writes the required artifacts and `ai-workflow/REPORT.md`, moves state to `IMPLEMENTED`, and stops for independent review. A failed panel-data gate is a valid completed implementation result and must stop without building a candidate. After Reviewer PASS, stop at `AWAITING_HUMAN_APPROVAL`. Do not implement the next structural-extraction checkpoint, request Human testing, commit, or push.
