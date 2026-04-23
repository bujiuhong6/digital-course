"""
学生：注册、**JWT 登录**、**GET /me**（设计 §3.2；任务 4–5）。

- 请求/响应 JSON 字段 **camelCase**（如 `studentNo`, `accessToken`）。
- 会话：**`Authorization: Bearer <JWT>`**；`sub` 为学生 id，**约 15 分钟**有效（见 `Settings.student_jwt_exp_minutes`）。
"""

from __future__ import annotations

import hmac
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db.models import RosterEntry, Student
from ..deps import CurrentStudent, DBSession
from ..services.crypto import decrypt_password, encrypt_password
from ..services.student_jwt import create_student_token

router = APIRouter(prefix="/v1/student", tags=["student"])


class RegisterBody(BaseModel):
    model_config = {"populate_by_name": True}

    student_no: str = Field(alias="studentNo", min_length=1, max_length=64)
    full_name: str = Field(alias="fullName", min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class LoginBody(BaseModel):
    model_config = {"populate_by_name": True}

    student_no: str = Field(alias="studentNo", min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterBody, db: DBSession) -> dict:
    r = await db.execute(
        select(RosterEntry).where(
            RosterEntry.student_no == body.student_no,
            RosterEntry.deleted_at.is_(None),
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="roster_not_found",
        )
    if row.full_name != body.full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="roster_name_mismatch",
        )
    if row.student_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_registered",
        )
    st = Student(
        id=uuid.uuid4(),
        student_no=body.student_no,
        full_name=body.full_name,
        password_ciphertext=encrypt_password(body.password),
        must_change_password=False,
    )
    db.add(st)
    await db.flush()
    row.student_id = st.id
    row.status = "bound"
    return {"ok": True, "studentId": str(st.id)}


@router.post("/login")
async def student_login(body: LoginBody, db: DBSession) -> dict:
    """
    校验学号与口令后签发 **JWT**（**非**教师 Cookie）。

    响应含 `accessToken`、**秒**为单位的 `expiresIn`；用于后续 `Authorization: Bearer`。
    """
    r = await db.execute(select(Student).where(Student.student_no == body.student_no))
    st = r.scalar_one_or_none()
    if st is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials",
        )
    try:
        plain = decrypt_password(st.password_ciphertext)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials",
        )
    if not hmac.compare_digest(plain.encode("utf-8"), body.password.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials",
        )
    token, exp_sec = create_student_token(st.id)
    return {
        "ok": True,
        "accessToken": token,
        "expiresIn": exp_sec,
        "student": {
            "studentId": str(st.id),
            "studentNo": st.student_no,
            "fullName": st.full_name,
            "mustChangePassword": st.must_change_password,
        },
    }


@router.get("/me")
async def student_me(me: CurrentStudent) -> dict:
    """当前学生（需 **Bearer**）。"""
    return {
        "ok": True,
        "student": {
            "studentId": str(me.id),
            "studentNo": me.student_no,
            "fullName": me.full_name,
            "mustChangePassword": me.must_change_password,
        },
    }
