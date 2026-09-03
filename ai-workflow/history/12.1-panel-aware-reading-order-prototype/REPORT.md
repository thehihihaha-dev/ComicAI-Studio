# Checkpoint 12.1 — Panel-Aware Reading Order Prototype

## A. What changed

Implemented the mandatory offline panel-data audit and stopped at the Architect's hard gate. Across the existing ten-page benchmark, persisted non-Human structure contains only page-wide `PAGE`/`PAGE_FALLBACK` groups; it contains zero panel bboxes/polygons and no panel adjacency/order. Because this fails the predeclared gate for Pages 15, 17, 38 and all control pages, no panel-aware candidate, assignment rule, panel order, or synthetic candidate behavior was implemented.

The initial Coder audit omitted explicit persisted panel-like records in the 11.10 scale/cache artifacts. Independent review failed the handoff on that evidence gap. This fix cycle adds both artifacts to immutable input hashes and per-page provenance, programmatically verifies their actual fields, and confirms they agree with the 11.11/11.17 fallback evidence; the gate result and outcome remain unchanged.

Checkpoint outcome: **B. PANEL DETECTION/ASSIGNMENT IS THE BOTTLENECK**.

## B. Files changed

- Added `scripts/panel_data_audit_12_1.py`.
- Added `backend/tests/test_panel_data_audit_12_1.py`.
- Added five 12.1 artifacts under `benchmarks/day12/`:
  - `panel-data-audit-12.1.json`
  - `panel-aware-protocol-12.1.json`
  - `panel-aware-comparison-12.1.json`
  - `panel-aware-structural-errors-12.1.json`
  - `panel-aware-summary-12.1.json`
- Updated `ai-workflow/REPORT.md` and workflow state for Reviewer handoff.

No production module, Human GT, Day 11 artifact, or approved 12.0 artifact was modified.

## C. Architecture/logic

### Panel-data hard gate

The corrected audit inventories all ten pages and all 63 persisted logical regions (50 Human-ordered plus 13 Human-excluded, though Human disposition is not used during the audit). It checks five non-Human prediction sources plus the forbidden manual-analysis source classification:

- `reader-logical-region-sample-11.11.json`: every logical region has `panel_id = PAGE_FALLBACK`; no panel bbox/polygon.
- `reader-v2-correctness-review-sample-11.11.json`: every page has one `predicted_groups` entry named `PAGE`; no group geometry.
- `reader-v2-final-scale-11.17.json`: every relevant emitted region has `predicted_group_id = PAGE`; no panel geometry field.
- `reader-v2-scale-40p-11.10.json`: for every page, `diagnostics.panel_count = 0`, exactly one page-wide `group_assignments` record, `panel_source = page_fallback_no_panel_hierarchy`, and `panel_order = [PAGE]`; no panel geometry.
- `reader-v2-scale-cache-11.10.json`: cached results for every page independently retain `panel_source = page_fallback_no_panel_hierarchy` and `panel_order = [PAGE]`; no panel geometry.

Every source is classified with artifact path, field location, record count, geometry type, provenance, real-panel status, assignment feasibility, and candidate-input usability. All five system sources classify as `PAGE_LEVEL_FALLBACK`; the 12.0 manual visual relationship evidence classifies `HUMAN_DERIVED_FORBIDDEN` for runtime purposes.

Per-page result is identical: predicted panel count excluding fallback = 0, confidently usable panels = 0, potentially assignable regions = 0, and every logical region lacks a usable panel. The known-failure-page gate is 0/3 usable; the control-page gate is 0/7 usable. Panel geometry is persisted/replayable only as the fact that fallback was used, not as structure capable of containment or ordering.

The gate therefore fails before Phase 2. Implementing containment, partial intersection, panel ordering, or fallback assignment would fabricate unavailable structure and violate GT isolation.

### GT leakage protections

The panel audit is generated using only the five non-Human prediction artifacts. It does not load Human click order. Checkpoint 12.0 manual visual evidence is explicitly classified `ANALYSIS_ONLY_FORBIDDEN_RUNTIME_INPUT` and is not loaded as prediction input. The audit and protocol are written and SHA-256 frozen before the frozen Human control is loaded for evaluation-only reproduction. Protocol records `gt_runtime_features: []`, no Human/manual panel input, all five exact input hashes, and the script code hash.

### Frozen control

After pre-score artifacts are frozen, control scoring reproduces exactly: 7/10 exact pages, 43/50 exact positions, 120/124 correct pairs (96.77%), and four inversions. The prior control delta remains 3 improved, 7 unchanged, 0 regressed, and Page 3 remains exact. The rule stays normalized vertical overlap `>= 0.50`, `BENCHMARK_FITTED`.

### Candidate and structural results

- Candidate implemented: no.
- Candidate Human metrics: `N/A`.
- Text-to-panel assignment: not run; structural capacity is 0 confident assignments and 63 regions without usable panel geometry.
- Panel order: not run; zero predicted panels have geometry or adjacency.
- Page 15/Page 17/Page 38: `NOT_RUN`; the four known inversions cannot be classified as repaired/unchanged by a candidate because no legitimate candidate exists.
- Regressed pages/new inversions: `N/A`, not zero—claiming zero would imply an evaluation that did not occur.
- Synthetic panel tests: not applicable after hard-stop; only audit/gate/NOT_RUN tests were added.

This is outcome B rather than D because 12.0 provides evidence that panel structure is the plausible missing mechanism, while 12.1 precisely identifies predicted panel detection/representation and subsequent assignment as the unavailable prerequisite.

## D. Tests

- Focused panel-audit plus existing Reading Order/12.0/final-contract/fast-pass tests after reviewer fix: 34/34 PASS.
- The first focused run had one incorrect new assertion expecting 50 inventory regions; audit correctly counted all 63 logical regions. The assertion was corrected to distinguish total logical inventory from the 50 Human-ordered scoring subset, then all focused tests passed.
- Canonical backend suite after reviewer fix: 343/343 PASS in 2.793 s.
- Python compilation: PASS.
- Five 12.1 JSON artifacts plus expanded 11.10 per-page provenance, input hashes, gate, hash-freeze, baseline, GT-isolation, and resource invariants: PASS.
- Workflow validation in `REVIEW_FAILED` fix state: PASS.
- `git diff --check`: PASS.

## E. Benchmark if allowed

Only the permitted read-only panel inventory and deterministic frozen-control reproduction ran. No panel candidate benchmark ran. OCR calls = 0, VLM calls = 0, Ollama calls = 0. Resource Guard remained `NORMAL`.

## F. Regressions

No production behavior changed and no candidate output exists. Frozen baseline reproduction remains exact. Historical artifacts and Human GT remain unchanged. Candidate regressions are correctly `N/A` rather than inferred as zero.

## G. Remaining limitations

- Current persisted structure cannot test panel containment, text-to-panel assignment, panel adjacency/order, cross-panel hierarchy, or ambiguity behavior.
- `PAGE`/`PAGE_FALLBACK` is not a predicted panel and must not be counted as one.
- Human/manual visual evidence could describe panels but is prohibited as candidate runtime input.
- New Human GT is not justified; the missing evidence is technical non-Human panel geometry, not another click-order label.

Recommended next experiment, only after Human approval: an isolated deterministic panel-structure extraction benchmark on these same ten source pages. It should produce non-Human panel bbox/polygon geometry with provenance and ambiguity, without reading Human click order, then rerun the 12.1 data gate. No OCR/model inference should be assumed without separate permission.

## H. Git diff summary

12.1 changes are limited to one offline audit script, one focused test module, five JSON artifacts, and workflow documents. The review fix only expanded persisted-source coverage and tests. Existing uncommitted 12.0 checkpoint files/history remain preserved. No commit or push was performed.
