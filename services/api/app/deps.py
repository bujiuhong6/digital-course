import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db.models import AdminConfig
from .db.session import get_async_session_maker
from .services.teacher_session import parse_teacher_session_value


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_async_session_maker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_teacher(
    db: DBSession,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
) -> str:
    """已登录教师：校验 Cookie 与 `admin_config` 存在。"""
    if not teacher_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    data = parse_teacher_session_value(teacher_session)
    if data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    res = await db.execute(select(AdminConfig).where(AdminConfig.id == 1))
    if res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return "admin"


CurrentTeacher = Annotated[str, Depends(get_current_teacher)]


def require_bootstrap_token(provided: str | None) -> None:
    expected = settings.admin_bootstrap_token
    if not expected:
        return
    if not provided or not hmac.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
