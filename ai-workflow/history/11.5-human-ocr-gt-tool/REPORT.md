# Checkpoint 11.5 Report — Human OCR Ground Truth Review

## A. Existing GT architecture inspected

`DialogueGroundTruth` is the authoritative, unique `(asset_id, region_id)` human
text store and already wins during dialogue reruns. Existing dialogue verification
upserts that row but lacks benchmark queue state, bbox/source hashes, revisions and
skip/unreadable semantics. The implementation preserves this authority and adds
only linked benchmark-review metadata.

## B. Queue source

The unchanged `reader-benchmark-manifest-11.4.json` future-transcription list is
read deterministically. Its frozen entries have null project IDs, so ownership is
validated from each stable asset ID against the requested project. Existing valid
GT regions are excluded. Actual imported queue: 20.

## C. Review sample identity

Stable artifact `sample_id`, unique asset/region, project, page, region, bbox,
text role, full source image SHA-256 and canonical unpadded crop SHA-256.

## D. Persistence design

Migration 006 adds `ocr_benchmark_reviews`; `DialogueGroundTruth` remains the only
authoritative transcription table. Metadata persists state, hashes, provenance,
compatibility, revision/cache revision and timestamps across restarts.

## E. Human provenance contract

Metadata enforces provenance `human`. Only an explicit `VERIFIED` request with
non-whitespace text upserts Ground Truth. Stored text is preserved exactly,
including outer whitespace/line structure; trimming is used only to reject empty
input. OCR/AI fields are never accepted by the endpoint.

## F. Source hash behavior

Every queue/crop/save/benchmark-consumption path verifies both full image hash and
crop hash. Missing/changed pixels yield `SOURCE_UNAVAILABLE`, block writes and are
excluded from VERIFIED-only export without reconstructing evidence.

## G. UI implementation

Internal route `/projects/[id]/ocr-benchmark` is linked from the project header.
It shows crop, progress, state, project page/role/region, editor, Save & Next,
Skip, Unreadable and Previous/Next. Cmd/Ctrl+Enter saves for keyboard flow.

## H. Crop behavior

Project/sample identifier API only; no filesystem path is exposed. Ownership and
hashes are revalidated. Display adds 32 px padding without changing the canonical
unpadded provenance crop. Actual validation returned a valid 182×168 RGB PNG.

## I. Save flow

Empty input is rejected. Explicit human text upserts one GT row, changes state to
VERIFIED, increments revision/cache revision and advances the UI.

## J. Skip flow

SKIPPED persists and advances without creating Ground Truth.

## K. Unreadable flow

UNREADABLE persists and advances without creating Ground Truth.

## L. Source-unavailable flow

Missing bbox/image or hash mismatch displays SOURCE_UNAVAILABLE, removes crop URL,
blocks transcription and remains ineligible for benchmark metrics.

## M. Resume behavior

Queue state is database-backed. Reload requests reconstruct progress and resume at
the persisted list; backend/frontend restart does not reset metadata.

## N. Edit behavior

Previously VERIFIED items expose only their human text for editing. A changed
human value updates the same GT row and increments revision/cache revision.

## O. Duplicate/idempotency behavior

Primary `sample_id` and unique asset/region prevent duplicates. Repeating an
identical save preserves revision, cache revision and verified timestamp.

## P. Benchmark integration

`reader_benchmark_verified.py` exports compatible VERIFIED samples without OCR by
default. `--run` is available only when N>0 and invokes unchanged 11.4 adapters/
metrics sequentially, writing `*-verified-latest.json`; frozen 11.4 files are never
overwritten. Metrics retain sample count N.

## Q. VERIFIED-only enforcement

Exporter requires state VERIFIED, provenance human, compatible hashes, existing
Ground Truth and current source/crop equality. Current export has N=0.

## R. OCR bias prevention

Before submission, queue/API/UI contain no raw OCR, EasyOCR, PaddleOCR, AI
correction or recovery proposal. After-save comparison was intentionally omitted
to keep the first implementation minimal and bias-safe.

## S. Model-call confirmation

Queue load, crop, and actions make 0 OCR and 0 VLM/Ollama calls; explicit mocked
tests enforce this. No Story/Dialogue/Coverage/Script/Vision call ran.

## T. Production OCR confirmation

Production remains EasyOCR. PaddleOCR remains only in explicit benchmark tooling.

## U. Resource behavior

Review operations perform image hashing/cropping and database work only. No heavy
model resources or concurrency are introduced. Future `--run` retains sequential
11.4 Resource Guard behavior.

## V. Backend tests

Full backend suite passes 249/249, including queue, valid save, empty rejection,
skip, unreadable, source unavailable, idempotency, reload, hash mismatch, edit/
cache invalidation, VERIFIED filtering, non-promotion, isolation and zero calls.

## W. Frontend tests/build

ESLint passes. TypeScript `--noEmit` passes. Next production build passes; the
first sandboxed build failed only because existing Google Fonts required network,
then passed with approved network access.

## X. Manual validation

Actual backend/UI: queue API 200 with total 20/pending 20/verified 0; forbidden
prediction fields absent; crop API 200 image/png; page route 200 and rendered the
OCR Ground Truth/Human transcription screen; empty production save rejected 422.
No fake manga transcription was entered. Save/reload semantics were exercised only
with isolated SQLite image/text fixtures.

## Y. Files changed

New review model, migration, service/router, frontend route/component, VERIFIED
export/rerun CLI, backend tests and one N=0 export artifact; small router/main,
project header, migration README and benchmark helper updates. 11.4 artifacts are
unchanged.

## Z. Current verified GT count

Benchmark-review VERIFIED: 0/20. Existing global DialogueGroundTruth rows remain 3
and were not treated as completed review-queue samples.

## AA. Remaining queue count

20 PENDING, 0 verified at checkpoint completion.

## AB. Limitations

The user must still transcribe the regions. Optional post-save OCR comparison is
not implemented. There is no statistical expansion until human review occurs.
Internal localhost API conventions remain hardcoded consistently with the current
frontend. Authentication is outside the current local application architecture;
project/asset ownership is nevertheless enforced.

## AC. Recommendation for 11.6

B. MORE HUMAN TRANSCRIPTION REQUIRED

Do not design EASY/HARD thresholds. First use the new UI to create sufficient,
diverse VERIFIED samples, then run the explicit VERIFIED-only benchmark.
