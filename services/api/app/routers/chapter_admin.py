"""
章 CRUD、**AI 生成**草稿、**发布**校验（任务 6；设计 §4.1–4.2）。

需 `teacher_session`。JSON 字段 **camelCase**。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..config import settings
from ..db.models import Chapter, ChapterCompletion, Student
from ..deps import CurrentTeacher, DBSession
from ..services.chapter_gen import generate_chapter_draft
from ..services.chapter_json import validate_for_publish

router = APIRouter(prefix="/v1/admin/chapters", tags=["admin", "chapters"])

_SLUG_RE = re.compile(r"^[a-z0-9][-a-z0-9]{0,126}$")


def _slugify(s: str) -> str:
    # 仅 a-z0-9-，避免 CJK 留在 slug 里导致校验失败
    t = s.lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if not t:
        t = f"ch-{uuid.uuid4().hex[:12]}"
    return t[:128]


class ChapterCreateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=128, description="缺省由 title 生成")
    chapter_order: int = Field(default=0, alias="order", ge=0)
    source_material: str | None = Field(default=None, alias="sourceMaterial")


class ChapterUpdateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, min_length=1, max_length=255)
    chapter_order: int | None = Field(default=None, alias="order", ge=0)
    source_material: str | None = Field(default=None, alias="sourceMaterial")
    ai_generated_draft: dict | list | None = Field(default=None, alias="aiGeneratedDraft")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_chapter(_t: CurrentTeacher, db: DBSession, body: ChapterCreateBody) -> dict:
    slug = (body.slug or "").strip() or _slugify(body.title)
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slug must be lowercase slug a-z0-9-",
        )
    ex = await db.execute(select(Chapter).where(Chapter.slug == slug))
    if ex.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="slug exists")
    ch = Chapter(
        slug=slug,
        title=body.title,
        order=body.chapter_order,
        content_status="draft",
        source_material=body.source_material,
        ai_generated_draft=None,
    )
    db.add(ch)
    await db.flush()
    return _chapter_to_dict(ch)


@router.get("")
async def list_chapters(_t: CurrentTeacher, db: DBSession) -> dict:
    r = await db.execute(select(Chapter).order_by(Chapter.order, Chapter.title))
    rows = r.scalars().all()
    return {"ok": True, "chapters": [_chapter_to_dict(c) for c in rows]}


@router.get("/{chapter_id}")
async def get_chapter(
    _t: CurrentTeacher, db: DBSession, chapter_id: uuid.UUID
) -> dict:
    ch = await _get_chapter_or_404(db, chapter_id)
    return {"ok": True, "chapter": _chapter_to_dict(ch)}


@router.get("/{chapter_id}/completions")
async def list_chapter_completions(
    _t: CurrentTeacher,
    db: DBSession,
    chapter_id: uuid.UUID,
    class_id: uuid.UUID | None = Query(default=None, alias="classId"),
) -> dict:
    """学生端「标记本章完成」后写入 `chapter_completions`；教师可查询提交记录。可选 `classId` 仅该班。"""
    ch = await _get_chapter_or_404(db, chapter_id)
    q = (
        select(ChapterCompletion, Student)
        .join(Student, Student.id == ChapterCompletion.student_id)
        .where(ChapterCompletion.chapter_id == chapter_id)
    )
    if class_id is not None:
        q = q.where(Student.class_id == class_id)
    r = await db.execute(
        q.order_by(ChapterCompletion.completed_at.desc())
    )
    rows = r.all()
    return {
        "ok": True,
        "chapterId": str(ch.id),
        "chapterTitle": ch.title,
        "completions": [
            {
                "studentId": str(st.id),
                "studentNo": st.student_no,
                "fullName": st.full_name,
                "completedAt": cc.completed_at.isoformat(),
            }
            for cc, st in rows
        ],
    }


@router.patch("/{chapter_id}")
async def patch_chapter(
    _t: CurrentTeacher,
    db: DBSession,
    chapter_id: uuid.UUID,
    body: ChapterUpdateBody,
) -> dict:
    ch = await _get_chapter_or_404(db, chapter_id)
    if body.title is not None:
        ch.title = body.title
    if body.chapter_order is not None:
        ch.order = body.chapter_order
    if body.source_material is not None:
        ch.source_material = body.source_material
    if body.ai_generated_draft is not None:
        ch.ai_generated_draft = body.ai_generated_draft
    ch.updated_at = datetime.now(timezone.utc)
    return {"ok": True, "chapter": _chapter_to_dict(ch)}


@router.delete("/{chapter_id}", status_code=status.HTTP_200_OK)
async def delete_chapter(
    _t: CurrentTeacher, db: DBSession, chapter_id: uuid.UUID
) -> dict:
    ch = await _get_chapter_or_404(db, chapter_id)
    await db.delete(ch)
    return {"ok": True}


@router.post("/{chapter_id}/generate")
async def generate_chapter(
    _t: CurrentTeacher, db: DBSession, chapter_id: uuid.UUID
) -> dict:
    ch = await _get_chapter_or_404(db, chapter_id)
    parsed, raw, err = await generate_chapter_draft(ch.source_material, model=None)
    ch.generator_prompt_version = settings.generator_prompt_version
    ch.generator_model = settings.chapter_gen_model
    ch.updated_at = datetime.now(timezone.utc)
    if err is not None and parsed is None:
        ch.ai_generated_raw = raw
        ch.ai_generated_draft = None
        ch.content_status = "draft_invalid"
        return {
            "ok": False,
            "error": err,
            "chapter": _chapter_to_dict(ch),
        }
    if parsed is not None:
        ch.ai_generated_draft = parsed
        ch.ai_generated_raw = raw
        ch.content_status = "draft"
        return {"ok": True, "chapter": _chapter_to_dict(ch)}
    ch.ai_generated_raw = raw
    ch.content_status = "draft_invalid"
    return {"ok": False, "error": err or "unknown", "chapter": _chapter_to_dict(ch)}


@router.post("/{chapter_id}/publish")
async def publish_chapter(_t: CurrentTeacher, db: DBSession, chapter_id: uuid.UUID) -> dict:
    ch = await _get_chapter_or_404(db, chapter_id)
    draft = ch.ai_generated_draft
    if draft is None:
        raise HTTPException(
            status_code=400, detail="no ai_generated_draft; generate or paste draft first",
        )
    if not isinstance(draft, dict):
        raise HTTPException(status_code=400, detail="ai_generated_draft must be an object")
    res = validate_for_publish(draft)
    if not res.ok or res.content is None:
        raise HTTPException(
            status_code=400,
            detail={"message": res.error or "validation failed", "warnings": res.warnings},
        )
    ch.published_content = res.content
    ch.content_status = "published"
    ch.updated_at = datetime.now(timezone.utc)
    return {
        "ok": True,
        "warnings": res.warnings,
        "chapter": _chapter_to_dict(ch),
    }


@router.post("/{chapter_id}/unpublish")
async def unpublish_chapter(_t: CurrentTeacher, db: DBSession, chapter_id: uuid.UUID) -> dict:
    ch = await _get_chapter_or_404(db, chapter_id)
    if ch.content_status != "published" or not ch.published_content:
        raise HTTPException(
            status_code=400,
            detail="未查到已发布的章节练习",
        )
    ch.published_content = None
    ch.content_status = "draft"
    ch.updated_at = datetime.now(timezone.utc)
    return {"ok": True, "chapter": _chapter_to_dict(ch)}


async def _get_chapter_or_404(db, chapter_id: uuid.UUID) -> Chapter:
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    return ch


def _chapter_to_dict(ch: Chapter) -> dict:
    return {
        "id": str(ch.id),
        "slug": ch.slug,
        "title": ch.title,
        "order": ch.order,
        "contentStatus": ch.content_status,
        "sourceMaterial": ch.source_material,
        "aiGeneratedDraft": ch.ai_generated_draft,
        "aiGeneratedRaw": ch.ai_generated_raw,
        "generatorPromptVersion": ch.generator_prompt_version,
        "generatorModel": ch.generator_model,
        "publishedContent": ch.published_content,
        "updatedAt": ch.updated_at.isoformat() if ch.updated_at else None,
    }
