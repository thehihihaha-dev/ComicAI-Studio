# Checkpoint 12.0 — Reading Order V3 Failure Audit

## Objective

Reproduce the frozen Day 11 manga Reading Order candidate (`normalized vertical overlap >= 0.50`) on the existing ten-page Human Reading Order set, reconstruct and explain all four remaining inversions, audit the current ordering decision path and global consistency, verify Human GT integrity, and recommend the safest generalizable Reading Order V3 experiment. This checkpoint is analysis-first; either a positive or negative result is acceptable when supported by evidence.

## Background

The frozen Day 11 candidate is `BENCHMARK_FITTED`, not `PRODUCTION_CALIBRATED`: 7/10 exact pages, 43/50 exact positions, 120/124 correct pairs (96.77%), four inversions, 3 pages improved, 7 unchanged, 0 regressed, Page 3 exact, and candidate selection in 10/10 leave-one-page-out folds. The remaining errors must be understood before any production algorithm change. Existing 11.11, 11.16, and 11.17 Human-GT-subset artifacts are the control evidence and must not be redefined.

## Files or modules likely involved

- `backend/app/services/reader_v2_fast_pass.py`
- `backend/app/services/reader_v2_final_contract.py`
- `backend/app/services/dialogue_builder.py` and relevant callers, read-only unless needed solely to document the current production decision path
- `scripts/reader_order_geometry_11_16.py`
- a new offline diagnostic script under `scripts/`
- focused Reading Order tests under `backend/tests/`
- frozen inputs under `benchmarks/day11/`
- new outputs under `benchmarks/day12/`
- `ai-workflow/REPORT.md`, `ai-workflow/REVIEW.md`, and workflow state files

## Scope

1. Reproduce the frozen 11.16/11.17 candidate metrics exactly from existing artifacts and persisted Human Reading Order GT.
2. Reconstruct each of the four remaining inversions with page/source identity, region IDs, predicted and Human relative order, bboxes, dimensions/aspect ratios, normalized vertical overlap, horizontal/vertical relations, containment/intersection, available panel/group metadata, neighboring regions, complete algorithm decision trace, and the exact reason for the error.
3. Classify every failure using evidence without forcing unsupported labels, and distinguish primary cause among pairwise geometry, row/tier construction, panel/group construction, text-region assignment, inherent ambiguity, or insufficient evidence.
4. Audit the actual current decision flow: page entry point; tier construction; overlap and manga right-to-left policy; tall-region behavior; panel/group metadata; ties; pairwise versus global construction; determinism; transitivity; and representation of ambiguity.
5. Audit global consistency for cycles, unstable ties, non-transitive decisions, unrelated-region sensitivity, and tall-region bridge effects. If a problem is possible, create the smallest clearly labeled `SYNTHETIC` fixture and keep it separate from Human GT; otherwise demonstrate why it is impossible.
6. Audit the four affected Human GT cases without modifying them: duplicate positions, missing/excluded regions, ambiguous/orphan state, available panel/group consistency, and source-hash validity. Report genuine ambiguity separately.
7. Explain the generalization limits of the 10/10 leave-one-page-out result, including small N, shared style, repeated geometry, benchmark fitting, and difficult-layout coverage.
8. Only after the audit, propose at most three candidate directions. For each, state its hypothesis, addressed failures, generalization rationale, regression risk, metadata needs, runtime complexity, and whether current evidence is sufficient.
9. Investigate evidence requirements for future `AMBIGUOUS_ORDER` output without integrating production routing. Separate `MANGA_POLICY` from `GENERIC_GEOMETRY` in the analysis.
10. Create at minimum:
   - `benchmarks/day12/reading-order-failure-audit-12.0.json`
   - `benchmarks/day12/reading-order-decision-traces-12.0.json`
   - `benchmarks/day12/reading-order-candidate-analysis-12.0.json`
   - `benchmarks/day12/reading-order-summary-12.0.json`
   Any synthetic fixture must be stored separately and explicitly labeled `SYNTHETIC`.
11. Diagnostic helpers and narrowly scoped offline candidate prototypes are allowed only when necessary to establish the audit or proposed experiment. Any candidate evaluation must preserve baseline metrics and report exact pages, positions, pairwise accuracy, inversions, improved/unchanged/regressed pages, plus repaired/unchanged/new inversions.

## Out of scope

- No production Reading Order replacement or silent candidate integration.
- No broad threshold search or threshold shopping for 10/10 pages; any threshold probe must be narrow, justified, and labeled diagnostic.
- No OCR engine, OCR confidence, R2, Repair Boundary, Reader text reliability, Story Analyzer/Reliability, Page Understanding, scene/chunk, Human OCR GT, or Human Reading Order GT changes.
- No OCR, VLM, Ollama, or paid/local model inference.
- No Webtoon or Western-comics policy experiment; only identify reusable generic geometry versus current manga policy.
- No Checkpoint 12.1 work, commit, push, or automatic approval.

## Safety constraints

- Human GT and existing Day 11 artifacts are immutable and evaluation-only.
- Preserve persisted user-approved and authoritative data; use artifact replay or read-only access.
- Expected calls: OCR = 0, VLM = 0, Ollama = 0. Do not start or load a model.
- Resource Guard must remain `NORMAL`; no expensive benchmark is authorized.
- Synthetic evidence must never be counted as Human benchmark GT.
- Never infer missing panel/tier labels as authoritative facts; record missing evidence as `N/A` or insufficient.
- Preserve the frozen baseline label and exact definition: manga, normalized vertical overlap `>= 0.50`, `BENCHMARK_FITTED`.

## Acceptance criteria

- Frozen metrics reproduce exactly: 7/10 exact pages, 43/50 positions, 120/124 pairs, four inversions, 3 improved/7 unchanged/0 regressed, Page 3 exact.
- All four inversions are independently derivable and each required geometric, structural, neighboring, source, and decision-path field is present or explicitly marked unavailable with reason.
- Failure taxonomy and geometry-versus-structure assignment are evidence-based, with ambiguity/insufficient evidence preserved.
- Current decision flow is concise but complete, distinguishes `MANGA_POLICY` from `GENERIC_GEOMETRY`, and accurately states global-order/transitivity behavior.
- Human GT integrity and source hashes are checked without mutation; excluded regions do not enter evaluation.
- Global consistency has either an evidence-backed impossibility argument or a separate minimal `SYNTHETIC` regression fixture.
- Generalization risk explains why 10/10 leave-one-page-out is encouraging but not production calibration.
- At most three post-audit candidates are documented without threshold shopping; one safest next experiment is recommended with expected regression risk and an evidence sufficiency decision.
- Ambiguity evidence and future handling are analyzed but not integrated.
- Required Day 12 JSON artifacts are deterministic, parseable, internally consistent, and do not mix Human and synthetic evidence.
- The final report returns exactly one checkpoint verdict: `A. ROOT CAUSE IDENTIFIED — GENERAL FIX READY TO TEST`, `B. MULTIPLE FAILURE CLASSES — SEPARATE EXPERIMENTS REQUIRED`, `C. CURRENT GEOMETRY INSUFFICIENT`, or `D. HUMAN GT / EVIDENCE INSUFFICIENT`.
- If new Human pages are needed for the next experiment, the report gives only the smallest justified future plan: exact page count, required layouts, required annotation, and tested hypothesis. Human testing is not required inside 12.0.
- No production integration, unrelated subsystem change, Human GT mutation, OCR/VLM/Ollama call, commit, push, or 12.1 work occurs.

## Required tests

- Focused Reading Order tests, including regression coverage for Day 11 Page 3, tall-panel behavior, frozen `>= 0.50` baseline, deterministic ordering, and exclusion of excluded regions.
- A focused global-consistency regression test if an issue is discovered.
- Canonical full backend suite: `backend/.venv/bin/python -m unittest discover -s backend/tests -t backend`.
- Python compilation for changed Python files.
- Parse and validate every new Day 12 JSON artifact and cross-artifact baseline/inversion invariants.
- Workflow validation used by the repository.
- `git diff --check`.

## Benchmark permission

`ALLOWED` only for deterministic, offline replay of the existing ten-page Day 11 Human Reading Order geometry/GT artifacts and narrowly scoped diagnostic candidate prototypes over those same pages or separate explicitly synthetic fixtures. OCR calls = 0, VLM calls = 0, Ollama calls = 0. No image inference, model loading, new data collection, broad parameter sweep, database mutation, or expensive benchmark is allowed.

## Stop condition

The Coder must write the required artifacts and `ai-workflow/REPORT.md`, move workflow state to `IMPLEMENTED`, and stop for independent review. After Reviewer `PASS`, move through `REVIEW_PASSED` to `AWAITING_HUMAN_APPROVAL` and stop. Do not start 12.1, commit, push, or treat Reviewer PASS as Human approval.
