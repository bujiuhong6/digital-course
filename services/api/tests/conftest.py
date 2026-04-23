import asyncio
import os
from collections.abc import Generator
from pathlib import Path

# 在导入 `app` 前固定会话语签密钥，使 Cookie 验签在测试间一致。
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-teacher-cookie-consistent-123")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import models as _db_models  # noqa: F401
from app.db.base import Base
from app.deps import get_db
from app.main import app


def _test_engine_and_get_db(
    db_path: Path,
) -> tuple[AsyncEngine, object, object]:
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(
        url,
        echo=False,
        poolclass=NullPool,
    )
    sm = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def _get_db() -> object:
        async with sm() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    return engine, _get_db, _create


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "teach.db"
    engine, get_db_over, _create = _test_engine_and_get_db(db_path)
    asyncio.run(_create())
    app.dependency_overrides[get_db] = get_db_over
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
