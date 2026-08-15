# ComicAI Studio — Project Context & Agent Instructions

## 1. Project Overview

ComicAI Studio is an AI-assisted platform for creating comic/manga/manhwa review videos.

Primary goals:

- Accept comic/manga/manhwa content as input.
- Extract and understand dialogue and page structure.
- Correct OCR errors safely.
- Understand story events.
- Generate review scripts.
- Generate voice.
- Automatically create/edit videos.
- Allow users to manually correct AI output.
- Eventually support both Short and Long-form video generation.
- Support Vietnamese first while keeping the architecture internationalizable.

The product should eventually behave more like an AI video editor specialized for comics than a simple "Generate Video" website.

## 2. Repository Structure

Main repository:

ComicAI-Studio/

Important directories:

- `frontend/` — Next.js frontend
- `backend/` — FastAPI backend
- `ai/` — AI service
- `docker/` — Docker infrastructure
- `docs/`
- `scripts/`
- `tests/`
- `assets/`

Before modifying anything, inspect the actual repository because this document describes architecture and intent, while the codebase is the source of truth for current implementation details.

## 3. Development Environment

Primary development machine:

- macOS
- Apple Silicon Mac

Current major services:

- Frontend: Next.js
- Backend: FastAPI
- AI service: FastAPI
- Database: PostgreSQL
- Local vision LLM: Ollama

Typical local ports:

- Frontend: `3000`
- Backend: `8000`
- AI service: `8001`
- PostgreSQL: `5432`
- Ollama: `11434`

## 4. Frontend

Frontend stack:

- Next.js
- TypeScript
- Tailwind CSS
- App Router

Project detail/editor-related code currently lives around:

`frontend/app/projects/[id]/`

Important existing components may include:

- `page.tsx`
- `AssetUploader.tsx`
- `ReviewQueue.tsx`

Always inspect the actual files before editing them.

## 5. Backend

Backend stack:

- FastAPI
- SQLAlchemy
- PostgreSQL

Important areas:

`backend/app/routers/`

`backend/app/models/`

`backend/app/services/`

Important existing model:

`Asset`

Asset currently stores data related to:

- uploaded file
- OCR
- OCR blocks
- vision regions
- reading order
- vision status
- dialogues
- dialogue status

## 6. Current AI Pipeline

Current pipeline conceptually works like this:

Input comic image

→ OCR

→ OCR blocks

→ Vision/Layout Analysis

→ Reading Order

→ Dialogue Construction

→ OCR Dialogue Correction

→ Correction Scoring

→ Decision Engine

→ Auto-Recovery when uncertain

→ Human Review when necessary

→ Verified Dialogue / Ground Truth

## 7. Vision / Layout Analysis

Important service:

`backend/app/services/vision_analyzer.py`

The vision system receives:

- original image
- OCR blocks
- OCR block IDs
- confidence
- bounding boxes

It uses a vision model to determine:

- dialogue/speech regions
- which OCR blocks belong together
- reading order

The model must NOT invent OCR block IDs.

### Vision Validation

Vision output is validated for:

- missing block IDs
- duplicate block IDs
- invalid block IDs

Not every OCR block is necessarily meaningful dialogue.

Low-quality OCR garbage may be ignored.

The system has recovery logic for important missing blocks.

### No-dialogue Pages

A comic image can legitimately contain no usable dialogue.

Such pages must NOT automatically be treated as vision failures.

The system now supports a status concept similar to:

`vision_status = "no_dialogue"`

Example benchmark behavior:

- `2.jpg` → vision completed
- `3.jpg` → no_dialogue
- `4.jpg` → vision completed
- `5.jpg` → vision completed

## 8. Ollama Vision

Important service:

`backend/app/services/ollama_vision.py`

Current local vision model has been:

`qwen3-vl:8b-instruct`

Ollama endpoint:

`http://127.0.0.1:11434/api/generate`

The system previously encountered context overflow with a 4096 token context.

The request was adjusted to support a larger context, currently around:

`num_ctx = 8192`

Do not remove this without understanding why it exists.

### JSON Handling

Vision models may return valid JSON wrapped in Markdown fences:

````text
```json
{ ... }

The response parser must tolerate this behavior rather than failing merely because Markdown fences are present.


## 9. Dialogue Correction

Important service:

`backend/app/services/dialogue_corrector.py`

Dialogue correction must:

- preserve original language
- preserve names
- preserve meaning
- correct OCR errors
- use image evidence
- avoid translation
- avoid summarization
- avoid creative rewriting
- never invent unseen information

Each corrected dialogue should preserve:

- `order`
- `region_id`
- `raw_text`

and can include:

- `clean_text`
- `confidence`
- `needs_review`
- `reason`


## 10. Correction Scoring

The system calculates a correction score using signals including:

- OCR confidence
- similarity between raw OCR and corrected text
- vision/model confidence
- model review flag

Example fields:

- `ocr_confidence`
- `text_similarity`
- `correction_score`
- `risky_text_change`
- `needs_review`


## 11. Decision Engine

Dialogue results can be classified approximately as:

- `auto_accepted`
- `needs_recovery`
- `auto_recovered`
- `needs_review`
- `verified`

High-confidence safe corrections can be accepted automatically.

Uncertain corrections should go through Auto-Recovery.

Remaining uncertain cases should go to human review.


## 12. Auto-Recovery

Auto-Recovery exists to re-check uncertain dialogue using image/context evidence.

It should NOT simply trust the previous correction.

A useful example discovered during development:

OCR / first correction:

`CHỜ DÙ LÀ LÚC ỐM ĐAU HAY BỆNH TẬT`

Recovery correctly determined:

`CHO DÙ LÀ LÚC ỐM ĐAU HAY BỆNH TẬT`

This demonstrates why semantically risky text changes need extra verification.


## 13. Human Review

Frontend contains or is developing:

`ReviewQueue.tsx`

Human review is intended only for uncertain cases.

Users should be able to verify or correct dialogue.

Example:

AI/OCR:

`NGUYỆN YẾU`

User correction:

`NGUYỆN YÊU`

Verified corrections should be treated as valuable Ground Truth.


## 14. Ground Truth

Model:

`backend/app/models/dialogue_ground_truth.py`

Ground truth records may include information such as:

- asset ID
- region ID
- raw OCR text
- AI text
- verified text
- correction score
- recovery confidence
- timestamp

Purpose:

Human corrections should become structured evaluation/improvement data rather than being discarded.


## 15. Day 8 Checkpoint

At the end of Day 8, the benchmark assets had the following state:

- `2.jpg` → vision completed, dialogue completed
- `3.jpg` → vision no_dialogue
- `4.jpg` → vision completed, dialogue completed
- `5.jpg` → vision completed, dialogue completed

Important Day 8 capabilities:

- Decision Engine
- risky text-change detection
- Auto-Recovery
- Human Review
- dialogue verification
- Ground Truth storage
- Ollama context overflow handling
- Markdown JSON response handling
- missing-block recovery
- low-quality OCR block handling
- no-dialogue page detection

Do not casually rewrite these systems without first understanding their behavior and tests.


## 16. Product UI Direction

There are two major interfaces.


### A. Main Dashboard

The main ComicAI Studio page should be clean and project-focused.

Concept:

ComicAI Studio

[ NEW PROJECT ]

Your Projects

[Project] [Project] [Project] [Project]

Project cards should eventually show:

- thumbnail
- project name
- Short / Long
- project status
- last modified time

Do NOT expose technical concepts such as OCR confidence, Vision Recovery, Ground Truth, etc. on the main dashboard unless needed for debugging/admin purposes.


### B. Project Editor

The project editor should resemble a professional video editor.

General layout:

Left:
Media Library

Center:
Video Preview

Right:
Subtitle / Inspector

Bottom:
Timeline

Conceptually:

| Media | Video Preview | Subtitle |
|       |               |          |
|       | Timeline      |          |

The user should remain in control even when AI automatically generates the video.


## 17. Media Library

The left panel should eventually support categories such as:

- Images
- Audio
- Text
- Meme
- Effects

Comic pages and generated media should appear here.


## 18. Synced Subtitle Editor

This is an important planned feature.

Voice playback and subtitles should be synchronized at word level.

Example data structure:

{
  "text": "THÌ CON CÓ CHẤP NHẬN NGUYỆN YÊU",
  "words": [
    {
      "text": "THÌ",
      "start": 0.00,
      "end": 0.25
    },
    {
      "text": "CON",
      "start": 0.25,
      "end": 0.47
    }
  ]
}

Desired UX:

- words already spoken → visually subdued
- currently spoken word → highlighted
- upcoming words → normal
- clicking a word seeks video/audio to that timestamp
- timeline movement updates subtitle position
- subtitle playback updates timeline
- user can edit subtitle directly

Example:

`NGUYỆN YẾU`

can be edited inline to:

`NGUYỆN YÊU`


## 19. Incremental Rebuild

When a user changes one subtitle word, ComicAI should eventually avoid rebuilding the entire video.

Desired dependency flow:

Subtitle correction

→ Ground Truth update

→ affected script/dialogue segment update

→ invalidate affected TTS segment

→ regenerate only affected voice segment

→ realign word timing

→ update timeline

This principle should influence future architecture.

Prefer segment-based processing over giant monolithic outputs.


## 20. Day 9 Direction

Day 9 begins the transition from text extraction to story understanding.

Main goals:

### Story Input Builder

Combine verified/clean dialogues from multiple pages into ordered story input.

Pages marked `no_dialogue` should be handled correctly.


### Story Analyzer

Extract structured story information such as:

- characters
- events
- relationships when supported
- scene meaning
- emotion
- important moments

Do NOT infer unsupported backstory.


### Story Grounding

Every important story claim should be traceable to source material.

Future data should preserve fields such as:

- `source_pages`
- source dialogue/region references where useful

If a claim cannot be grounded in source material, it should not silently become story fact.


### Short Script Engine

Initial focus is Short-form content.

Potential script structure:

HOOK

→ SETUP

→ DEVELOPMENT

→ PAYOFF

→ ENDING


### Style Engine

Initial potential presets:

- Funny
- Emotional
- Dramatic

Style may affect narration and later editing behavior, but must not change factual story content.


### Script Quality

Potential future metrics:

- grounding score
- hook score
- coherence score
- coverage score
- style score


## 21. Long-form Content

Long-form support is planned but is NOT the immediate focus.

Do not force Short and Long into identical generation/editing behavior.

Shared story understanding components are desirable, but Long-form may later use:

- different chunking
- lighter editing
- fewer memes/effects
- different pacing
- much larger context management


## 22. Internationalization

ComicAI Studio should not be architected as Vietnamese-only.

Vietnamese is an important initial language, but future support should allow:

- Japanese source
- Korean source
- English source
- Vietnamese output
- other languages later

Avoid hardcoding Vietnamese assumptions into core data models when unnecessary.


## 23. Agent Working Rules

IMPORTANT FOR CODEX:

### Before editing

1. Read this `AGENTS.md`.
2. Inspect the relevant existing files.
3. Trace the current execution path.
4. Understand existing behavior before proposing changes.
5. Prefer the smallest safe modification.


### Never assume

Do not assume a function/file exists merely because this document mentions it.

Inspect the repository.

The actual code is the source of truth.


### When the user reports an error

First:

1. inspect the traceback/error
2. identify the exact file
3. identify the exact function
4. inspect related callers
5. explain the likely cause

Then state clearly where the fix belongs.


### When explaining manual edits

The user prefers precise instructions.

Use:

- exact file path
- function name
- nearby recognizable code
- what goes BEFORE
- what goes AFTER

Do NOT merely say:

"Add this to vision_analyzer.py."

Instead say something like:

"In `backend/app/services/vision_analyzer.py`, inside
`analyze_comic_page()`, find this block:

[existing code]

Insert the following immediately after it and before:

[next existing code]"


### Avoid unnecessary rewrites

Do not replace entire working modules to fix a small bug.

Do not refactor unrelated code during bug fixes.


### Preserve working pipeline behavior

Before changing OCR/Vision/Dialogue systems, consider whether the change could break:

- reading order
- no-dialogue detection
- recovery
- human review
- Ground Truth
- existing completed benchmark pages


### Testing

When practical:

- run relevant tests
- run targeted commands
- inspect output
- report what was tested

Do not claim something works unless it was actually tested or the statement is clearly presented as an expectation.


### Database changes

Be careful with schema changes.

Before adding/changing SQLAlchemy models:

- inspect existing models
- inspect table creation/migration strategy
- inspect foreign keys
- ensure referenced models/tables are loaded when required

A previous issue occurred where SQLAlchemy could not resolve:

`assets.project_id -> projects.id`

because the referenced table metadata was not loaded in a standalone script.


### AI safety against hallucination

For all story-processing systems:

Never silently replace uncertainty with invented information.

Prefer:

- confidence
- source references
- recovery
- review

over confident hallucination.


## 24. Development Philosophy

ComicAI Studio should gradually move toward:

AI does most repetitive work.

Human reviews only uncertain or creative decisions.

The architecture should support:

AI automation + human control + traceability.

The target experience is:

Upload comic

→ AI understands it

→ AI creates a draft video

→ creator reviews/edit subtitles, script, voice and timeline

→ creator exports final video.

Do not optimize only for a demo.

Prefer architecture that can evolve into a maintainable product.
````
