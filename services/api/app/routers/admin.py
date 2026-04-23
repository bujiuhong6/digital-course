"""
教师管理 API。鉴权：仅 **HttpOnly 签名 Cookie** `teacher_session`（无教师端 Bearer，设计 §3.1）。

登录与 bootstrap 成功后会 **Set-Cookie: teacher_session=...**（HMAC-SHA256 签名，见 `app.services.teacher_session`）。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from ..config import settings
from ..db.models import AdminConfig
from ..deps import CurrentTeacher, DBSession, require_bootstrap_token
from ..services.teacher_session import create_teacher_session_value

try:
    from passlib.context import CryptContext
except ImportError:  # pragma: no cover
    CryptContext = None  # type: ignore[misc, assignment]

router = APIRouter(prefix="/v1/admin", tags=["admin"])

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None


class PasswordBody(BaseModel):
    model_config = {"populate_by_name": True}

    password: str = Field(min_length=1, description="管理员密码", alias="password")


def _set_teacher_cookie(response: Response) -> None:
    val = create_teacher_session_value()
    response.set_cookie(
        key="teacher_session",
        value=val,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        secure=settings.admin_cookie_secure,
        path="/",
    )


@router.post("/bootstrap", status_code=status.HTTP_201_CREATED)
async def bootstrap(
    body: PasswordBody,
    response: Response,
    db: DBSession,
    x_admin_bootstrap_token: str | None = Header(default=None, alias="X-Admin-Bootstrap-Token"),
) -> dict:
    """
    首次写入 `admin_config`。**若表已有配置则 403。**

    当环境配置 `admin_bootstrap_token` 时，须同时请求头
    `X-Admin-Bootstrap-Token: <同值>`，否则 403。
    """
    require_bootstrap_token(x_admin_bootstrap_token)
    r = await db.execute(select(AdminConfig).where(AdminConfig.id == 1))
    if r.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="admin already bootstrapped",
        )
    if _pwd is None:
        raise RuntimeError("passlib not installed")
    h = _pwd.hash(body.password)
    db.add(AdminConfig(id=1, password_hash=h))
    _set_teacher_cookie(response)
    return {"ok": True}


@router.post("/login")
async def login(body: PasswordBody, response: Response, db: DBSession) -> dict:
    """校验 bcrypt 后设置 `teacher_session`（HttpOnly、签名，见模块文档字符串）。"""
    r = await db.execute(select(AdminConfig).where(AdminConfig.id == 1))
    row = r.scalar_one_or_none()
    if row is None or _pwd is None or not _pwd.verify(body.password, row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials",
        )
    await db.execute(
        update(AdminConfig).where(AdminConfig.id == 1).values(updated_at=func.now())
    )
    _set_teacher_cookie(response)
    return {"ok": True}


@router.get("/me")
async def me(teacher: CurrentTeacher) -> dict:
    return {"ok": True, "role": "admin", "sub": teacher}
