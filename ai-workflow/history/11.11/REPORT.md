# Checkpoint 11.11 — Post-Human Correctness Report

## A. Human GT completeness
The current manifest resolves exactly 10 versioned source/representation pairs: 10 VERIFIED, 0 PENDING, 50 ordered logical regions, 13 explicitly excluded regions, 50 Human transcriptions and 0 unreadable. Every ordered/excluded partition is complete and disjoint; all source hashes are valid. One stale Page 15 row from an earlier representation hash remains preserved and is outside the current manifest.

## B. Preservation
Human click-order GT and Reader prediction occupy separate fields/stores. Prediction artifacts, the 11.9 comparison artifact and authoritative project processing snapshot are byte/state unchanged. Previous fragment/hierarchical Reading Order GT and OCR GT remain present; no conversion or overwrite was performed. Four pages have Human order values different from the scored original prediction.

## C. Reading Order correctness
Original persisted prediction versus Human order, after reporting and removing only Human-explicit exclusions from order scoring: exact page order 6/10 (60%); exact region position 37/50 (74%); pairwise 116/124 (93.55%); 8 inversions; 4 pages requiring correction; 13 moved positions. There are 0 missing prediction regions, 0 extra regions and 0 ambiguous/unresolved regions. Reader prediction treated all 13 Human-excluded regions as readable; these are reported separately rather than scored as Human order elements.

## D. Reading Order errors
Likely deterministic causes across inverted pairs: row grouping 4, top-to-bottom 2, right-to-left 2. Exclusion handling contributes 13 additional errors. The inversion pattern clusters around the shared `tiered_order` row/tier geometry rule rather than page-specific special cases.

## E. OCR correctness
Using only the 50 Human logical-region transcriptions: exact match 10/50 (20%); normalized CER 11.28%; WER 33.81%. Of 44 logical regions whose source fragments were all `ACCEPT_CANDIDATE`, 8 were exact and 36 were false accepts: false-accept rate 81.82%. Six regions were HARD/review; unreadable 0.

## F. OCR error analysis
Observed categories: merged/split fragment reconstruction 28, wrong character 17, missing character/text 16, extra character/text 6 and punctuation 1. Categories may overlap per erroneous region. The dominant operational failure is not merely raw character error: the acceptance signal labels many incorrect reconstructed logical texts safe.

## G. Click-to-order UX
The Human successfully completed all ten pages using only sentence clicks, explicit “Câu này không cần đọc”, optional text correction and page confirmation. All annotations persisted. Mandatory panel/group/fragment editing remains absent.

## H. Resource safety
Resource Guard stayed NORMAL. Swap delta 0. New OCR inference 0; VLM 0; Ollama 0. Analysis reused persisted Fast Pass outputs.

## I. Verdicts
Reading Order: **B. PASS WITH DETERMINISTIC FIXES.** Pairwise behavior is promising, but 40% of pages still require correction and the shared tier/row rule needs one causal fix.

OCR: **B. ROUTER/CORRECTNESS FIX REQUIRED.** The 81.82% observed false-accept rate makes current `ACCEPT_CANDIDATE` unsuitable as a safe routing signal on this Human sample.

## J. Single next action
Redesign and validate the OCR `ACCEPT_CANDIDATE` rule against these observed false-safe logical-region cases before changing the OCR engine. Do not combine this with a geometry or preprocessing experiment; causal attribution should remain isolated.

## K. Tests and limitations
Backend passes 292/292. Python compilation, five-artifact JSON assertions, workflow validation and `git diff --check` pass. No frontend contract changed during post-human analysis. This is a stratified ten-page/50-transcription benchmark and is not a production-accuracy claim.
