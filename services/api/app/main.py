from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .db import dispose_engine, get_engine
from .db import models as _db_models  # noqa: F401 — register ORM metadata
from .routers import admin, chapter_admin, chat, student, teacher_ui


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    _ = settings.database_url
    yield
    await dispose_engine()


app = FastAPI(title="Teaching API", version="0.1.0", lifespan=lifespan)
# 学生 Tauri 开发（Vite 1420 端口）调 API 需 CORS；生产可收窄来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin.router)
app.include_router(chapter_admin.router)
app.include_router(chat.router)
app.include_router(teacher_ui.router)
app.include_router(student.router)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
