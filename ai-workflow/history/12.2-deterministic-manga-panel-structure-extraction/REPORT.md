# Checkpoint 12.2 — Deterministic Manga Panel Structure Extraction

## A. What changed

Implemented one isolated offline deterministic hybrid panel extractor and ran its single predeclared configuration on the same ten hash-verified manga pages. The pixel-only extractor combines recursive whitespace-gutter partitioning, border/contour evidence, page-edge support, deterministic candidate fusion, nested/duplicate suppression, explicit ambiguity, and spatial adjacency metadata. It does not integrate with Reader or Reading Order.

The run produced some structurally useful candidates but no independent panel labels exist to measure their correctness. Checkpoint outcome: **D. PANEL CORRECTNESS CANNOT BE EVALUATED YET**.

### Review-failure fix

Independent review correctly failed the first handoff because the protocol claimed `page_edge_completion` while the extractor only accepted and labeled already closed edge-touching panels. The focused fix adds actual completion from three agreeing straight borders: the two perpendicular borders must terminate within a scale-normalized tolerance of the same page edge, and the opposing border must join their endpoints within a separate normalized tolerance. The page boundary supplies exactly the missing fourth side. Completion records the completed side and all three supporting line segments in provenance/evidence. Insufficient or conflicting edge evidence remains ambiguous/unresolved.

Corrected synthetic coverage now removes the page-facing border at each of LEFT, RIGHT, TOP, and BOTTOM, verifies the raw closed-contour detector does not already produce the intended bbox, then verifies deterministic completed geometry, `DETECTED` state, and `page_edge_completion` provenance. A negative fixture with weak edge-touching line/artwork evidence does not produce a completed detected panel.

## B. Files changed

- Added offline extractor: `backend/app/services/deterministic_panel_extractor.py`.
- Added offline runner: `scripts/panel_extraction_12_2.py`.
- Added focused synthetic/artifact tests: `backend/tests/test_deterministic_panel_extractor.py`.
- Added seven required 12.2 JSON artifacts under `benchmarks/day12/`.
- Updated this report and workflow state for Reviewer handoff.

No production caller, Reader, Reading Order, OCR, R2, Repair Boundary, Story, database, API, frontend, Human GT, or historical artifact was modified.

## C. Architecture/logic

### Inputs and leakage boundary

All ten images were resolved uniquely under `backend/uploads/` by the immutable source hashes in `reader-logical-region-sample-11.11.json`; filenames were not trusted. The extractor API accepts only an image pixel array and optional fixed configuration. It cannot accept text regions, Human order, or manual panel evidence.

The input audit and protocol were written first. Two pixel-only prediction passes then produced identical semantic SHA-256 hashes, and the prediction artifact was persisted and hashed before logical-region geometry or the 12.0 manual audit was used. Logical bboxes were used only afterward for containment usefulness. The 12.0 evidence was first opened after freeze and only for qualitative Page 15/17 diagnostics. `gt_runtime_features` is empty throughout.

### Extractor and states

The fixed configuration uses scale-normalized, synthetic/domain-derived constants labeled `PREDECLARED_SCALE_NORMALIZED_NOT_BENCHMARK_FITTED`. The fix adds only normalized terminal/join tolerances justified by the four synthetic edge orientations; no real-page tuning, parameter sweep, or page-specific condition ran.

Panel candidates contain stable geometry-derived IDs, pixel and normalized bboxes, optional contour polygons, `DETECTED`/`AMBIGUOUS` state, provenance, uncalibrated structural evidence, page-edge flags, overlap conflicts, and relative-position adjacency. Only multi-source candidates or multi-leaf whitespace partitions without conflicts become `DETECTED`; weak single-source or conflicting candidates remain `AMBIGUOUS`. A page with no detected panel is `UNRESOLVED` and uses explicit page fallback, which never counts as a panel.

### Ten-page result

- Pages with detected structure: 6/10 (Pages 2, 3, 4, 7, 18, 38).
- Detected panels: 7.
- Ambiguous candidates: 49.
- Unresolved pages / PAGE_FALLBACK rate: 4/10 / 40% (Pages 1, 5, 15, 17).
- Raw candidates: 71; nested/duplicates suppressed: 15.
- Logical regions uniquely contained by a detected panel: 9/63.
- Logical regions unassigned: 54/63.
- Multi-contained and boundary-intersection regions: 0 in this run.
- Adjacency edges: 114 total, split in the artifact into usable detected-to-detected versus ambiguity-tainted edges.
- One real-page detected panel now includes independently derived `page_edge_completion` provenance. It fused with its existing structural candidate, so aggregate panel/state/containment counts did not change.

This demonstrates nonzero Reader-relevant containment but not panel correctness. The high ambiguity/unassigned rates and absence of an oracle prohibit outcome A. It is outcome D rather than C because independent predictions produce seven detected structures and nine unique containment assignments, but their correctness cannot be established without labels.

### Pages 15 and 17

Both pages are `UNRESOLVED`. Their known failure-region bboxes have no detected-panel owner. Post-freeze diagnostic status is `UNRESOLVED` for Page 15 and Page 17; no Reading Order was run or scored, and predictions were not changed after inspection.

### Human validation decision

A separately approved minimum four-page panel validation gate is justified: Pages 15 and 17, one detected control page, and one additional ambiguous/unresolved control. Human annotators would mark panel bbox/polygon and genuine structural ambiguity only—no OCR or Reading Order GT. Those labels would unlock panel precision/recall/IoU, over/under-splitting analysis, and the decision whether Reader integration is justified.

## D. Tests

- Synthetic extractor tests after the fix: 11/11 PASS. The page-edge completion test contains four positive subcases (missing LEFT/RIGHT/TOP/BOTTOM page-facing border); the separate negative edge-content case also passes. The suite additionally covers 2x2, right/left, upper/lower, tall beside stacked, narrow gutter, missing non-edge border, overlap ambiguity, rejection, provenance, repeatability, and pixels-only isolation.
- Focused checkpoint plus Reader/Reading Order/12.0/12.1 regression selection: 49/49 PASS in 0.349 s.
- Canonical backend suite after the page-edge fix: 358/358 PASS in 2.957 s.
- Python compilation: PASS.
- Seven JSON artifacts, ten-page completeness, 63-region reconciliation, unsupported accuracy `N/A`, deterministic repeat, zero model calls, and Resource Guard NORMAL: PASS.
- The original implementation's first synthetic run was 9/10: the narrow-gutter fixture accidentally left fewer white pixels than the declared scale-normalized minimum after border thickness. The fixture—not the threshold—was corrected. Reviewer then exposed the separate page-edge-completion coverage gap; that FAIL is preserved in `REVIEW.md` and resolved by the implementation and 11-test suite described above.

## E. Benchmark if allowed

Reran exactly the same single deterministic approach twice on the approved ten images after the focused fix. Both fixed runs produced semantic hash `b52a3a7371b9e92542ae243db239f58d12bcefa284f90b538873102864fb051d`. The hash legitimately differs from the pre-fix output because page-edge-completion evidence/provenance is now meaningful output; aggregate metrics remain 6 pages, 7 detected, 49 ambiguous, 4 unresolved, 9 contained, and 54 unassigned. No OCR, VLM, Ollama, paid/local model, or Reading Order benchmark ran. Calls = 0/0/0; Resource Guard remained `NORMAL`.

## F. Regressions

No production behavior changed because the module has no production caller. Existing Reader/Reading Order focused regressions and the backend suite passed. Historical artifacts and Human GT were unchanged.

## G. Remaining limitations

- Correctness cannot be measured without independent panel labels; precision, recall, and IoU are explicitly `N/A`.
- Pages 15 and 17 remain unresolved, so this prototype does not yet supply the structure needed for their known cross-panel failures.
- Only 9/63 logical regions are uniquely contained; 49 ambiguous candidates and 54 unassigned regions show weak real-page coverage.
- Borderless, broken-border, artwork-crossing, nested/inset, irregular, and true-overlap layouts remain risky.
- Heuristic evidence is not a calibrated probability; the configuration is not production-calibrated.
- Reader integration must not begin until a separate Human-approved validation gate establishes panel correctness.

## H. Git diff summary

Checkpoint changes are limited to one offline service module, one runner, one test module, seven new 12.2 artifacts, and workflow documents. Existing uncommitted 12.0/12.1 work and history were preserved. No commit or push was performed.

## Post-Human Frozen Correctness Evaluation

### A. What changed

Added an evaluation-only deterministic one-to-one bbox matcher and compared the unchanged frozen predictions with the independently validated 15-panel Human GT. Verdict: **B. PANEL EXTRACTION PARTIALLY VALID — DETERMINISTIC FIXES REQUIRED**.

### B. Files changed

- Added `backend/app/services/panel_correctness_evaluator.py`.
- Added `scripts/panel_correctness_evaluation_12_2.py`.
- Added `backend/tests/test_panel_correctness_evaluator.py`.
- Added non-overwriting protocol and result artifacts under `benchmarks/day12/`.

### C. Architecture/logic

The primary evaluation matches `DETECTED` predictions one-to-one to Human panels by maximum eligible cardinality, then maximum total bbox IoU, with a fixed evaluation-only IoU convention of 0.50 and stable ID tie-breaking. `AMBIGUOUS` candidates are matched and reported separately; they are never promoted into precision/recall. Structural coverage relations qualify IoU matches that under-split multiple Human panels or over-split one Human panel.

### D. Tests

Focused tests cover deterministic one-to-one behavior, duplicate handling, DETECTED/AMBIGUOUS isolation, under/over-split relations, and threshold inclusivity. Two clean evaluation writes must remain byte-identical. Human GT, frozen prediction hashes, JSON invariants, workflow, and diff checks are revalidated.

### E. Benchmark if allowed

No detector benchmark or inference ran. This is comparison-only against the approved GT. The two DETECTED panels are both correct on Page 2 (precision 1.0, recall 0.133333, F1 0.235294; IoUs 0.918092 and 0.978158). Thirteen Human panels are missed by DETECTED output. Twelve Human panels have IoU-eligible AMBIGUOUS matches, but two are under-split; ten are structurally clean full-panel candidates. Three of four pages are unresolved.

### F. Regressions

Human GT, detector code, frozen predictions, Reader, Reading Order, OCR, and production behavior are unchanged. OCR/VLM/Ollama calls remain 0/0/0.

### G. Remaining limitations

The 15-panel set is sufficient to select a fusion/classification direction, not a production-calibrated threshold. DETECTED precision is based on only two predictions. Panel correctness does not establish panel-order correctness.

### H. Git diff summary

Changes are isolated to the pure evaluator, offline runner, focused tests, new evaluation artifacts, and this report. No commit or push was performed.
