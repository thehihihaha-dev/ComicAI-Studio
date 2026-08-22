# Checkpoint 11.6 Report — OCR Routing Signals

## A. Human GT persisted state

TOTAL 20; VERIFIED 20; UNREADABLE 0; SKIPPED 0; SOURCE_UNAVAILABLE 0;
PENDING 0. No human text was modified.

## B. VERIFIED sample count

20/20 human-provenance samples passed current full-image and crop-hash validation
and entered correctness metrics.

## C. Benchmark dataset

Twenty logical-region crops from the existing three-page project, with stable
sample/asset/region identity, bbox, image/crop hashes, human GT, both OCR outputs,
confidence and adapter cache status. All OCR outputs were `measured_this_run`; no
exact prior cache result existed for these 20 queue identities.

## D. Languages

Deterministic character evidence: Vietnamese 15, unknown 5; unknown is not claimed
as English. No supported English-only conclusion.

## E. Text roles

Dialogue 12; narration 8.

## F. EasyOCR accuracy

Normalized exact 1/20 (5%); micro raw CER 0.9749; mean normalized CER 0.8207;
mean WER 0.9333; missing output 0/20. Correct counts remain 1 at CER==0,
CER<=0.05 and CER<=0.10.

## G. PaddleOCR accuracy

Normalized exact 2/20 (10%); micro raw CER 0.9572; mean normalized CER 0.7983;
mean WER 0.9000; missing output 3/20. Correct counts remain 2 at each experimental
CER threshold. Paddle wins narrowly but neither recognizer is adequate on these
logical-region/multiline crops.

## H. EasyOCR latency

Cold init 2.3339 s; warm 20-crop inference 0.1095 s; mean 0.00547 s/region; total
including init 2.4434 s.

## I. PaddleOCR latency

Cold init 1.6643 s; warm inference 0.3606 s; mean 0.01803 s/region; total 2.0249 s.
Paddle has faster cold total here but warm crop inference is 3.29× EasyOCR.

## J. Dual OCR cost

Sequential warm cost 0.4701 s for 20 crops, 4.29× EasyOCR-only warm cost. Full cold
totals sum to about 4.4683 s. Agreement adds cost but observes only one safe exact
agreement, so dual OCR is not justified by current routing value.

## K. Confidence calibration

EasyOCR's sole correct result had confidence 0.6617 while wrong results reached
0.8788. Its confidence≥0.80 experiment accepted 2/20 and both were wrong.
Paddle's two exact results were 0.9902/0.9995; wrong results peaked at 0.8567.
Paddle≥0.90 therefore observed 2 correct/0 wrong, but this is only two positives
and is BENCHMARK-FITTED, not calibrated.

## L. OCR agreement

Mean normalized edit similarity 0.2519. Exact agreement 1/20; high agreement
(similarity≥0.90) 1/20. That one case was correct for both engines.

## M. Agreement-but-wrong cases

High-agreement both-wrong: 0/1 high-agreement cases. The dangerous event was not
observed, but N=1 agreement cannot establish safety.

## N. Both-wrong cases

18/20 were wrong for both at normalized CER==0.

## O. EasyOCR wins

0/20 exact-only wins. Both correct: 1/20.

## P. PaddleOCR wins

1/20 exact-only win. Both correct: 1/20.

## Q. Sanity heuristics

Across paired outputs: suspiciously short 9, unusual-symbol ratio 6, excessive
whitespace 4, empty 3 and cross-engine script mismatch 2. Rules use OCR outputs
only—no GT leakage or aggressive language rejection. Adding sanity filters did
not improve beyond the single high-agreement accepted case.

## R. Router candidates

Evaluated 52 BENCHMARK-FITTED rules: Easy confidence, Paddle confidence, edit
similarity agreement, agreement+dual confidence and agreement+confidence+sanity,
at explicit confidence/similarity grids. Each is recorded for CER==0, <=0.05 and
<=0.10; no production threshold was selected.

## S. FALSE_SAFE comparison

Best nonempty observed Paddle confidence rule (≥0.90 or ≥0.95): false-safe 0/20.
Agreement≥0.90 and combined variants: 0/20. Easy confidence≥0.80: false-safe 2/20
(10%). Lower thresholds admit many incorrect samples; complete grid is in JSON.

## T. EASY coverage comparison

Paddle confidence≥0.90: accepted 2/20, safe-accept 10%, HARD 90%. Agreement and
combined rules: accepted/safe 1/20 (5%), HARD 95%. Easy confidence≥0.80 accepted
2/20 but safe-accept 0%.

## U. EASY precision

Observed Paddle confidence precision 2/2 and agreement/combined precision 1/1;
Easy confidence precision 0/2. These tiny denominators prohibit a safety claim.

## V. Threshold sensitivity

The apparently safe Paddle result exists only above the gap between wrong maximum
0.8567 and correct minimum 0.9902. Agreement value collapses to one accepted sample
at ≥0.90. Conclusions are highly coverage-sensitive and benchmark-fitted.

## W. Leave-one-out/stability

For the fixed best observed rule, leave-one-out false-safe remains 0, but accepted
EASY ranges only 1–2. Omitting either positive removes half the already tiny EASY
set; this is not robust evidence of generalization.

## X. Machine resources

Easy pass peak process RSS 1,077,805,056 bytes; Paddle sequential-pass process peak
1,854,504,960 bytes (includes the process's prior Easy pass/library residency).
Available-memory samples remained recorded; swap delta 0 for both; safety NORMAL.
Concurrency was one.

## Y. VLM call confirmation

0 VLM/Ollama calls. No Story, Vision, Dialogue, Coverage or Script inference.

## Z. Structural limitations

This is transcription routing on known crops. It cannot recover a never-detected
bubble or repair merged/split bubble/panel structure. The dominant deletion/CER
also shows that single-line recognizers are mismatched to many logical multiline
region crops; routing cannot compensate for that adapter/segmentation problem.

## AA. Reader V2 architecture decision

D. NO SAFE ROUTER YET

Paddle is slightly more accurate, and high Paddle confidence looks promising on
only 2 regions, but 18/20 both-wrong and 90% HARD coverage make A/B/C unsafe.
Production remains EasyOCR; no router was deployed.

## AB. 5/10/20/50-page projection

OCR-only warm projections derived from 20 regions across 3 pages (not chapter
measurements, excluding VLM/structure): Easy-only 0.182/0.365/0.730/1.825 s; dual
sequential 0.783/1.567/3.134/7.834 s for 5/10/20/50 pages respectively.

## AC. Files changed

Added pure routing analysis CLI, focused tests and four required 11.6 artifacts;
extended VERIFIED export with persisted state counts/language analysis support;
updated workflow documents. Frontend and production OCR are unchanged in 11.6.

## AD. Tests

Full backend suite passes 253/253. Focused tests cover VERIFIED/hash loading via
existing 11.5 tests plus similarity, confidence/router extraction, false-safe,
safe-accept, hard rate, EASY precision, sanity, threshold evaluation and exact
cache reuse. Python compile, four-artifact JSON validation, workflow validation
and `git diff --check` pass. Analysis itself makes no model calls.

## AE. Limitations

N=20 from one project/three pages; 15 visibly Vietnamese and 5 language-unknown;
no English conclusion. Threshold search and evaluation use the same data. Logical
region crops often contain multiple lines while both underlying recognizers are
line-oriented. Timings are one sequential run and projections exclude detection,
structure and repair. No statistical or production-calibration claim is made.

## AF. Recommendation for Checkpoint 11.7

Do not start a FAST PASS prototype. Investigate a deterministic line-aware crop
adapter/line aggregation experiment and expand diverse human GT before repeating
routing-signal analysis. Keep architecture decision D until cheap OCR correctness
improves materially.
