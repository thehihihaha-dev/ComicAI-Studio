# Checkpoint 11.8 — Reader V2 Fast Pass Prototype

## Objective

Build an additive, deterministic/local-first Reader V2 Fast Pass using the 11.7
logical-region crop result: image + compatible logical regions -> 2% bounded crop
-> EasyOCR -> geometry-based MANGA_RTL order -> explicit uncertainty -> structured
output, with zero automatic VLM/Ollama calls.

## Scope

- Reusable isolated Fast Pass service; do not replace production OCR or persist its output.
- Preserve source bbox/identity, native JSON coordinates, engine/config/timing,
  quality signals, ACCEPT_CANDIDATE/HARD/AMBIGUOUS routing and page stats.
- Configurable reading-order policy contract; validate MANGA_RTL with panel/group
  hierarchy, tier clustering, deterministic ties, orphans and ambiguous geometry.
- Deterministic fingerprint over source/crop/OCR/order revisions for future reuse.
- Read-only benchmark on the same 20 VERIFIED GT regions and existing three pages.
- Measure exact/CER/WER, errors, regressions against 11.7 Mode B, false ACCEPT,
  crop/OCR/order/wall latency, resources, swap, safety and model-call count.

## Safety

No GT or authoritative OCR/Vision/Dialogue/Story mutation; no automatic VLM,
Ollama, correction or recovery; no new model/download, production switch,
40-page run, threshold tuning, 11.9, commit or push. ACCEPT_CANDIDATE means only
that no known escalation signal fired. Stop benchmark on CRITICAL Resource Guard.

## Required artifacts

- `benchmarks/day11/reader-v2-fast-pass-11.8.json`
- `benchmarks/day11/reader-v2-fast-pass-errors-11.8.json`
- `benchmarks/day11/reader-v2-reading-order-11.8.json`
- `benchmarks/day11/reader-v2-performance-11.8.json`

## Required validation

Focused Fast Pass/OCR/reading-order/resource tests, full backend suite, Python
compile, four-artifact JSON validation, workflow validation and `git diff --check`.

## Stop condition

Write A–Z report, perform independent review and stop at
`AWAITING_HUMAN_APPROVAL`. Do not begin 11.9, commit or push.
