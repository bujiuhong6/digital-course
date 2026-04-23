"""
学生：注册/绑定（设计 §3.2–3.3；任务 4）。**Bearer/JWT 在任务 5**；本阶段仅 `POST /register`。
JSON 请求体字段为 **camelCase**（`studentNo`, `fullName`, `password`）。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db.models import RosterEntry, Student
from ..deps import DBSession
from ..services.crypto import encrypt_password

router = APIRouter(prefix="/v1/student", tags=["student"])


class RegisterBody(BaseModel):
    model_config = {"populate_by_name": True}

    student_no: str = Field(alias="studentNo", min_length=1, max_length=64)
    full_name: str = Field(alias="fullName", min_length=1, max_length=255)
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
