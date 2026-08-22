# Checkpoint 11.6 — OCR Routing Signal Benchmark & Reader V2 Decision

## Objective

Using only compatible human-VERIFIED crops, measure whether EasyOCR confidence,
PaddleOCR confidence, normalized OCR agreement, deterministic text sanity signals,
or combinations can safely route Reader V2 regions as EASY versus HARD, without
deploying a router or changing production OCR.

## Background

Persisted 11.5H state is exactly 20/20 VERIFIED with no unreadable, skipped,
source-unavailable or pending samples. Production remains EasyOCR. The existing
VERIFIED-only tool binds GT to source/crop hashes and can run the unchanged 11.4
EasyOCR/Paddle recognition adapters sequentially into new non-frozen artifacts.

## Files/modules likely involved

- VERIFIED-only export/rerun and unchanged 11.4 OCR metric adapters
- a new pure routing-signal analysis module/CLI
- focused benchmark tests
- four new 11.6 JSON artifacts and workflow documents

## Scope

- Recount persisted states and export exactly compatible VERIFIED human GT.
- Reuse exact-key cached OCR only if available; otherwise measure both OCR engines
  sequentially on equivalent crops, recording cache status/resources/latency.
- Compute per-sample raw/normalized CER/exactness, confidence, normalized edit
  similarity, agreement outcomes and conservative deterministic sanity flags.
- Evaluate CER==0, <=0.05 and <=0.10 correctness labels separately.
- Simulate confidence-only, similarity-only, confidence+agreement, and combined
  sanity routers across explicit benchmark-fitted threshold grids.
- Report accepted count/rate, safe-accept rate, false-safe rate/count, hard rate,
  EASY precision and correct-region coverage with N for every candidate.
- Identify high-agreement-both-wrong, false-confidence, engine wins/both outcomes,
  threshold sensitivity and leave-one-out stability.
- Compare EasyOCR-only and sequential dual-OCR cost/resources and project measured
  OCR-only latency to 5/10/20/50 pages as projections.
- Choose exact architecture A/B/C/D based on false-safe-first evidence.

## Out of scope

Production router/threshold deployment, third OCR, parallel OCR, model training,
VLM/Ollama repair, full Reader V2, merged/split bubble repair, Story/Vision/
Dialogue/Coverage/Script calls, frontend changes, 11.7, commit and push.

## Safety constraints

- Human GT is read-only; never modify transcription or accept non-VERIFIED rows.
- Production remains EasyOCR and Paddle remains benchmark-only.
- Both OCR passes are sequential, concurrency one, Resource-Guarded; stop new work
  on CRITICAL and preserve completed artifacts.
- Expected VLM/model calls are zero.
- Thresholds are BENCHMARK-FITTED sensitivity analyses, never production-calibrated.
- FALSE_SAFE minimization takes priority over EASY coverage and latency.

## Acceptance criteria

1. Persisted state counts and VERIFIED export are exact; all 20 samples pass current
   image/crop hash validation and carry human provenance.
2. Both engines use equivalent crop identity, and inference/cache status, versions,
   preprocessing, confidence, timings/resources and N are reproducible.
3. Similarity, CER correctness classes, sanity flags and agreement/win outcomes are
   deterministic and machine-readable.
4. Each router reports false-safe, safe-accept, hard rate, EASY precision and
   coverage with counts/denominators; dangerous agreement-but-wrong is explicit.
5. Threshold sensitivity and leave-one-out reveal instability rather than claim
   unsupported generalization from N=20.
6. Dual-OCR cost and page-count projections use measured OCR-only latency and are
   labeled projections.
7. Structural detection limitations remain separate and VLM calls equal zero.
8. Decision is exactly A/B/C/D, does not change production, and gates 11.7 only as
   a recommendation.

## Required tests

VERIFIED-only loading/hash validation, CER, normalized similarity, confidence
extraction, sanity flags, correctness classes, false-safe/safe-accept/hard/EASY
precision/coverage, threshold evaluation, cached reuse logic, leave-one-out,
no-model-call analysis; full backend suite, Python compile, four-artifact JSON
validation, workflow validation and `git diff --check`.

## Benchmark permission

ALLOWED: export the 20 compatible VERIFIED samples and run exactly one sequential
EasyOCR pass plus one cached PP-OCRv6-small pass only where exact cache entries do
not exist. Use Resource Guard/concurrency one, write only new 11.6/latest artifacts,
and make zero VLM/Ollama calls. No third engine or repeat for prettier timing.

## Stop condition

Write A–AF report, perform independent review, and stop at
`AWAITING_HUMAN_APPROVAL`. Do not commit, push, deploy routing or start 11.7.
