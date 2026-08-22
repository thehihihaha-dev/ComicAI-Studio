# Checkpoint 11.3 — Reader V2 OCR/Text-Detection Baseline & Bake-Off

## Objective

Establish a read-only, reproducible 3-page Reader benchmark, measure the exact
production EasyOCR configuration against one locally cached lightweight
Vietnamese/English-capable candidate, and recommend the safest Reader V2 text
region/transcription foundation without changing production OCR.

## Background

Checkpoint 11.2 was human-approved with the 4B Story candidate rejected for
quality and the production Story/Vision fallback unchanged. Reader V1 currently
uses coupled EasyOCR detection/recognition before VLM layout, dialogue building,
correction/recovery, and Ground Truth. The existing audit identifies 22 important
regions across three persisted pages, while current human Ground Truth is much
smaller; metrics must therefore expose unavailable denominators as N/A.

## Files/modules likely involved

- `backend/app/services/ocr_service.py` (inspection only)
- a benchmark-only Reader metrics/schema module
- a read-only Reader benchmark runner under `scripts/`
- benchmark-only unit tests
- `benchmarks/day11/reader-*-11.3.json`
- `ai-workflow/REPORT.md` and `ai-workflow/REVIEW.md`

## Scope

- Document the actual Reader V1 path and model-call boundaries from current code.
- Create an immutable manifest for the same three persisted benchmark pages,
  including content hashes, dimensions, trustworthy geometry, expected important
  regions, and human Ground Truth references.
- Define deterministic normalization, CER/WER, geometry matching, and explicit
  merge/split/orphan/miss records before comparing engines.
- Run isolated EasyOCR using exactly `vi,en`, CPU, and production `readtext`
  behavior, without invoking normal persistence endpoints.
- Inventory local candidates and benchmark only one suitable cached candidate,
  selected for Apple Silicon feasibility and Vietnamese/English support.
- Run Mode A full-page combined OCR and, where technically valid, Mode B
  recognition on trusted crops; label non-overlapping capabilities honestly.
- Measure initialization, per-page/total latency, confidence buckets, process RSS,
  available memory, swap delta, safety state, and runtime backend sequentially.
- Simulate only potential easy/hard routing; make no claim of actual VLM savings.
- Hash authoritative OCR, Vision, Dialogue, Ground Truth, Story/review, and Script
  state before and after and require exact equality.
- Produce control, candidate, comparison, report, and independent review evidence.

## Out of scope

Production OCR changes, semantic normalization, VLM inference, Story/Script work,
Reading Order V2, connected-components repair, unified detector training,
annotation, cache migration, MLX/CoreML migration, full Reader V2, chapter-scale
testing, model tournaments, Checkpoint 11.4, commit, and push.

## Safety constraints

- Benchmark is offline/read-only with results written only to benchmark artifacts.
- Do not mutate assets, OCR, Vision, Dialogue, Ground Truth, Story/review, or Script.
- Use Resource Guard before and after each engine; stop the candidate safely on
  CRITICAL pressure and never run engines concurrently.
- Do not download or install candidates: use only already installed, fully cached
  assets. Do not call Ollama/VLM.
- Do not treat AI-cleaned dialogue as human transcription Ground Truth.
- Preserve geometry for later work, but do not infer missing boxes or denominators.

## Acceptance criteria

1. Manifest hashes the three source images and records the honest provenance and
   sufficiency of region geometry and human transcription Ground Truth.
2. Detection, transcription, and structure metrics remain separate; unavailable
   precision or text denominators are explicitly N/A.
3. Matching handles one-to-many merges and many-to-one splits without inflating
   one-to-one detection results.
4. EasyOCR control exactly mirrors current production configuration through an
   isolated non-persisting path.
5. At most one cached candidate is run and its detector/recognizer/combined role,
   language support, runtime, confidence, and Mode A/Mode B comparability are clear.
6. Artifacts contain deterministic raw/normalized outputs, timings, resources,
   structural errors, confidence buckets, schema/version metadata, and no secrets.
7. Authoritative before/after snapshot hashes are identical and VLM call count is
   zero; otherwise the checkpoint fails.
8. Candidate verdict uses one required exact label and architecture recommendation
   uses exactly A, B, C, or D without automatically switching production OCR.

## Required tests

- Normalization, CER, and WER.
- Geometry matching, one-to-many merge, and many-to-one split behavior.
- Benchmark artifact schemas and immutable/read-only snapshot comparison.
- Targeted unit tests with no model/network access, Python compilation, JSON
  validation, workflow validation, and `git diff --check`.
- Full backend suite is required only if a shared production utility changes.

## Benchmark permission

ALLOWED: exactly one isolated EasyOCR control plus one sequential candidate using
already installed libraries and already cached local model assets on the same
three pages. No downloads, installations, VLM calls, persistence endpoints, or
additional candidates. Stop before candidate inference if Resource Guard is
CRITICAL; stop further benchmark work if severe pressure occurs.

## Stop condition

Write the required A–AC report, perform an independent Reviewer pass, and stop at
`AWAITING_HUMAN_APPROVAL`. Do not commit, push, change production OCR, or start
Checkpoint 11.4.
