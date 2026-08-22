# Checkpoint 11.7 Report — Line-Aware Crop & Text Reconstruction

## A. Outcome
Completed the bounded EasyOCR-only A/B/C experiment on exactly 20 frozen human-VERIFIED samples. Decision: **B. LOGICAL-REGION CROP HELPS, LINE-AWARE DOES NOT**.

## B. Dataset integrity
All 20 sample IDs, human GT values, image hashes and crop hashes were reused. Authoritative persisted-state hashes matched before/after; no GT or production data was written.

## C. Mode A
Reused exact cached 11.6 EasyOCR whole-region line-recognizer results; no Mode A inference.

## D. Mode B
Ran one EasyOCR instance sequentially with detection+recognition on logical-region crops at 0/2/5/8% padding; detected lines were deterministically sorted and joined.

## E. Mode C
Recognized persisted line boxes separately at winning 2% padding, ordered top-to-bottom with left-to-right ties, then joined without semantic repair.

## F. Padding selection
Mean normalized CER: 0%=0.11739, 2%=0.11038, 5%=0.12781, 8%=0.12100. The bounded winner was 2%.

## G. Current accuracy
Mode A: exact 1/20, micro raw CER 0.97493, mean normalized CER 0.82072, WER 0.93333, missing 0.

## H. Logical-crop accuracy
Mode B: exact 4/20, micro raw CER 0.22714, mean normalized CER 0.11038, WER 0.40558, missing 0.

## I. Explicit line-mode accuracy
Mode C: exact 4/20, micro raw CER 0.23746, mean normalized CER 0.12648, WER 0.47009, missing 0.

## J. CER change
B reduced normalized CER by 0.71034 absolute/86.55% relative versus A. C reduced it by 0.69424/84.59%, but was 0.01609 worse than B.

## K. Per-sample deltas
B and C were each improved on 18, unchanged on 2, regressed on 0 versus A; no severe regression.

## L. Exact-match change
Both candidates moved normalized exact matches from 1 to 4 (+3), but remained wrong on 16/20.

## M. Edit profile
A: 0 insertions/622 deletions/39 substitutions. B: 6/14/134. C: 11/11/139. The original path's deletion-dominant failure largely disappeared.

## N. Geometry diagnostics
Observed 18 multiline regions, 20 exact-union zero-margin crops (`CROP_TOO_TIGHT`), and one persisted-versus-geometric line-order mismatch.

## O. Failure attribution
Observed evidence suggests crop geometry for 18 samples, recognition for 1, and insufficient evidence/no baseline failure for 1; this is not causal proof.

## P. Reconstruction order
Deterministic key: vertical center, left edge, stable line ID. Nonempty outputs are joined with one space.

## Q. Provenance
Artifacts retain source/sample identity, logical/line/crop boxes, padding, raw lines, order, engine/version, preprocessing, latency and cache identity.

## R. Cache behavior
A is `CACHED_11.6`; B/C are `MEASURED_THIS_RUN`. Keys include source hash, bbox, padding, engine version, mode and preprocessing.

## S. Runtime
Initialization 1.31604 s; B winner 0.79454 s; C 0.43539 s. Full B grid: 0.80195/0.79454/0.84551/0.89559 s.

## T. Resource Guard
NORMAL before/after. Available memory 8,017,543,168→7,084,638,208 bytes; peak RSS 1,329,610,752; swap delta 0; concurrency 1.

## U. Model-call safety
VLM/Ollama calls: 0. No Story, Vision, Dialogue, Script, Paddle or third engine ran.

## V. Decision rationale
Logical-crop detection materially beats A. Persisted-line C adds no benefit over B and is slightly worse on CER/WER, so decision A would overstate evidence.

## W. Production impact
None. Production OCR, prompts, routing and safety thresholds remain unchanged.

## X. Artifacts
Added the four required 11.7 sample, comparison, crop-diagnostic and performance JSON artifacts under `benchmarks/day11/`.

## Y. Implementation files
Added `scripts/reader_line_aware.py` and `backend/tests/test_reader_line_aware.py`; only active workflow documents changed beyond cumulative earlier-checkpoint work.

## Z. Focused tests
5/5 pass: padding/bounds, order/reconstruction, cache identity, delta classification and A/B decision semantics.

## AA. Full tests
Full backend suite passes 258/258 in 2.382 s.

## AB. Validation
Python compile, four-artifact JSON assertions and `git diff --check` pass. Workflow validation is run after state transitions.

## AC. Benchmark incident
The first pass completed inference but JSON serialization failed on NumPy polygon integers; authoritative state stayed unchanged. Coordinates were converted to floats and the exact permitted experiment was rerun once. No extra mode/engine was added and it was not rerun for prettier results.

## AD. Regressions
No measured sample regression versus A, swap growth, CRITICAL state or persisted-state mutation. Production behavior was unchanged.

## AE. Limitations
N=20 from one project/three pages; padding selection and evaluation share this small set. Tags do not prove causality, timing is one CPU/macOS run, and exact match remains 4/20.

## AF. Recommendation
For a later human-approved checkpoint, prefer logical-region `readtext` with bounded 2% padding as the measured candidate; validate broader GT before production use. Do not promote Mode C.

## AG. Git/workflow status
No commit/push. The worktree includes cumulative approved/uncommitted earlier changes plus 11.7. Stop after independent review at human approval; 11.8 has not begun.
