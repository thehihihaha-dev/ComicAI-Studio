# Checkpoint 11.9 Report — Human Reading-Order Validation UI

## A. What changed

Added a human-only reading-order validation queue for existing manga pages. The UI shows the original page, Reader V2 region boxes/predicted numbers and ambiguity markers; humans can reorder regions, assign ordered panel/group names, set orphan/ambiguous dispositions and explicitly verify a page.

## B. Files changed

Added the reading-order review SQLAlchemy model, migration 007, isolated service/router, six backend tests and the new frontend route/component. Registered only the new API router and a project-editor navigation link. Updated active workflow documents.

## C. Architecture/logic

Reader predictions and human GT occupy separate immutable/persisted fields. Queue creation uses at most ten real project assets with compatible persisted logical regions; this project has three. Source SHA-256 changes invalidate eligibility. Project identity is checked on every read/write. Opening/refreshing never verifies. A valid explicit submission must contain every region exactly once in both sequence and groups; identical resubmission is idempotent. `ordering_metrics()` deterministically exposes exactness, pairwise accuracy, inversions and correction count for the post-human phase, but no metrics were run against invented GT.

## D. Tests

Focused reading-order tests pass 6/6: persistence/reload, duplicate idempotency, prediction separation, incomplete/duplicate rejection, project isolation, source invalidation, deterministic partial-error metrics and zero model calls. Full backend passes 273/273 in 2.386 s. ESLint and TypeScript `--noEmit` pass. Next production build passes after network access allowed existing Google Font retrieval. Python compilation and `git diff --check` pass.

## E. Human queue

Project `e1d1b85f-90b8-4d6b-9eb6-6694e1dc5fb2`: total 3 real pages, VERIFIED 0, PENDING 3, SOURCE_UNAVAILABLE 0. No human sequence/disposition was created by the agent.

## F. Safety/data integrity

Ollama calls 0; VLM calls 0; no OCR inference or model download. Production OCR/Vision/Dialogue/Story fields were not modified. Migration 007 creates only the separate review table. The first standalone queue attempt failed before commit because the Project model was not registered in SQLAlchemy metadata; the import order was fixed and the subsequent queue initialization succeeded without partial rows.

## G. Remaining limitations

Only three compatible project pages exist, below the approximate ten-page target. Persisted data has no verified panel boundaries, so the initial prediction displays a page fallback group; the human can define groups, but the agent cannot validate their semantic correctness. Post-human metrics/error taxonomy/export are intentionally deferred until the user explicitly completes validation.

## H. Git/workflow status

No commit or push. No 11.10 work. Stop at the human testing gate after independent technical review and service availability verification.
