from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

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