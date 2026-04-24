import hmac
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db.models import AdminConfig, Student
from .db.session import get_async_session_maker
from .services.student_jwt import decode_student_token
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


async def get_current_student(
    db: DBSession,
    authorization: str | None = Header(default=None),
) -> Student:
    """学生端：`Authorization: Bearer <JWT>`（设计 §3.2）。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    parts = authorization.split(None, 1)
    if len(parts) < 2:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    token = parts[1].strip()
    try:
        payload = decode_student_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    try:
        sid = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    r = await db.execute(select(Student).where(Student.id == sid))
    st = r.scalar_one_or_none()
    if st is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return st


CurrentStudent = Annotated[Student, Depends(get_current_student)]


async def teacher_cookie_valid(teacher_session: str | None, db: AsyncSession) -> bool:
    """供 HTML 教师页判断 Cookie 是否仍有效（`teacher_session` + `admin_config`）。"""
    if not teacher_session:
        return False
    data = parse_teacher_session_value(teacher_session)
    if data is None:
        return False
    res = await db.execute(select(AdminConfig).where(AdminConfig.id == 1))
    return res.scalar_one_or_none() is not None


def require_bootstrap_token(provided: str | None) -> None:
    expected = settings.admin_bootstrap_token
    if not expected:
        return
    if not provided or not hmac.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
