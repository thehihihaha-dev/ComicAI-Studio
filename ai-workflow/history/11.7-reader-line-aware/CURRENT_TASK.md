# Checkpoint 11.7 — Line-Aware Crop & Text Reconstruction Experiment

## Objective

Using the frozen 20 human-VERIFIED samples, isolate whether deterministic crop
padding, text-line OCR and geometry-based reconstruction materially improve
EasyOCR transcription versus the cached 11.6 current logical-region recognizer
path, without changing production OCR.

## Background

11.6 was human-approved with both engines wrong on 18/20 and decision D. Current
GT regions are logical bubble/narration boxes formed as unions of persisted OCR
line blocks, while 11.6 fed each full often-multiline crop to a line recognizer.
This mismatch may explain much of the deletion-heavy CER.

## Files/modules likely involved

- a pure line geometry/crop/reconstruction benchmark helper and runner
- focused tests
- four new 11.7 JSON artifacts
- workflow report/review documents

## Scope

- Freeze and revalidate exactly the same 20 sample IDs/GT/image/crop hashes.
- Diagnose persisted region/block geometry, line count/order, tightness, clipping,
  overlap and neighboring-block contamination using evidence-based tags only.
- Mode A: reuse exact cached 11.6 EasyOCR whole-region recognizer output.
- Mode B: run EasyOCR full detection+recognition on each logical-region crop at a
  bounded 0/2/5/8% padding grid; sort detected lines deterministically.
- Mode C: crop persisted line boxes belonging to the logical region, apply bounded
  winning padding within image bounds, recognize each line, order top-to-bottom
  with left-to-right ties, and deterministically join text.
- Retain complete line boxes/order/raw output/padding/engine/cache provenance.
- Calculate exact/CER/WER/edit/missing metrics with N, select padding by CER then
  regressions, and classify every sample IMPROVED/UNCHANGED/REGRESSED versus A.
- Attribute failures conservatively to recognition, geometry, reconstruction,
  detection or unknown and measure latency/resources sequentially.

## Out of scope

Production OCR changes, Paddle tournament, Reader router, VLM/Ollama, Story/
Dialogue/GT mutation, panel/bubble reading-order implementation, full Reader V2,
large padding search, 11.8, commit and push.

## Safety constraints

- Human GT and persisted OCR/Vision/Dialogue/Story/Review/Script are read-only and
  hashed before/after.
- EasyOCR only, one instance, concurrency one; Resource Guard before inference and
  stop new modes on CRITICAL while preserving partial results.
- Zero VLM calls; no semantic reconstruction or spelling correction.
- Crop coordinates clip to image bounds and cache identity includes source hash,
  bbox, padding, engine/version, preprocessing and reconstruction mode.

## Acceptance criteria

1. All 20 frozen samples remain compatible and stable IDs permit direct A/B/C
   comparison without GT changes.
2. Diagnostics retain region/line geometry and use only supported tags.
3. Mode A is cached 11.6 evidence; B/C provenance fully explains crop, line order,
   raw OCR and deterministic reconstruction.
4. Padding search is bounded and reports both improvement and harm.
5. Mode metrics and per-sample deltas include N, absolute/relative CER change,
   exact change, improved/regressed counts and severe regressions.
6. Performance/resources/cache status and zero VLM calls are reproducible.
7. Decision is exactly A/B/C/D and makes no production deployment.

## Required tests

Crop padding/image-bound clipping, line ordering/ties, deterministic reconstruction,
stable cache identity, GT immutability, CER delta/regression classification and
zero-model-call analysis; full backend suite, Python compile, four-artifact JSON
validation, workflow validation and `git diff --check`.

## Benchmark permission

ALLOWED: reuse cached Mode A and run one EasyOCR instance sequentially across the
bounded Mode B padding grid plus Mode C persisted line boxes on exactly 20 crops.
No Paddle rerun, VLM/Ollama, third engine, concurrency, production write or repeat
for prettier numbers.

## Stop condition

Write A–AG report, perform independent review, and stop at
`AWAITING_HUMAN_APPROVAL`. Do not commit, push, deploy or begin 11.8.
