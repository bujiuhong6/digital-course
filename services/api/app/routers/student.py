"""
学生：注册、**JWT 登录**、**GET /me**、**已发布章**、**cell 上报**、**本章完成**（设计 §4.2；任务 4–8）。

- 请求/响应 JSON 字段 **camelCase**。
- 会话：**`Authorization: Bearer <JWT>`**；`sub` 为学生 id（见 `Settings.student_jwt_exp_minutes`）。
- **单章**响应**不含**教师草稿（`sourceMaterial`、`aiGeneratedDraft` 等）。
"""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db.models import CellVerification, Chapter, ChapterCompletion, RosterEntry, Student
from ..deps import CurrentStudent, DBSession
from ..services.cell_eval import (
    is_cell_passing,
    required_cell_ids_from_content,
)
from ..services.crypto import decrypt_password, encrypt_password
from ..services.student_jwt import create_student_token

router = APIRouter(prefix="/v1/student", tags=["student"])

_STOUT_MAX = 200_000


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
        class_id=row.class_id,
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


# --- 任务 8：只读**已发布**章、cell 验证、章完成 ---


def _public_chapter_dict(ch: Chapter) -> dict:
    """学生可见；**无** `sourceMaterial` / 草稿等。"""
    return {
        "id": str(ch.id),
        "slug": ch.slug,
        "title": ch.title,
        "order": ch.order,
        "contentStatus": ch.content_status,
        "publishedContent": ch.published_content,
        "updatedAt": ch.updated_at.isoformat() if ch.updated_at else None,
    }


@router.get("/chapters")
async def list_published_chapters(me: CurrentStudent, db: DBSession) -> dict:
    r = await db.execute(
        select(Chapter)
        .where(Chapter.content_status == "published")
        .order_by(Chapter.order, Chapter.title)
    )
    rows = r.scalars().all()
    if not rows:
        return {"ok": True, "chapters": []}

    chapter_ids = [c.id for c in rows]

    cr = await db.execute(
        select(ChapterCompletion.chapter_id).where(
            ChapterCompletion.student_id == me.id,
            ChapterCompletion.chapter_id.in_(chapter_ids),
        )
    )
    completed_ids = {row[0] for row in cr.all()}

    pr = await db.execute(
        select(CellVerification.chapter_id)
        .where(
            CellVerification.student_id == me.id,
            CellVerification.chapter_id.in_(chapter_ids),
            CellVerification.run_ok.is_(True),
        )
        .distinct()
    )
    has_pass_ids = {row[0] for row in pr.all()}

    def _practice_status(cid: uuid.UUID) -> str:
        if cid in completed_ids:
            return "submitted"
        if cid in has_pass_ids:
            return "inProgress"
        return "pending"

    return {
        "ok": True,
        "chapters": [
            {
                "chapterId": str(c.id),
                "slug": c.slug,
                "title": c.title,
                "order": c.order,
                "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
                "practiceStatus": _practice_status(c.id),
            }
            for c in rows
        ],
    }


@router.get("/chapters/{chapter_id}")
async def get_published_chapter(
    me: CurrentStudent, db: DBSession, chapter_id: uuid.UUID
) -> dict:
    r = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.content_status == "published")
    )
    ch = r.scalar_one_or_none()
    if ch is None:
        raise HTTPException(status_code=404, detail="chapter not found or not published")
    return {"ok": True, "chapter": _public_chapter_dict(ch)}


class CellVerifyBody(BaseModel):
    model_config = {"populate_by_name": True}

    chapter_id: uuid.UUID = Field(alias="chapterId")
    cell_id: str = Field(min_length=1, max_length=128, alias="cellId")
    run_ok: bool = Field(alias="runOk")
    stdout: str | None = None
    stderr: str | None = None
    error_excerpt: str | None = Field(default=None, max_length=500, alias="errorExcerpt")
    elapsed_ms: int | None = Field(default=None, ge=0, alias="elapsedMs")


@router.post("/cells/verify")
async def verify_cell(
    me: CurrentStudent, db: DBSession, body: CellVerifyBody
) -> dict:
    """
    据 **§4.2** `passRule` 与上报计算是否过关，写入/更新 `cell_verifications`（**唯一**学生+章+cell，**只保留一条**即覆盖）。
    响应 `passed` 为**服务端**判定；`runOk` 为入库值（与 `passed` 一致）。
    """
    r = await db.execute(
        select(Chapter).where(
            Chapter.id == body.chapter_id,
            Chapter.content_status == "published",
        )
    )
    ch = r.scalar_one_or_none()
    if ch is None or ch.published_content is None or not isinstance(ch.published_content, dict):
        raise HTTPException(status_code=404, detail="chapter not found or not published")
    pc = ch.published_content
    out = (body.stdout or "")[:_STOUT_MAX]
    err_s = (body.stderr or "")[:_STOUT_MAX]
    passed = is_cell_passing(
        pc,
        body.cell_id,
        run_ok=body.run_ok,
        stdout=out,
        stderr=err_s,
    )
    ex = (body.error_excerpt or "")[:500] if body.error_excerpt else None
    now = datetime.now(timezone.utc)
    existing = await db.execute(
        select(CellVerification).where(
            CellVerification.student_id == me.id,
            CellVerification.chapter_id == body.chapter_id,
            CellVerification.cell_id == body.cell_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        db.add(
            CellVerification(
                student_id=me.id,
                chapter_id=body.chapter_id,
                cell_id=body.cell_id,
                run_ok=passed,
                at=now,
                stdout=out or None,
                error_excerpt=ex,
                elapsed_ms=body.elapsed_ms,
            )
        )
    else:
        row.run_ok = passed
        row.at = now
        row.stdout = out or None
        row.error_excerpt = ex
        row.elapsed_ms = body.elapsed_ms
    return {
        "ok": True,
        "passed": passed,
        "runOk": passed,
    }


@router.post("/chapters/{chapter_id}/complete", status_code=status.HTTP_200_OK)
async def complete_chapter(
    me: CurrentStudent, db: DBSession, chapter_id: uuid.UUID
) -> dict:
    """
    必做 **guideCell + extensionCell** 的 **全部** `cell` id 在库中 `run_ok=true` 才记完成；否则 **400**。
    已存在完成记录时 **200** 幂等。
    """
    r = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.content_status == "published")
    )
    ch = r.scalar_one_or_none()
    if ch is None or ch.published_content is None:
        raise HTTPException(status_code=404, detail="chapter not found or not published")
    pc = ch.published_content
    if not isinstance(pc, dict):
        raise HTTPException(status_code=400, detail="invalid published content")
    need = required_cell_ids_from_content(pc)
    if not need:
        raise HTTPException(status_code=400, detail="no cells in chapter")
    for cid in need:
        vr = await db.execute(
            select(CellVerification).where(
                CellVerification.student_id == me.id,
                CellVerification.chapter_id == chapter_id,
                CellVerification.cell_id == cid,
                CellVerification.run_ok.is_(True),
            )
        )
        if vr.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=400, detail="cells_not_all_passing",
            )
    ex = await db.execute(
        select(ChapterCompletion).where(
            ChapterCompletion.student_id == me.id,
            ChapterCompletion.chapter_id == chapter_id,
        )
    )
    if ex.scalar_one_or_none() is not None:
        return {"ok": True, "alreadyCompleted": True}
    db.add(
        ChapterCompletion(
            student_id=me.id,
            chapter_id=chapter_id,
        )
    )
    return {"ok": True, "alreadyCompleted": False}
