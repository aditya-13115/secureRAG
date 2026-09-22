from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.db.database import init_db


app = FastAPI(
    title="Monk-E Second Brain",
    version="0.1.0",
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(
    documents_router
)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }