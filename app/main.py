from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.db.database import init_db
from app.api.chat import router as chat_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="Monk-E Second Brain",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(
    documents_router
)

app.include_router(chat_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }