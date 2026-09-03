# Checkpoint 12.2 — Final Human Panel GT Validation Review

## Verdict

**PASS — A. HUMAN PANEL GT VALIDATED**

## Independent evidence

- The recovered invalid-coordinate audit contains exactly 13 literal annotations across Pages 1, 2, 15, and 17 (3/2/3/5). Its canonical material independently reproduces SHA-256 `d49cc0aab140a743317bbb36a3f53a74ecf1c2305f279ccb75d306855e9e3b1c`.
- Recovery provenance resolves to persisted Codex JSONL line 1396 and tool call `call_IEj8hODYlCmDDCIfnblRzba4`. The preceding call is a direct SQLAlchemy read of `PanelGroundTruthReview.human_panels`; the logged arrays were parsed literally. No bbox was inferred, transformed, or obtained from the new GT.
- The old evidence is explicitly `INVALID_COORDINATE_SYSTEM`, `NOT AUTHORITATIVE GT`, and inactive.
- PostgreSQL independently contains exactly Pages 1, 2, 15, and 17, all `VERIFIED`: 3/2/5/5 panels, 15 total, with 0 ambiguous and 15 non-ambiguous.
- Canonical persisted new-GT SHA-256 independently reproduces `5ac1383fdbd611bd203fa1e1b35d8fb0eb4e4e082f62e04907adc493c5635fd3` and differs from the invalid snapshot.
- For every page, persisted asset ID, source path, dimensions, and SHA-256 agree with the frozen input manifest; actual file bytes independently reproduce the same source SHA-256.
- Every bbox is finite, positive-area, and inside the 900x1280 source image. Horizontal union coverage is 84.39%–85.37%, not the invalid 36.94%–37.78% signature; no common horizontal letterbox offset remains.
- The object-contain mapping excludes letterbox padding and implements matching source/display transforms. Focused tests prove outside-image pointer rejection and exact source/display/source roundtrip across resize sizes; persisted source coordinates remain unchanged.
- Direct visual inspection of the four source images against the persisted coordinates confirms all 15 annotations cover complete manga panels. None is a speech bubble, text region, character-only crop, accidental drag, or letterbox region.
- `gt_runtime_features` is empty. Frozen prediction file SHA-256 remains `80e46d5c6216e3d18e9686af149a0012911795a246d1323ae4bb74d516b4b735`. Human GT has not entered extraction, thresholds, fusion, ambiguity, page-edge completion, or frozen prediction state.

## Validation rerun

- Audit integrity plus Human GT tests: 11/11 PASS.
- Coordinate/interaction tests: 8/8 PASS.
- JSON audit/isolation validation: PASS.
- Workflow validation: PASS at `AWAITING_HUMAN_APPROVAL`, next role `HUMAN`.
- `git diff --check`: PASS.
- Resource Guard `NORMAL`; OCR/VLM/Ollama calls 0/0/0.

The new 15-panel Human GT is trustworthy independent authoritative evaluation evidence. Frozen panel-detector correctness evaluation is now safe to run only when explicitly directed; it was not run in this review.
