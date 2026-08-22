# Checkpoint 11.5 — Human OCR Ground-Truth Benchmark Tool

## Objective

Build an internal, resumable and bias-resistant review workflow for the 20 regions
queued by 11.4 so a human can inspect exact reproducible crops and create/edit
authoritative OCR Ground Truth, plus a deterministic VERIFIED-only benchmark rerun
entry point, without changing production OCR or generating semantic labels.

## Background

11.4 was human-approved with decision D: only two reproducible verified crops,
one historical GT missing its source, and twenty regions needing transcription.
Existing `DialogueGroundTruth` uniquely owns authoritative asset/region text but
lacks benchmark state, bbox/hash provenance, revision, and unreadable/skip states.
Existing region crop APIs derive bbox from persisted regions/blocks.

## Files/modules likely involved

- `DialogueGroundTruth` plus one benchmark-review metadata model/migration
- a benchmark review service/router and schemas
- existing safe crop helpers/endpoints
- a project-scoped internal frontend route/component and navigation link
- a VERIFIED-only benchmark CLI using unchanged 11.4 metric definitions
- backend/frontend tests and workflow documents

## Scope

- Deterministically import the 11.4 queue using stable sample IDs without copying
  OCR/AI proposal text into UI/API payloads.
- Persist PENDING/VERIFIED/SKIPPED/UNREADABLE/SOURCE_UNAVAILABLE, exact bbox/full
  image hash/crop hash, human provenance, revision, timestamps and cache revision.
- Upsert exactly one existing `DialogueGroundTruth` row only on explicit VERIFIED
  human submission; other actions never create authoritative GT.
- Validate project/asset/region ownership, exact source hash and crop reproduction
  on queue, crop and mutation operations; stale pixels cannot reuse old GT.
- Provide project-scoped queue/progress/navigation/crop and idempotent action/edit
  APIs with empty VERIFIED transcription rejection.
- Build keyboard-friendly internal UI hiding all OCR/AI text before submission,
  with Save & Next, skip, unreadable, previous/next and refresh persistence.
- Provide deterministic VERIFIED-only benchmark export/rerun tooling that preserves
  11.4 metrics and includes N; never overwrite 11.4 artifacts.
- Manually validate rendering/navigation/persistence using non-semantic fixtures
  only; do not transcribe production manga.

## Out of scope

Agent-created GT, automatic OCR/AI promotion, production OCR/routing switch,
Reader V2 EASY/HARD thresholds, OCR on page load, VLM/Ollama/Story/Dialogue/
Coverage/Script/Vision calls, arbitrary filesystem exposure, 11.6, commit, push.

## Safety constraints

- Production OCR remains EasyOCR; Paddle stays benchmark-only.
- Review queue/page makes zero OCR and zero model calls.
- Only explicit human VERIFIED input may write `verified_text`; preserve exact text
  except rejection of empty/whitespace-only submissions.
- Source unavailable/hash mismatch disables verification and invalidates benchmark
  compatibility without reconstructing evidence.
- Stable identity and DB uniqueness make repeated requests idempotent.
- Any optional benchmark rerun is sequential, Resource-Guarded and concurrency one.

## Acceptance criteria

1. Initial queue derives from the unchanged 11.4 artifact and excludes preexisting
   valid GT without duplicating region identity.
2. Queue/API/UI never reveal OCR, Paddle, AI correction or recovery text before a
   human submission; crop URLs expose identifiers only.
3. All five states persist across sessions; VERIFIED alone creates/updates one
   DialogueGroundTruth with explicit human provenance metadata.
4. Source/crop hashes and bbox bind GT to pixels; missing/changed sources cannot be
   verified or consumed by benchmark.
5. Save & Next, skip, unreadable, previous/next, progress, reload, and verified edit
   work and increment revision/cache invalidation deterministically.
6. Project isolation, ownership, empty input, duplicate save, and no-model-call
   behavior are covered by tests.
7. VERIFIED-only rerun/export consumes compatible VERIFIED records, retains 11.4
   metric definitions/sample N, and cannot overwrite 11.4 artifacts.
8. Backend/full frontend validation and isolated manual UI/API checks pass without
   entering fake production transcription.

## Required tests

Queue loading, human save, empty rejection, skip, unreadable, source unavailable,
idempotency, reload persistence, source hash mismatch, verified edit/revision,
VERIFIED-only filtering, AI/OCR non-promotion, project isolation, zero model calls,
crop ownership, migration/model integrity, benchmark export/cache invalidation;
full backend suite, ESLint, TypeScript noEmit, Next production build, Python
compile, JSON/workflow validation and `git diff --check`.

## Benchmark permission

NOT ALLOWED for semantic production samples. Do not run OCR/VLM or enter GT. An
isolated synthetic fixture may validate UI/API persistence. Implementing (but not
executing) the sequential VERIFIED-only OCR rerun command is allowed.

## Stop condition

Write A–AC report, perform independent review, recommend exactly A or B for the
11.6 gate, and stop at `AWAITING_HUMAN_APPROVAL`. Do not commit, push, or start 11.6.
