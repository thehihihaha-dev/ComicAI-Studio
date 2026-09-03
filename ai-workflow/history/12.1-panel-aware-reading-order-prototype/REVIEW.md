# Checkpoint 12.1 — Independent Re-review After Fix

## Verdict

**PASS**

Independent checkpoint outcome: **B. PANEL DETECTION/ASSIGNMENT IS THE BOTTLENECK**.

## Independent evidence

- Direct inspection of `reader-v2-scale-40p-11.10.json` and `reader-v2-scale-cache-11.10.json` independently resolves all ten benchmark asset identities. For every page, scale diagnostics record `panel_count = 0` and exactly one `group_assignments` entry named `PAGE`; scale and cache reading-order details both record `panel_source = page_fallback_no_panel_hierarchy` and `panel_order = [PAGE]`.
- These records are correctly classified `PAGE_LEVEL_FALLBACK`. They are system-generated and replayable, but contain no panel bbox/polygon, real panel boundary, containment, adjacency, or within-page panel sequence. They cannot support text-to-panel assignment or serve as a legitimate panel-aware candidate input.
- The expanded audit now hashes both 11.10 artifacts and records their actual per-page fields/provenance alongside the 11.11 logical/review and 11.17 final-contract fallback evidence. All five system sources agree; no conflicting predicted panel geometry exists in the frozen benchmark artifacts.
- All ten pages have zero usable predicted panels. The audit accounts for all 63 logical regions, and every region lacks a structural parent capable of panel assignment. The known-failure gate is 0/3 usable and control gate is 0/7 usable.
- The audit loads only non-Human prediction artifacts before freezing the audit/protocol hashes. It does not load Human click order during panel inventory; `gt_runtime_features` is empty; 12.0 manual visual relationships are explicitly forbidden runtime evidence and are not used to construct panels, assignments, or candidate output.
- The hard stop is correct. Phase 2 would require fabricated structure or leakage from manual/Human evidence. No candidate was implemented, so candidate metrics, regressions, Pages 15/17 results, and four-inversion changes remain honestly `N/A`/`NOT_RUN`.
- The frozen control independently remains 7/10 exact pages, 43/50 exact positions, 120/124 correct pairs (96.77%), and four inversions; Page 3 remains exact and the overlap `>= 0.50` rule remains `BENCHMARK_FITTED`.
- Outcome B is supported rather than C: panel-aware ordering was never reached. It is supported rather than D because 12.0 already establishes the cross-panel failure hypothesis and the expanded audit precisely identifies missing predicted panel detection/representation as the prerequisite.
- The smallest next experiment, if Human-approved, is offline deterministic panel-structure extraction on the same ten source pages. It should ask whether ComicAI can produce non-Human panel bbox/polygon geometry with provenance and ambiguity before rerunning this gate. New Human click-order GT is not needed yet; any later panel-detection GT request requires separate justification.

## Validation rerun

- Focused panel-audit/Reading Order/12.0/final-contract/fast-pass tests: 34/34 PASS.
- Canonical backend suite: 343/343 PASS in 3.100 s.
- Python compilation: PASS.
- Five 12.1 JSON artifacts, expanded per-page 11.10 provenance/input hashes, pre-score hash freeze, baseline, GT isolation, and gate invariants: PASS.
- Workflow validation in `FIXED` state: PASS.
- `git diff --check`: PASS.
- Resource Guard NORMAL; OCR/VLM/Ollama calls 0/0/0.
- No production Reader/OCR, Human GT, Story, R2, Repair Boundary, or historical artifact changed. No model inference, commit, or push occurred.

The previous blocker is fully resolved. Stop at `AWAITING_HUMAN_APPROVAL`; do not start panel extraction or another checkpoint.
