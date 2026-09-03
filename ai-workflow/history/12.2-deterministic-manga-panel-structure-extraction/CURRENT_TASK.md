# Checkpoint 12.2 — Deterministic Manga Panel Structure Extraction

## Objective

Run one controlled offline experiment on the existing ten Reading Order pages to determine whether ComicAI can independently extract Reader-useful manga panel structure from source pixels and legitimate non-Human geometry. Produce deterministic panel candidates with provenance and uncertainty; do not integrate them into Reading Order.

## Background

Human-approved Checkpoint 12.1 concluded **B. PANEL DETECTION/ASSIGNMENT IS THE BOTTLENECK**: usable predicted panels are 0/10 and all 63 logical regions lack panel geometry. The frozen Reading Order baseline remains 7/10 exact pages, 43/50 positions, 120/124 pairs, and four inversions. Pages 15 and 17 contain cross-panel failures, but their Human/manual structural descriptions are forbidden extraction inputs.

Repository inspection confirms the ten images are available under `backend/uploads/` and resolvable by the source hashes in the Day 11 logical-region artifact. Legitimate inputs are source pixels/dimensions, persisted raw/logical region bboxes and IDs, and system provenance/fallback records. Pillow, NumPy, OpenCV, and scikit-image are installed, but no project panel extractor exists. `reader_v2_fast_pass.py` accepts rectangular panels but remains read-only.

## Files or modules likely involved

- read-only Day 11/12.1 input and provenance artifacts under `benchmarks/day11/` and `benchmarks/day12/`
- ten hash-matched images under `backend/uploads/`
- `backend/app/services/reader_v2_fast_pass.py` (read-only future-containment reference)
- one isolated extractor under `backend/app/services/`, one offline runner under `scripts/`, and one focused test module under `backend/tests/`
- new non-overwriting 12.2 artifacts under `benchmarks/day12/`
- `ai-workflow/REPORT.md` and workflow state files during Coder handoff

## Scope

### Input audit and freeze

1. Resolve the same ten pages by asset ID, page number, and source SHA-256. Fail closed on missing, duplicate, or mismatched images.
2. Inventory source pixels/dimensions, raw/logical geometry, fallback structure, available deterministic utilities, and every runtime feature. Classify Human click order, Human panel/group labels, and 12.0 manual evidence as evaluation-only or forbidden; record `gt_runtime_features: []`.
3. Freeze the input manifest and one predeclared extractor configuration before Human/manual comparison. No parameter sweep, benchmark-selected variant, or page-specific rule. Any value changed after observing these pages is labeled `BENCHMARK_FITTED` everywhere.

### Panel object and extraction

4. A panel is a visual manga frame/container smaller than the page—not a page fallback, bubble, text region, or Human group. Each prediction contains stable `panel_id`; pixel and normalized bbox; polygon only when contour-supported; state `DETECTED` or `AMBIGUOUS`; evidence/provenance; an explicitly heuristic, non-probabilistic score; edge-touch and overlap metadata; and naturally derivable relative-position/adjacency edges. A page with no defensible structure is `UNRESOLVED`. Never emit the whole page as a detected panel.
5. Implement one lightweight deterministic hybrid pipeline:
   - deterministic grayscale plus binary edge/near-white masks;
   - sustained horizontal/vertical whitespace-gutter proposals with recursive partitioning, including terminating splits needed for tall-panel-beside-stacked layouts;
   - independent strong closed/near-closed border-contour rectangles, including page-edge completion;
   - deterministic fusion, nested/near-duplicate suppression, and rejection of page-sized, tiny, degenerate, bubble-like, or unsupported candidates;
   - conflicting overlaps, broken-border evidence, or weak single-source candidates remain `AMBIGUOUS`; weak pages become `UNRESOLVED`/`PAGE_FALLBACK` without inventing a panel.
6. Use one configuration justified by scale-normalized structural assumptions and synthetic fixtures. Persisted region bboxes are post-extraction Reader-relevance diagnostics only; they cannot create/move boundaries or tune thresholds. Do not invoke OCR.

### Layout limits

7. Target rectangular bordered grids, right/left and upper/lower splits, tall panel beside stacked panels, narrow visible gutters, offset rectangles, and page-edge panels.
8. Borderless panels are detectable only with independent whitespace evidence. Missing-border and mild irregular layouts may be ambiguous. Arbitrary polygons, artwork crossing boundaries, nested/inset or true overlapping panels, absent gutters, and borderless layouts without stable whitespace are explicitly risky/unsupported.

### Evaluation and leakage boundary

9. Hash/freeze audit, protocol, and per-page predictions before loading Human click order or 12.0 manual evidence.
10. Report: pages with detected structure; detected/ambiguous panels per page; fallback/unresolved rates; logical regions contained in exactly one panel, multiply contained, boundary-intersecting, ambiguous, or unassigned; duplicate/nested/overlap counts before/after suppression; usable and conflicting adjacency edges; source/config/code hashes; runtime/resources; and byte-equivalent semantic repeatability across two clean runs.
11. Reader relevance is an interpretive gate: useful output must support defensible containment for some logical regions and spatial relations for a future panel-order experiment. Unrelated rectangles are not success.
12. After freezing predictions, diagnose Pages 15 and 17: whether independently predicted geometry separates the relevant visible areas and permits assignments without Human answers. Do not special-case, revise predictions, run Reading Order, or claim inversion repair.
13. Existing 12.0 manual descriptions are allowed only as isolated post-prediction qualitative Page 15/17 diagnostics, never for extraction, tuning, selection, or numeric GT. Human click order cannot establish panel correctness.
14. Panel accuracy/precision/recall/IoU are `N/A` unless legitimate independent panel labels are discovered. Never fabricate them. If predictions exist but correctness is undecidable, choose outcome D and propose the smallest separately approved Human panel validation set.

### Artifacts

Create without overwriting history:

- `benchmarks/day12/panel-extraction-input-audit-12.2.json`
- `benchmarks/day12/panel-extraction-protocol-12.2.json`
- `benchmarks/day12/panel-predictions-12.2.json`
- `benchmarks/day12/panel-structural-metrics-12.2.json`
- `benchmarks/day12/panel-page-15-17-diagnostics-12.2.json`
- `benchmarks/day12/panel-ambiguities-12.2.json`
- `benchmarks/day12/panel-extraction-summary-12.2.json`

Optional deterministic overlays may live only in a new `benchmarks/day12/panel-extraction-overlays-12.2/` directory and are diagnostics, not GT.

## Out of scope

- No production Reader, Reading Order, OCR, R2, Repair Boundary, Story, database, API, frontend, or Human GT change.
- No text-to-panel integration, panel reading-order algorithm, Reader candidate scoring, or claim that an inversion was repaired.
- No Human panel/group labels, click order, or manual structure as extractor input; no semantic analysis, OCR, VLM/Ollama/model inference, model shopping, broad sweep, per-page patch, deployment, commit, push, or next checkpoint.

## Safety constraints

- Extraction is image-only at its core; region geometry is diagnostics-only and cannot affect predicted boundaries.
- Human/manual evidence stays immutable and unavailable until prediction hashes freeze; runtime fingerprints contain no Human feature.
- Preserve all historical artifacts and persisted/user-approved data.
- Never force a panel, count `PAGE_FALLBACK` as a panel, hide conflicting candidates, or present heuristic confidence as correctness.
- OCR/VLM/Ollama calls = 0/0/0. Resource Guard must remain `NORMAL`; stop before expensive/model inference.
- Benchmark-observed adjustments are `BENCHMARK_FITTED` and cannot imply production calibration.

## Acceptance criteria

- All ten images are hash-verified and the audit completely classifies legitimate/forbidden evidence.
- One deterministic extractor emits schema-valid panels or honest ambiguity/unresolved states for all pages, with stable IDs, geometry, provenance, evidence, overlap/adjacency metadata, and no full-page false panel.
- Predictions freeze before Human/manual evaluation; `gt_runtime_features` is empty; tests prove isolation.
- Requested per-page/aggregate structural metrics reconcile. Unsupported accuracy metrics are `N/A`.
- Containment diagnostics establish Reader relevance without integration; Pages 15/17 receive non-special-cased post-freeze diagnostics.
- Two clean runs are semantically byte-equivalent except separately recorded timing/resource observations. Synthetic results are labeled `SYNTHETIC` and excluded from ten-page performance.
- Summary selects exactly one:
  - **A. DETERMINISTIC PANEL EXTRACTION IS VIABLE**
  - **B. PARTIAL PANEL EXTRACTION — SPECIFIC FAILURE CLASSES REMAIN**
  - **C. DETERMINISTIC PANEL EXTRACTION IS INSUFFICIENT**
  - **D. PANEL CORRECTNESS CANNOT BE EVALUATED YET**
- A requires independently useful real-page structure, meaningful single-panel assignment coverage, and usable spatial relations. B names failure classes; C identifies deterministic evidence limits; D requests only minimal later validation.
- No production/authoritative changes; zero model/OCR calls; Resource Guard `NORMAL`.

## Required tests

- Separate synthetic fixtures: 2x2 grid, right/left, upper/lower, tall beside stacked, narrow gutter, page edge, missing border, and overlapping/ambiguous. Never count these as benchmark performance.
- Unit tests: stable IDs/output; image/hash validation; gutter partition; contour evidence; edge completion; nested/duplicate suppression; full-page/tiny/bubble-like rejection; ambiguity/unresolved handling; provenance; adjacency; fallback avoidance.
- GT isolation: pixels-only extractor API; no Human/manual runtime input/fingerprint; freeze precedes diagnostics; region geometry cannot change panel boundaries.
- Ten-page artifact/metric reconciliation and explicit Page 15/17 coverage without page-specific branches.
- Preserve Reader/Reading Order/12.0/12.1 regressions; run canonical backend suite, compilation, JSON/hash validation, two-run determinism, workflow validation, and `git diff --check`.

## Benchmark permission

`ALLOWED` only for one predeclared lightweight deterministic configuration on the same ten hash-verified local images, plus separate synthetic fixtures. Persisted bboxes may be used only after extraction for diagnostics. After prediction freeze, existing manual evidence may be read solely for qualitative Page 15/17 diagnostics. OCR/VLM/Ollama calls = 0/0/0. No Human labels as input, new GT, Reading Order integration/scoring, sweep, model inference, database mutation, production change, or expensive benchmark.

## Stop condition

The Coder writes the isolated extractor, runner, focused tests, artifacts, and `REPORT.md`; selects one A/B/C/D outcome; advances to `IMPLEMENTED`; and stops for independent review. If images cannot be hash-resolved, Resource Guard is not `NORMAL`, or model/expensive inference is needed, stop honestly. Do not integrate Reader, request Human annotation during this checkpoint, implement another checkpoint, commit, or push.
