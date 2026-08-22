# Checkpoint 11.16 — Independent Review

## Verdict

**PASS**

## Evidence

- Frozen 11.11 control was independently recomputed from the ten stored page sequences: 6/10 exact pages, 37/50 exact positions, 116/124 correct pairs, and eight inversions. The stored frozen SHA-256 (`ddf52c…fb2`) matches the current 11.11 comparison artifact; the preserved 11.9 artifact also matches its recorded SHA-256 (`0762f2…592`).
- The production `tiered_order` implementation confirms the documented control behavior: `[x1,y1,x2,y2]` boxes, mean tier-center comparison, `max(4 px, min(item height, maximum tier-member height) * 0.5)`, no overlap signal, insertion/top tier order, and manga right-to-left peer order.
- All eight inversion pairs were independently derived and match the audit exactly. The geometry-only taxonomy totals five tall-region interference, one different-row merge, one vertical-overlap ambiguity, and one same-row misclassification. No Human panel/tier oracle exists, so exact group structure, same-tier accuracy, merge count, and split count are correctly reported as `N/A`, not inferred.
- Candidate definitions are deterministic and isolated: A overlap >= 0.50, B normalized center distance <= 0.50, and C the disclosed overlap/center hybrid with 1.8x tall-box protection. The declaration protocol hash recomputes to `f14cebd…95ec`; all candidates use bbox geometry only and `gt_runtime_features` is empty. Human order is used only by scoring/selection after prediction generation. Parameters are honestly labeled benchmark-fitted rather than production-calibrated.
- Independent candidate recomputation matches all artifacts: A = 7/10 pages, 43/50 positions, 120/124 pairs, four inversions, 3 improved/7 unchanged/0 regressed; B = 5/10, 38/50, 117/124, seven inversions, 2/7/1; C = 6/10, 40/50, 118/124, six inversions, 2/7/1.
- Candidate A repairs four audited pairs: three of five tall-interference pairs and the same-row pair. The other two tall cases, different-row merge, and vertical-overlap ambiguity remain. The hybrid's explicit tall protection does not outperform A.
- Page 3 is exact under CONTROL and all three candidates. Leave-one-page-out selection was independently recomputed and selects A in all 10/10 folds. The report appropriately warns that this is a small benchmark-fitted result, not out-of-sample production evidence.
- Runtime arithmetic is correct: 933,625 ns total = 31,120.83 ns/page/candidate and 6,224.17 ns/region/candidate. Resource samples remain NORMAL at about 26.6 MB RSS, about 6.856 GB available memory, and zero swap delta.
- Search and code-path inspection show the candidate service is experiment-only and is not imported into production Reader V2. The benchmark records zero OCR, VLM, and Ollama calls; Human GT, frozen control, production Reading Order, and authoritative state are reported unchanged. No model call was made during review.
- Verdict **A. GEOMETRY FIX PASS** is supported within checkpoint scope: A halves inversions, improves all three correctness metrics, has no page regression, preserves Page 3, and wins every page-grouped leave-one-out fold. The recommended next action is appropriately limited to offline end-to-end Reader V2 integration validation with explicit predicted group geometry and new page-grouped Human validation; it does not authorize deployment.

## Validation

- Focused tests: 18/18 PASS.
- Full backend suite: 327/327 PASS.
- Python compilation: PASS.
- Five 11.16 JSON artifacts parse successfully.
- Workflow validation and `git diff --check`: PASS.
- Diff hygiene: checkpoint additions are isolated to experiment service/script/tests, benchmark artifacts, and workflow documents; no commit or push was performed.

No actionable correction is required. Stop at `AWAITING_HUMAN_APPROVAL`; do not start 11.17 or deploy the candidate.
