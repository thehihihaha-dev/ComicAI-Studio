# Checkpoint 11.4 — Reader OCR Benchmark Expansion & Error Characterization

## Objective

Strengthen the trustworthy Reader V2 OCR evidence by evaluating exactly EasyOCR
and cached PaddleOCR v6 small on every available human-verified region, explicitly
characterizing transcription/confidence/agreement errors, and identifying regions
that still require human labels without changing production OCR.

## Background

11.3 found equal 21/21 known-region recall, line-oriented structural over-split,
and promising Paddle transcription/resource results, but only two human GT labels.
A read-only inventory now finds only three human-verified regions repository-wide.
This is not a substantial accuracy dataset, so 11.4 must benchmark those three
without fabrication and publish a deterministic future-human-transcription queue.

## Files/modules likely involved

- Existing benchmark-only Reader library/runner under `scripts/`
- A new isolated 11.4 crop benchmark/evaluation runner
- Benchmark-only unit tests
- Five `benchmarks/day11/reader-*-11.4.json` artifacts
- Workflow report/review documents

## Scope

- Build a deterministic, deduplicated manifest from all existing human GT rows,
  linking region bbox, role/language/tags only where evidence supports them.
- Add unlabeled audit-important regions to a separate `requires_human_transcription`
  queue; never use OCR/AI-cleaned dialogue as reference text.
- Run identical source crops with EasyOCR recognition and PP-OCRv6 small
  recognition, sequentially, CPU-only, concurrency one, zero VLM calls.
- Record preprocessing differences forced by APIs, cache keys/status, cold init,
  per-region/total latency, RSS, available memory, swap, and Resource Guard state.
- Calculate raw and evaluation-normalized exact/CER/WER plus edit operation rates,
  missing text, error taxonomy, confidence buckets, and cross-engine agreement.
- Report language/role/difficulty subgroup metrics only when adequately labeled;
  otherwise include counts and N/A.
- Keep 11.3 structural detection/bubble evidence separate from crop transcription.
- Snapshot and verify authoritative Asset/GT/Story/review/Script state unchanged.
- Answer all ten required analysis questions and choose exact decision A/B/C/D.

## Out of scope

Ground Truth creation, semantic decisions, production OCR/routing changes, a third
OCR engine, VLM/Ollama, Story/Dialogue/Coverage/Script inference, panel ordering,
chapter chunking, carry-over state, Story Graph, VLM repair, bubble repair,
training, concurrency, Checkpoint 11.5, commit, and push.

## Safety constraints

- Read-only database/image access; artifacts are the only outputs.
- Production remains EasyOCR; Paddle remains benchmark-only.
- No downloads/installations; require installed libraries and complete local cache.
- Resource Guard before each engine, sequential execution, stop before another
  stage on CRITICAL and preserve completed partial artifacts.
- No fabricated bbox, GT, language, role, or difficulty labels; unsupported fields
  are `unknown`/N/A and insufficient subgroups are not scored as conclusions.
- Cache reuse must disclose `measured_this_run` versus `reused_cached_result`.

## Acceptance criteria

1. Manifest contains all and only deduplicated human-verified samples available,
   plus a clearly non-GT future transcription queue.
2. Both engines receive identical pixel crops; forced adapter preprocessing is
   recorded, and no inference result is persisted to product tables.
3. CER/edit operations are correct and raw versus normalized metrics are separate.
4. Error taxonomy, confidence buckets/high-confidence errors, deterministic OCR
   agreement outcomes, and both-confidently-wrong evidence are machine-readable.
5. Text detection, transcription, OCR line splitting, and logical bubble merging
   remain distinct findings; 11.3 detection is not misreported as crop detection.
6. Performance/resource samples are comparable, concurrency is one, safety is
   respected, and VLM calls equal zero.
7. Authoritative before/after hashes match exactly and production OCR is unchanged.
8. Five required reproducible 11.4 artifacts and A–AD report explicitly disclose
   the three-sample limitation and answer the required analysis.
9. Decision uses exactly A/B/C/D and does not authorize a production switch.

## Required tests

- Raw/evaluation normalization, CER/WER, insertion/deletion/substitution counts.
- Error taxonomy including punctuation, diacritic, case, language confusion,
  missing text, and general substitution.
- Confidence buckets, agreement matrix, cache key/hash, schema, deduplication, and
  immutable snapshot behavior.
- OCR adapters mocked with no network/model download.
- Focused tests, full backend suite, Python compile, JSON validation, workflow
  validation, and `git diff --check`.

## Benchmark permission

ALLOWED: one sequential 11.4 recognition benchmark per engine on exactly the three
available human-verified crops, using installed EasyOCR and already cached
PP-OCRv6 small recognizer. Cached reuse is allowed only on an exact key match and
must be disclosed. No full-page OCR rerun, third engine, download, installation,
VLM/Ollama, persistence endpoint, or product-table write.

## Stop condition

After implementation, tests, artifacts, A–AD report, and independent review, stop
at `AWAITING_HUMAN_APPROVAL`. Do not commit, push, or begin 11.5.
