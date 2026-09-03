# Copilot / Agent Instructions — ComicAI Studio

Purpose: short, actionable guidance so code agents are immediately productive in this repo.

**Big Picture**
- Backend: `backend/` (FastAPI + SQLAlchemy). Key services under `backend/app/services/` (e.g. `vision_analyzer.py`, `ollama_vision.py`, `dialogue_corrector.py`).
- AI service: `ai/` (FastAPI) — small, separate process for model orchestration.
- Frontend: `frontend/` (Next.js, TypeScript, Tailwind) — project editor under `frontend/app/projects/[id]/`.
- Orchestration and policies: `ai-workflow/` holds task/state artifacts and role contracts; read `ai-workflow/STATE.json` before changes.

**Immediate developer workflows**
- Run backend tests from repo root:
  - `backend/.venv/bin/python -m unittest discover -s backend/tests -t backend`
- Run a targeted backend test (from `backend/`):
  - `.venv/bin/python -m unittest tests.<module>`
- Start backend dev server (from `backend/`):
  - `.venv/bin/python -m uvicorn main:app --reload --port 8000`
- Start AI service (from `ai/`):
  - `.venv/bin/python -m uvicorn main:app --reload --port 8001`
- Start frontend (from `frontend/`):
  - `npm run dev`
- Bring up local Postgres for integration: `docker compose -f docker/docker-compose.yml up -d`

**Project-specific conventions & patterns**
- Do not invent or change OCR `block_id` values: the vision system must preserve block IDs.
- Pages can be legitimately `no_dialogue`; do not treat that as an error. Search for `vision_status = "no_dialogue"` behavior in tests and services.
- Vision/LLM responses may include JSON wrapped in Markdown fences — parser tolerates fenced JSON (see `ollama_vision.py`).
- There is explicit auto-recovery and human-review flow: prefer marking `needs_recovery`/`needs_review` rather than auto-accepting risky changes.
- Never automatically commit or push changes as part of agent work; follow ai-workflow handoff rules (`ARCHITECT -> CODER -> REVIEWER -> HUMAN APPROVAL`).

**Integration points to inspect when changing behavior**
- `backend/app/services/vision_analyzer.py` — reading-order / region grouping logic.
- `backend/app/services/ollama_vision.py` — model endpoint, context length (`num_ctx`) handling, and JSON-fenced responses.
- `backend/app/services/dialogue_corrector.py` — correction rules, output fields (`raw_text`, `clean_text`, `needs_review`, `confidence`).
- `ai/main.py` — AI service entry; check how the AI and backend communicate.
- `ai-workflow/STATE.json` and `ai-workflow/roles/*` — required pre-change checks and handoff rules.
- Frontend editor files: `frontend/app/projects/[id]/page.tsx`, `AssetUploader.tsx`, `ReviewQueue.tsx` for human-review UI patterns.

**Testing & safety notes**
- The backend test harness uses Python `unittest` discovery. Run only tests relevant to `CURRENT_TASK.md`.
- Scripts with `benchmark` in their name may be expensive; do not run them without explicit permission in `CURRENT_TASK.md`.
- Do not start Ollama or other local/paid models unless `CURRENT_TASK.md` or `ai-workflow` grants `ALLOWED` for the intended run.

**PR / edit guidance for agents**
- Prefer small, focused patches that fix the root cause. Do not refactor unrelated modules.
- When editing pipeline code, preserve existing data flows (reading order, ground-truth, review flags).
- When adding fields to models or DB migrations, inspect `backend/.env`, SQLAlchemy models, and migrations; avoid silent schema mismatches.

**Quick links (examples)**
- Vision analyzer: `backend/app/services/vision_analyzer.py`
- Ollama integration: `backend/app/services/ollama_vision.py`
- Dialogue correction: `backend/app/services/dialogue_corrector.py`
- AI service entry: `ai/main.py`
- Workflow state and roles: `ai-workflow/STATE.json`, `ai-workflow/roles/`

If anything in this guidance is unclear or you want more examples (e.g., typical test file, a representative failing test, or a small PR example), tell me which area to expand. I can update this file accordingly.
