import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
from app.routers import projects
from app.routers.assets import router as assets_router
from app.routers.ocr_benchmark_reviews import router as ocr_benchmark_reviews_router
from app.routers.reading_order_benchmark_reviews import router as reading_order_benchmark_reviews_router
from app.routers.reader_correctness_reviews import router as reader_correctness_reviews_router
from app.routers.reader_logical_reviews import router as reader_logical_reviews_router
from app.routers.reader_router_validation_reviews import router as reader_router_validation_reviews_router
from app.routers.panel_ground_truth_reviews import router as panel_ground_truth_reviews_router
try:
    from src.api.routes.editor import router as editor_router
except ModuleNotFoundError:
    from backend.src.api.routes.editor import router as editor_router
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="ComicAI Studio API",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(assets_router)
app.include_router(ocr_benchmark_reviews_router)
app.include_router(reading_order_benchmark_reviews_router)
app.include_router(reader_correctness_reviews_router)
app.include_router(reader_logical_reviews_router)
app.include_router(reader_router_validation_reviews_router)
app.include_router(panel_ground_truth_reviews_router)
app.include_router(editor_router)

from starlette.responses import Response
from typing import Any

class CORSStaticFiles(StaticFiles):
    """StaticFiles wrapper adding CORS headers for cross-origin asset loading."""
    async def get_response(self, path: str, scope: Any) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

from pathlib import Path
uploads_dir = Path(__file__).resolve().parent / "uploads"
if not uploads_dir.exists():
    uploads_dir = Path("uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", CORSStaticFiles(directory=str(uploads_dir)), name="uploads")

artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"
artifacts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", CORSStaticFiles(directory=str(artifacts_dir)), name="artifacts")

AI_ENGINE_URL = "http://127.0.0.1:8001"


@app.get("/")
def root():
    return {
        "name": "ComicAI Studio API",
        "status": "online",
        "version": "0.0.1",
    }


@app.get("/health")
async def health():
    ai_status = "offline"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{AI_ENGINE_URL}/health")

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "healthy":
                ai_status = "online"

    except httpx.HTTPError:
        ai_status = "offline"

    return {
        "status": "healthy",
        "ai_engine": ai_status,
    }

