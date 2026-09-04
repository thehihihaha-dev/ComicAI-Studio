"""FastAPI router for Web Editor interactive endpoints (/api/v1/editor).

Endpoints:
- POST /api/v1/editor/draft: Generates Timeline JSON Contract from uploaded comic image.
- POST /api/v1/editor/render: Synthesizes final 9:16 vertical MP4 video from client Timeline Contract.
"""
from __future__ import annotations

import logging
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from fastapi import APIRouter, HTTPException, Request, status

try:
    from src.api.timeline_schema import (
        DraftRequest,
        RenderRequest,
        RenderResponse,
        TimelineContract,
    )
    from src.services.pipeline_orchestrator import ComicPipelineOrchestrator
except ModuleNotFoundError:
    from backend.src.api.timeline_schema import (
        DraftRequest,
        RenderRequest,
        RenderResponse,
        TimelineContract,
    )
    from backend.src.services.pipeline_orchestrator import ComicPipelineOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/editor", tags=["Web Editor"])


@router.post(
    "/draft",
    response_model=TimelineContract,
    status_code=status.HTTP_200_OK,
    summary="Generate Interactive Timeline JSON Contract",
    description="Ingests a comic page image, executes the full pipeline, and returns the editable Timeline Contract.",
)
async def generate_editor_draft(request: Request) -> TimelineContract:
    """Generate TimelineContract from multipart file upload or JSON request."""
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        project_id = str(form.get("project_id", "default_project"))
        page_order = int(form.get("page_order", 1))

        if uploaded_file and hasattr(uploaded_file, "filename") and uploaded_file.filename:
            save_dir = ROOT / "backend" / "uploads"
            save_dir.mkdir(parents=True, exist_ok=True)
            safe_name = f"{uuid.uuid4()}_{Path(uploaded_file.filename).name}"
            target_path = save_dir / safe_name
            content = await uploaded_file.read()
            target_path.write_bytes(content)
            img_path = target_path
        elif form.get("image_path"):
            img_path = Path(str(form.get("image_path")))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'file' upload or 'image_path' must be provided in form data.",
            )
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload.",
            )

        img_path_str = body.get("image_path")
        if not img_path_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'image_path' is required in JSON body.",
            )
        img_path = Path(img_path_str)
        project_id = str(body.get("project_id", "default_project"))
        page_order = int(body.get("page_order", 1))

    # Resolve image path
    if not img_path.is_file():
        if (ROOT / img_path).is_file():
            img_path = ROOT / img_path
        elif (ROOT / "backend" / img_path).is_file():
            img_path = ROOT / "backend" / img_path
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image file not found at: {img_path}",
            )

    orchestrator = ComicPipelineOrchestrator()
    try:
        timeline = orchestrator.generate_draft(
            image_path=img_path,
            project_id=project_id,
            page_order=page_order,
        )
        return timeline
    except Exception as exc:
        logger.exception("Error executing pipeline draft generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline draft generation failed: {exc}",
        )


@router.post(
    "/render",
    response_model=RenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Render Final Broadcast 9:16 Video",
    description="Synthesizes final broadcast-ready 9:16 vertical MP4 video strictly adhering to the Timeline Contract.",
)
async def render_editor_video(payload: RenderRequest) -> RenderResponse:
    """Render 9:16 MP4 video from the client-submitted TimelineContract."""
    orchestrator = ComicPipelineOrchestrator(
        canvas_size=payload.timeline.canvas_size,
        fps=payload.timeline.fps,
    )

    out_dir = ROOT / "artifacts" / "video" / "day18"
    out_dir.mkdir(parents=True, exist_ok=True)

    if payload.output_filename:
        safe_fname = Path(payload.output_filename).name
        if not safe_fname.endswith(".mp4"):
            safe_fname += ".mp4"
    else:
        pid = payload.timeline.project_id
        page = payload.timeline.page_id
        safe_fname = f"render_{pid}_p{page}_{uuid.uuid4().hex[:8]}.mp4"

    output_path = out_dir / safe_fname

    try:
        render_summary = orchestrator.render_final_video(
            timeline=payload.timeline,
            output_path=output_path,
        )
        return RenderResponse(**render_summary)
    except Exception as exc:
        logger.exception("Error synthesizing video: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video rendering failed: {exc}",
        )

