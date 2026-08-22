# Checkpoint 11.4 Report — OCR Error Characterization

## A. Dataset

Repository-wide authoritative inventory found three human-verified GT rows. One
old row cannot be benchmarked because its source image no longer exists. The
reproducible dataset therefore contains the same two accessible crops plus a
20-region future-human-transcription queue. No label was invented.

## B. Ground Truth sources

Only `DialogueGroundTruth.verified_text` records produced through human review.
AI text, raw OCR, clean dialogue, Story, and visual guesses were excluded.

## C. Sample count

2 benchmarkable, 1 verified-but-unavailable due to missing source image, and 20
audit-important regions requiring future human transcription.

## D. Difficulty distribution

One multiline/punctuation-heavy sample and one short-text sample. These objective
tags are counts only; each subgroup is N/A for accuracy due to n<3.

## E. Language distribution

Vietnamese: 2. English/mixed language: 0. English comparison is N/A.

## F. Text-role distribution

Speech bubble: 2. Narration and other roles have no trusted transcription sample.

## G. EasyOCR configuration

EasyOCR 1.7.2, `vi,en`, `gpu=False`, CPU/PyTorch, direct recognizer on a fresh
instance, concurrency one. All results are `measured_this_run`.

## H. PaddleOCR configuration

PaddleOCR 3.7.0/PaddlePaddle 3.2.1, cached `PP-OCRv6_small_rec`, CPU/Paddle
Inference, concurrency one. No download/install; benchmark-only.

## I. Preprocessing equality

Both receive the exact same source image bbox and RGB crop pixels. EasyOCR's
recognizer API requires grayscale conversion; Paddle receives RGB. This forced
adapter difference and each preprocessing-specific cache key are recorded.

## J. Detection recall

N/A for crop recognition. Separate 11.3 Mode A evidence remains 21/21 known-region
recall for both engines. It is not reused as a 11.4 crop detection claim.

## K. Exact match

Raw and case-normalized exact match: EasyOCR 0/2; PaddleOCR 0/2.

## L. EasyOCR CER

Micro raw CER 0.9714 over 35 reference characters (n=2).

## M. PaddleOCR CER

Micro raw CER 0.9143 over 35 reference characters (n=2).

## N. Normalized CER

Evaluation normalization is NFC, collapsed whitespace, and case-folding while
preserving punctuation/diacritics. Mean normalized CER: EasyOCR 0.8333; PaddleOCR
0.6667. Raw and normalized results are stored separately.

## O. WER

Mean WER is 1.0 for both (n=2); word-level conclusions are unsupported.

## P. Insertions

EasyOCR 1 (rate 0.0286); PaddleOCR 0 (n=2, 35 reference characters).

## Q. Deletions

EasyOCR 31 (0.8857); PaddleOCR 30 (0.8571). Multiline crop recognition dominates
these deletion counts because a line recognizer is given a logical-region crop.

## R. Substitutions

Both engines: 2 (0.0571).

## S. Missing text

Both returned non-empty strings on 2/2; missing-text rate 0. This does not imply
useful transcription—the long crop collapsed to `9`/a CJK character.

## T. Error taxonomy

EasyOCR: substitution 2, deletion 1 sample, insertion 1 sample. PaddleOCR:
substitution 2, deletion 1, language confusion 1, diacritic error 1. No source was
human-labeled unreadable. Structural `MERGED_TEXT`/`SPLIT_TEXT` remains separate.

## U. Vietnamese comparison

Paddle has lower measured raw/normalized CER on the two Vietnamese samples, but
n=2 is insufficient to say it is the better Vietnamese engine.

## V. English comparison

N/A: zero trusted English samples.

## W. Confidence calibration

EasyOCR placed both wrong results below 0.60. Paddle placed one wrong result below
0.60 and the wrong `Háy` result in 0.80–0.90. No bucket has sufficient n for
calibration. Confidence alone cannot safely route EASY/HARD.

## X. High-confidence errors

At ≥0.90, none occurred in this two-crop run. A materially confident error still
exists at 0.8597 (`Hây`→`Háy`). The 11.3 full-page evidence also warned that high
confidence is not correctness; thresholds remain analysis-only.

## Y. OCR agreement analysis

Agreement rate 0/2. Agreement+correct 0, agreement+incorrect 0, disagreement+Easy
correct 0, disagreement+Paddle correct 0, disagreement+both wrong 2. There are no
agreement cases, so whether agreement is a stronger signal is N/A.

## Z. Both-wrong analysis

Both engines were wrong on 2/2 disagreements. Both-confidently-wrong at the
explicit ≥0.90 rule: 0. The sample count cannot estimate a rate.

## AA. Structural segmentation findings

11.4 measures transcription only. 11.3 separately found 19 logical bubble
over-splits and 0 merges for each engine, with only 2 one-to-one matches. Current
failure therefore includes both transcription errors and unresolved line-to-bubble
segmentation; neither may be hidden behind one OCR score.

## AB. Performance/resources

EasyOCR: cold init 2.3495 s, warm crops 0.0220 s total/0.0110 s mean, total 2.3715
s, peak RSS 1,054,277,632 bytes. Paddle: cold init 1.8355 s, warm crops 0.0466 s
total/0.0233 s mean, total 1.8821 s, peak RSS 1,106,952,192 bytes. Paddle initialized
faster but crop inference was slower on n=2, so “Paddle is faster” is not a general
claim. Both had zero swap delta and NORMAL safety. Page latency is N/A. VLM calls: 0.

## AC. Decision

D. INSUFFICIENT EVIDENCE — MORE HUMAN GT REQUIRED

Production remains EasyOCR. Paddle is not ready for a Reader V2 decision, and a
hybrid strategy is not justified by two disagreements where both engines failed.

## AD. Recommendation for 11.5

Obtain human transcription for the 20 queued audit regions (including narration,
clean/multiline/small/punctuation cases) and add trusted English samples before any
routing experiment. Restore the missing historical source only from an
authoritative user-owned copy. Do not use AI-cleaned text as GT.

## Limitations

The intended expansion was blocked by source-of-truth scarcity: only two crops are
reproducible. Difficulty, language, role, confidence, and agreement subgroups are
therefore descriptive or N/A. Cache keys are implemented and every inference is
marked measured; no prior cached result was silently reused. Authoritative
Asset/GT/Story/review/Script hashes were identical before/after each run.

## Files and validation summary

Added one isolated 11.4 runner, pure metric/error helpers and tests, five JSON
artifacts, and workflow documents. Production OCR code is unchanged. Full backend
tests passed 243/243; Python compilation, five-artifact JSON/schema validation,
workflow validation, and `git diff --check` also passed.
