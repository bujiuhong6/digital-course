from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette import status
from starlette.responses import Response

from ..db.models import PostExercise, PostExerciseSubmission, Student
from ..deps import CurrentTeacher, DBSession
from ..services.post_exercise_json import (
    default_post_exercise_content,
    validate_post_exercise_content,
)


router = APIRouter(tags=["admin", "post-exercises"])
templates = Jinja2Templates(directory="app/templates")


def _wants_htmx(request: Request) -> bool:
    return (request.headers.get("hx-request") or "").lower() == "true"


def _post_exercise_edit_flash(request: Request) -> tuple[str | None, str | None]:
    qp = request.query_params
    if qp.get("error") == "1":
        return (
            "JSON 无法发布，请确认题型数量（单选 3-5、主观 1、代码 1-2）、题目 id、分值与标准答案完整。",
            "error",
        )
    if qp.get("draft_error") == "1":
        return "草稿保存失败：JSON 无法解析或不符合题目结构要求。", "error"
    if qp.get("pub_ok") == "1":
        return "发布成功。", "ok"
    if qp.get("saved") == "1":
        return "草稿已保存。", "ok"
    if qp.get("renamed") == "1":
        return "标题已更新。", "ok"
    if qp.get("rename_err") == "1":
        return "标题无效（须为 1～255 个非空字符）。", "error"
    if qp.get("unpub_ok") == "1":
        return "已取消发布，学生端暂时看不到本课后作业。", "ok"
    if qp.get("unpub_err") == "1":
        return "当前不是已发布状态。", "warn"
    return None, None


class PostExerciseCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    order: int = Field(default=0, ge=0)


class PostExercisePublishBody(BaseModel):
    questions: list[dict] = Field(min_length=1, max_length=20)


def _exercise_to_dict(ex: PostExercise) -> dict:
    return {
        "exerciseId": str(ex.id),
        "title": ex.title,
        "order": ex.order,
        "status": ex.status,
        "content": ex.published_content,
        "updatedAt": ex.updated_at.isoformat() if ex.updated_at else None,
    }


async def _get_or_404(db: DBSession, exercise_id: uuid.UUID) -> PostExercise:
    row = (await db.execute(select(PostExercise).where(PostExercise.id == exercise_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="post_exercise_not_found")
    return row


@router.post("/v1/admin/post-exercises", status_code=status.HTTP_201_CREATED)
async def create_post_exercise(_t: CurrentTeacher, db: DBSession, body: PostExerciseCreateBody) -> dict:
    ex = PostExercise(title=body.title, order=body.order, status="draft")
    db.add(ex)
    await db.flush()
    return {"ok": True, **_exercise_to_dict(ex)}


@router.post("/v1/admin/post-exercises/{exercise_id}/publish")
async def publish_post_exercise(
    _t: CurrentTeacher,
    db: DBSession,
    exercise_id: uuid.UUID,
    body: PostExercisePublishBody,
) -> dict:
    ex = await _get_or_404(db, exercise_id)
    content = validate_post_exercise_content({"version": 1, "questions": body.questions})
    ex.published_content = content
    ex.status = "published"
    ex.updated_at = datetime.now(timezone.utc)
    return {"ok": True, "exercise": _exercise_to_dict(ex)}


@router.get("/teacher/post-exercises", response_class=HTMLResponse)
async def page_post_exercises(request: Request, _t: CurrentTeacher, db: DBSession):
    rows = (
        await db.execute(select(PostExercise).order_by(PostExercise.order, PostExercise.title))
    ).scalars().all()
    return templates.TemplateResponse(
        request,
        "teacher/post_exercises.html",
        {"exercises": rows, "flash": request.query_params.get("flash")},
    )


@router.post("/teacher/post-exercises/new")
async def post_exercise_new(_t: CurrentTeacher, db: DBSession, title: str = Form("新课后作业")):
    ex = PostExercise(title=title.strip() or "新课后作业", status="draft")
    db.add(ex)
    await db.flush()
    return RedirectResponse(f"/teacher/post-exercises/{ex.id}/edit", status_code=303)


@router.get("/teacher/post-exercises/{exercise_id}/edit", response_class=HTMLResponse)
async def page_post_exercise_edit(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    exercise_id: uuid.UUID,
):
    ex = await _get_or_404(db, exercise_id)
    content = ex.published_content or default_post_exercise_content()
    ui_flash, ui_flash_level = _post_exercise_edit_flash(request)
    return templates.TemplateResponse(
        request,
        "teacher/post_exercise_edit.html",
        {
            "exercise": ex,
            "template_json": json.dumps(default_post_exercise_content(), ensure_ascii=False, indent=2),
            "content_json": json.dumps(content, ensure_ascii=False, indent=2),
            "ui_flash": ui_flash,
            "ui_flash_level": ui_flash_level,
        },
    )


@router.post("/teacher/post-exercises/{exercise_id}/rename")
async def post_exercise_rename(
    _t: CurrentTeacher,
    db: DBSession,
    exercise_id: uuid.UUID,
    title: str = Form(""),
):
    ex = await _get_or_404(db, exercise_id)
    t = (title or "").strip()
    if not t or len(t) > 255:
        return RedirectResponse(
            url=f"/teacher/post-exercises/{exercise_id}/edit?rename_err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ex.title = t
    ex.updated_at = datetime.now(timezone.utc)
    return RedirectResponse(
        url=f"/teacher/post-exercises/{exercise_id}/edit?renamed=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/teacher/post-exercises/{exercise_id}/save-draft")
async def post_exercise_save_draft(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    exercise_id: uuid.UUID,
    draft: str = Form(""),
):
    ex = await _get_or_404(db, exercise_id)
    htmx = _wants_htmx(request)
    try:
        content = validate_post_exercise_content(json.loads(draft))
    except (json.JSONDecodeError, HTTPException):
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "error", "message": "草稿保存失败：JSON 无法解析或不符合题目结构要求。"},
            )
        return RedirectResponse(
            url=f"/teacher/post-exercises/{exercise_id}/edit?draft_error=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ex.published_content = content
    ex.status = "draft"
    ex.updated_at = datetime.now(timezone.utc)
    loc = f"/teacher/post-exercises/{exercise_id}/edit?saved=1"
    if htmx:
        return Response(status_code=200, content=b"", headers={"HX-Redirect": loc})
    return RedirectResponse(url=loc, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/teacher/post-exercises/{exercise_id}/publish")
async def post_exercise_publish(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    exercise_id: uuid.UUID,
    draft: str = Form(""),
):
    ex = await _get_or_404(db, exercise_id)
    htmx = _wants_htmx(request)
    try:
        content = validate_post_exercise_content(json.loads(draft))
    except (json.JSONDecodeError, HTTPException):
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "error", "message": "发布失败：JSON 无法解析或不符合题目结构要求。"},
            )
        return RedirectResponse(f"/teacher/post-exercises/{exercise_id}/edit?error=1", status_code=303)
    ex.published_content = content
    ex.status = "published"
    ex.updated_at = datetime.now(timezone.utc)
    loc = f"/teacher/post-exercises/{exercise_id}/edit?pub_ok=1"
    if htmx:
        return Response(status_code=200, content=b"", headers={"HX-Redirect": loc})
    return RedirectResponse(url=loc, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/teacher/post-exercises/{exercise_id}/unpublish")
async def post_exercise_unpublish(
    request: Request, _t: CurrentTeacher, db: DBSession, exercise_id: uuid.UUID
):
    ex = await _get_or_404(db, exercise_id)
    htmx = _wants_htmx(request)
    if ex.status != "published":
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "warn", "message": "当前不是已发布状态。"},
            )
        return RedirectResponse(
            url=f"/teacher/post-exercises/{exercise_id}/edit?unpub_err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ex.status = "draft"
    ex.updated_at = datetime.now(timezone.utc)
    loc = f"/teacher/post-exercises/{exercise_id}/edit?unpub_ok=1"
    if htmx:
        return Response(status_code=200, content=b"", headers={"HX-Redirect": loc})
    return RedirectResponse(url=loc, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/teacher/post-exercises/{exercise_id}/delete")
async def post_exercise_delete(_t: CurrentTeacher, db: DBSession, exercise_id: uuid.UUID):
    ex = await _get_or_404(db, exercise_id)
    await db.delete(ex)
    return RedirectResponse("/teacher/post-exercises?flash=deleted", status_code=303)


@router.get("/teacher/post-exercises/{exercise_id}/submissions", response_class=HTMLResponse)
async def page_post_exercise_submissions(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    exercise_id: uuid.UUID,
):
    ex = await _get_or_404(db, exercise_id)
    rows = (
        await db.execute(
            select(PostExerciseSubmission, Student)
            .join(Student, Student.id == PostExerciseSubmission.student_id)
            .where(PostExerciseSubmission.exercise_id == exercise_id)
            .order_by(PostExerciseSubmission.submitted_at.desc())
        )
    ).all()
    return templates.TemplateResponse(
        request,
        "teacher/post_exercise_submissions.html",
        {"exercise": ex, "rows": rows},
    )


@router.get("/teacher/post-exercises/submissions.csv")
async def export_post_exercise_scores(_t: CurrentTeacher, db: DBSession) -> Response:
    rows = (
        await db.execute(
            select(PostExerciseSubmission, Student, PostExercise)
            .join(Student, Student.id == PostExerciseSubmission.student_id)
            .join(PostExercise, PostExercise.id == PostExerciseSubmission.exercise_id)
            .order_by(PostExerciseSubmission.submitted_at.desc())
        )
    ).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["studentNo", "fullName", "exerciseTitle", "score", "submittedAt"])
    for sub, st, ex in rows:
        writer.writerow([st.student_no, st.full_name, ex.title, sub.score, sub.submitted_at.isoformat()])
    # UTF-8 BOM：Excel 等软件可正确识别中文列。
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="post-exercise-scores.csv"'},
    )
