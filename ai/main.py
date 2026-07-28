from fastapi import FastAPI

app = FastAPI(
    title="ComicAI Studio AI Engine",
    version="0.0.1",
)


@app.get("/")
def root():
    return {
        "name": "ComicAI Studio AI Engine",
        "status": "online",
        "version": "0.0.1",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }