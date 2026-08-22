# Checkpoint 11.4 Independent Review

## Verdict

PASS

## Scope and production isolation

The checkpoint changes benchmark-only scripts/helpers/tests/artifacts and workflow
documents. Production `ocr_service.py` remains EasyOCR and unchanged. PaddleOCR is
constructed only inside the isolated runner. There are no product DB writes,
production routing, third OCR engine, reading-order/panel work, Story/Dialogue/
Coverage/Script inference, Ollama calls, downloads, commits, pushes, or 11.5 work.

## Dataset and Ground Truth audit

The runner queries all `DialogueGroundTruth.verified_text` rows and never promotes
raw OCR or AI-cleaned text to reference truth. Repository state contains three
human GT rows, but the source image for the older third row is absent. The runner
correctly records it as unavailable rather than substituting another image. The
two reproducible samples are deduplicated by asset/region identity. Twenty
unlabeled audit regions are separated into a future-human-transcription queue and
never enter accuracy metrics.

This does not achieve a statistically substantial expansion, but the user's
explicit fallback requires a manifest rather than fabricated labels when trusted
data are insufficient. The report and exact decision D disclose this limitation.

## Metric and adapter validity

- Both engines receive the same source image and bbox. Required EasyOCR grayscale
  versus Paddle RGB adapter preprocessing is explicit and included in cache keys.
- Raw exact/CER and case-folded NFC/whitespace normalized exact/CER are separate;
  punctuation and diacritics remain meaningful.
- Deterministic edit counts sum to CER distance and expose insertion, deletion,
  and substitution rates against reference characters.
- Error taxonomy correctly flags missing, punctuation, diacritic, case, language
  confusion, and edit-operation classes in focused tests.
- All subgroup outputs include sample count and return N/A below the documented
  minimum of three.
- Confidence uses only analysis buckets. The wrong Paddle `Háy` at 0.8597 is
  retained, and the report rejects confidence-only routing.
- Agreement matrix is exhaustive for the two pairs: both disagree and both are
  wrong. It correctly treats agreement calibration as N/A.
- Crop transcription makes no detection claim. 11.3 region detection and bubble
  over-split evidence are labeled historical and structurally separate.

## Performance, safety, and integrity

Runs were sequential at concurrency one and every result is marked
`measured_this_run`; no hidden cache reuse occurred. Cold initialization, warm
per-region/total latency, RSS/peak RSS, available memory, swap delta, and safety
samples exist for both engines. Both remained NORMAL with zero swap delta and
zero VLM calls. The report avoids a general Paddle speed claim from n=2.

Canonical before/after snapshots cover full Asset OCR/Vision/Dialogue rows,
Ground Truth, Story/review/approval, and Short Script for both relevant projects.
Hashes match in manifest and engine artifacts. Source inspection confirms the
runner never calls database mutation methods.

## Decision and required analysis

The report answers the ten requested questions across A–AD. English is honestly
N/A, dominant errors and both-wrong cases are enumerated, and transcription versus
structure remains separated. Exact decision is:

`D. INSUFFICIENT EVIDENCE — MORE HUMAN GT REQUIRED`

This decision is supported and does not authorize a production switch.

## Verification

- Full backend suite: 243/243 passed.
- Focused adapter, normalization, CER/WER, edit-operation, taxonomy, confidence,
  geometry, cache-key, schema, and immutability tests passed.
- Python compilation passed.
- All five required 11.4 JSON artifacts passed JSON/schema validation.
- Workflow validation at IMPLEMENTED passed.
- `git diff --check` passed.

## Required fixes

None.
