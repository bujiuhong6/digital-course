from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from .config import settings
from .db import dispose_engine, get_engine
from .db import models as _db_models  # noqa: F401 — register ORM metadata
from .routers import admin


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    _ = settings.database_url
    yield
    await dispose_engine()


app = FastAPI(title="Teaching API", version="0.1.0", lifespan=lifespan)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
