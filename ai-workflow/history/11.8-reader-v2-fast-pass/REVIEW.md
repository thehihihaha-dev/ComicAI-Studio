# Checkpoint 11.8 Independent Review — Fix Review

## Verdict

PASS

## Evidence

- The prior cache-contract defect is fixed: normalized panel identity/geometry now participates in the fingerprint, the runtime call supplies panels, and a focused test proves panel geometry changes the key.
- Saved benchmark fingerprints recompute exactly under the corrected contract; they were refreshed without OCR/model inference.
- The additive service implements bounded reusable crops, structured OCR provenance, explicit non-authoritative uncertainty, deterministic hierarchical MANGA_RTL preparation and zero automatic VLM/Ollama calls.
- Read-only benchmark remained comparable with 11.7 Mode B: exact 4/20, normalized CER 0.11038, WER 0.40558 and 0 regressions. Authoritative state stayed unchanged and Resource Guard stayed NORMAL with swap delta 0.
- The 16/19 (84.21%) false ACCEPT result is prominently disclosed and blocks any safe-router/production-trust claim.
- Focused fix tests 9/9, focused Reader/OCR/geometry/resource tests 32/32 and full backend 267/267 pass. Python compile, four JSON artifacts, workflow validation and `git diff --check` pass.
- No production integration, 40-page benchmark, VLM, model download, 11.9, commit or push occurred.

## Required fixes

None.
