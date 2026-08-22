# Checkpoint 11.6 Independent Review

## Verdict

PASS

## Human GT and scope audit

Persisted state was independently checked before inference: 20 TOTAL/VERIFIED and
zero in every other state. VERIFIED export revalidates human provenance, GT row,
full image hash and crop hash; all 20 passed. Human transcription is read-only.
No AI-cleaned text is used as oracle.

Exactly EasyOCR and cached PP-OCRv6 small were run once, sequentially at
concurrency one. Engine results disclose `measured_this_run`; the older cached
outputs belong to different samples, so reuse was not possible. Production OCR is
unchanged, Paddle remains benchmark-only, and no router/VLM repair/Reader V2
implementation, third engine, frontend change, 11.7 work, commit or push exists.

## Metric and signal validity

- Per-sample artifacts bind identical source/crop identity and retain GT, raw OCR,
  confidence, raw/normalized CER and normalized edit similarity.
- Correctness classes CER==0, <=0.05 and <=0.10 are separate. On this data all
  three yield the same counts, which is reported rather than hidden.
- Similarity uses case-folded NFC/whitespace-normalized edit distance without
  deleting punctuation/diacritics.
- Sanity flags use OCR output only. They do not inspect GT and therefore do not
  leak correctness into routing.
- All 52 rule/threshold combinations report N, accepted/correct/false-safe counts,
  safe-accept rate, false-safe rate over all regions, HARD rate, EASY precision and
  correct-region coverage. Empty-accept rules cannot win selection.
- High-agreement/both-wrong, both-engine outcomes and false-confidence examples
  are explicit. No dangerous agreement-wrong event was observed, but the report
  correctly refuses to infer safety from one high-agreement sample.
- Thresholds are labeled BENCHMARK-FITTED and the report discloses train/evaluate
  reuse of the same N=20 data.

## Routing decision audit

Paddle confidence >=0.90/0.95 observed 2 correct EASY and zero false-safe, but
routes 90% HARD. Agreement accepts only 1/20. Easy confidence >=0.80 accepts two
wrong samples. Meanwhile 18/20 are wrong for both recognizers. Decision
`D. NO SAFE ROUTER YET` follows the false-safe-first contract and is more justified
than A/B/C; it is not a predetermined preference.

Fixed-rule leave-one-out retains zero observed false-safe but only 1–2 accepted
samples, correctly exposing dependence on two positives. The analysis does not
misrepresent this as independent calibration.

## Performance, resources and structural separation

Warm dual sequential cost and Easy-only cost derive directly from the measured
engine artifacts. The 4.29× warm multiplier is correct. Cold initialization and
total times remain separate. Page projections use the measured 20 regions/3 pages,
are explicitly OCR-only projections, and do not include VLM/repair.

Both resource artifacts show NORMAL state and zero swap delta. Paddle's process
peak is correctly disclosed as including prior library/process residency from the
sequential run. VLM/Ollama calls are zero.

The report clearly separates crop transcription from detection/bubble/panel
structure and identifies the line-recognizer versus multiline logical-crop mismatch
as a likely upstream experiment—not as a routing solution.

## Required comparison questions

All twelve questions are answered across A–AF: Paddle is slightly more accurate;
Easy is faster warm; wins/both outcomes are counted; confidence/agreement/combined
signals are compared; best observed tradeoff and dual cost are explicit. Language
unknown samples are not mislabeled as English.

## Verification

- Full backend suite: 253/253 passed.
- Focused similarity, routing metrics, sanity, threshold and cache tests passed;
  existing 11.5 tests cover VERIFIED/hash loading and zero review model calls.
- Python compilation passed.
- Four required 11.6 artifacts parse and each has N=20.
- Workflow validation at IMPLEMENTED passed.
- `git diff --check` passed.

## Required fixes

None.
