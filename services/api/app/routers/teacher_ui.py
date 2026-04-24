"""
教师 **Web**（Jinja2 + **HTMX**；任务 10）。路径前缀 **`/teacher`**；需 Cookie `teacher_session`。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update

from ..config import settings
from ..db.models import AdminConfig, Chapter, RosterEntry
from ..deps import DBSession, require_bootstrap_token, teacher_cookie_valid
from ..services.chapter_gen import generate_chapter_draft
from ..services.chapter_json import validate_for_publish, sample_published_v1

from .admin import (  # noqa: PLC2701
    _load_rows_from_file,
    _set_teacher_cookie,
    _upsert_roster_row,
)
from .admin import _pwd
from .chapter_admin import _SLUG_RE, _slugify

router = APIRouter(prefix="/teacher", tags=["teacher-ui"])
templates = Jinja2Templates(directory="app/templates")


def _redirect_login() -> RedirectResponse:
    return RedirectResponse(url="/teacher/login", status_code=status.HTTP_302_FOUND)


@router.get("/login", response_class=HTMLResponse)
async def page_login(
    request: Request,
    db: DBSession,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if await teacher_cookie_valid(teacher_session, db):
        return RedirectResponse(url="/teacher", status_code=status.HTTP_302_FOUND)
    r = await db.execute(select(AdminConfig).where(AdminConfig.id == 1))
    need_bootstrap = r.scalar_one_or_none() is None
    return templates.TemplateResponse(
        request,
        "teacher/login.html",
        {
            "need_bootstrap": need_bootstrap,
            "bootstrap_token_required": bool(settings.admin_bootstrap_token),
            "login_error": None,
        },
    )


@router.post("/bootstrap")
async def post_bootstrap(
    request: Request,
    db: DBSession,
    password: str = Form(""),
    bootstrap_token: str = Form(""),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if await teacher_cookie_valid(teacher_session, db):
        return RedirectResponse(url="/teacher", status_code=status.HTTP_302_FOUND)
    r = await db.execute(select(AdminConfig).where(AdminConfig.id == 1))
    if r.scalar_one_or_none() is not None:
        return templates.TemplateResponse(
            request,
            "teacher/login.html",
            {
                "need_bootstrap": False,
                "bootstrap_token_required": bool(settings.admin_bootstrap_token),
                "login_error": "管理员已存在，请直接登录。",
            },
        )
    require_bootstrap_token(bootstrap_token or None)
    if not password or _pwd is None:
        return templates.TemplateResponse(
            request,
            "teacher/login.html",
            {
                "need_bootstrap": True,
                "bootstrap_token_required": bool(settings.admin_bootstrap_token),
                "login_error": "密码无效或环境未装 passlib。",
            },
        )
    db.add(AdminConfig(id=1, password_hash=_pwd.hash(password)))
    redir = RedirectResponse(url="/teacher", status_code=status.HTTP_303_SEE_OTHER)
    _set_teacher_cookie(redir)
    return redir


@router.post("/do-login")
async def post_login(
    request: Request,
    db: DBSession,
    password: str = Form(""),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if await teacher_cookie_valid(teacher_session, db):
        return RedirectResponse(url="/teacher", status_code=status.HTTP_303_SEE_OTHER)
    row = (await db.execute(select(AdminConfig).where(AdminConfig.id == 1))).scalar_one_or_none()
    if row is None:
        return templates.TemplateResponse(
            request,
            "teacher/login.html",
            {
                "need_bootstrap": True,
                "bootstrap_token_required": bool(settings.admin_bootstrap_token),
                "login_error": "尚未创建管理员，请先在下方完成首次设置。",
            },
        )
    if _pwd is None or not _pwd.verify(password, row.password_hash):
        return templates.TemplateResponse(
            request,
            "teacher/login.html",
            {
                "need_bootstrap": False,
                "bootstrap_token_required": bool(settings.admin_bootstrap_token),
                "login_error": "密码错误。"
                if _pwd is not None
                else "密码校验不可用（请检查 passlib 环境）。",
            },
        )
    await db.execute(
        update(AdminConfig).where(AdminConfig.id == 1).values(updated_at=func.now())
    )
    redir = RedirectResponse(url="/teacher", status_code=status.HTTP_303_SEE_OTHER)
    _set_teacher_cookie(redir)
    return redir


@router.get("", response_class=HTMLResponse)
async def page_dashboard(
    request: Request,
    db: DBSession,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).order_by(Chapter.order, Chapter.title))
    chapters = r.scalars().all()
    return templates.TemplateResponse(
        request,
        "teacher/dashboard.html",
        {"chapters": chapters},
    )


@router.post("/chapters/new", response_class=HTMLResponse)
async def ui_chapter_new(
    request: Request,
    db: DBSession,
    title: str = Form("未命名章"),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    slug = _slugify(title.strip() or "chapter")
    if not _SLUG_RE.match(slug):
        slug = f"ch-{uuid.uuid4().hex[:12]}"
    for _ in range(8):
        ex = (await db.execute(select(Chapter).where(Chapter.slug == slug))).scalar_one_or_none()
        if ex is None:
            break
        slug = f"{slug[:100]}-x{uuid.uuid4().hex[:6]}"
    ch = Chapter(
        slug=slug,
        title=title.strip() or "未命名章",
        order=0,
        content_status="draft",
        source_material=None,
        ai_generated_draft=None,
    )
    db.add(ch)
    await db.flush()
    return RedirectResponse(
        url=f"/teacher/chapters/{ch.id}/edit", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/roster", response_class=HTMLResponse)
async def page_roster(
    request: Request,
    db: DBSession,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(
        select(RosterEntry)
        .where(RosterEntry.deleted_at.is_(None))
        .order_by(RosterEntry.student_no)
    )
    rows = r.scalars().all()
    return templates.TemplateResponse(
        request,
        "teacher/roster.html",
        {"rows": rows},
    )


@router.post("/roster/import", response_class=HTMLResponse)
async def ui_roster_import(
    request: Request,
    db: DBSession,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
    file: UploadFile = File(...),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    if not file.filename:
        return templates.TemplateResponse(
            request,
            "teacher/partials/roster_result.html",
            {"ok": False, "message": "请选择文件"},
        )
    raw = await file.read()
    rows = _load_rows_from_file(raw, file.filename)
    n = 0
    for sn, fn in rows:
        if not sn or not fn:
            continue
        await _upsert_roster_row(db, sn, fn)
        n += 1
    return templates.TemplateResponse(
        request,
        "teacher/partials/roster_result.html",
        {
            "ok": True,
            "message": f"已处理 {n} 行。",
        },
    )


@router.get("/chapters/{chapter_id}/edit", response_class=HTMLResponse)
async def page_chapter_edit(
    request: Request,
    db: DBSession,
    chapter_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        return HTMLResponse("章不存在", status_code=404)
    draft_json = (
        json.dumps(ch.ai_generated_draft, ensure_ascii=False, indent=2)
        if ch.ai_generated_draft is not None
        else json.dumps(sample_published_v1(), ensure_ascii=False, indent=2)
    )
    return templates.TemplateResponse(
        request,
        "teacher/chapter_edit.html",
        {
            "ch": ch,
            "draft_json": draft_json,
        },
    )


@router.post("/chapters/{chapter_id}/save-draft", response_class=HTMLResponse)
async def ui_save_draft(
    request: Request,
    db: DBSession,
    chapter_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
    draft: str = Form(""),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        return HTMLResponse("章不存在", status_code=404)
    try:
        parsed = json.loads(draft)
    except json.JSONDecodeError as e:
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {"level": "error", "message": f"JSON 错误: {e!s}"},
        )
    if not isinstance(parsed, (dict, list)):
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {"level": "error", "message": "草稿须为 JSON 对象或数组。"},
        )
    ch.ai_generated_draft = parsed
    ch.content_status = "draft"
    ch.updated_at = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        request,
        "teacher/partials/flash.html",
        {"level": "ok", "message": "草稿已保存。"},
    )


@router.post("/chapters/{chapter_id}/generate", response_class=HTMLResponse)
async def ui_generate(
    request: Request,
    db: DBSession,
    chapter_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        return HTMLResponse("章不存在", status_code=404)
    parsed, raw, err = await generate_chapter_draft(ch.source_material, model=None)
    ch.generator_prompt_version = settings.generator_prompt_version
    ch.generator_model = settings.chapter_gen_model
    ch.updated_at = datetime.now(timezone.utc)
    if err and parsed is None:
        ch.ai_generated_raw = raw
        ch.ai_generated_draft = None
        ch.content_status = "draft_invalid"
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {"level": "error", "message": err or "生成失败"},
        )
    if parsed is not None:
        ch.ai_generated_draft = parsed
        ch.ai_generated_raw = raw
        ch.content_status = "draft"
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {"level": "ok", "message": "已生成草稿。请检查并发布。"},
        )
    ch.content_status = "draft_invalid"
    return templates.TemplateResponse(
        request,
        "teacher/partials/flash.html",
        {"level": "error", "message": err or "unknown"},
    )


@router.post("/chapters/{chapter_id}/publish", response_class=HTMLResponse)
async def ui_publish(
    request: Request,
    db: DBSession,
    chapter_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        return HTMLResponse("章不存在", status_code=404)
    d = ch.ai_generated_draft
    if d is None or not isinstance(d, dict):
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {"level": "error", "message": "无有效草稿。请先「保存 JSON」或「从素材生成」。"},
        )
    res = validate_for_publish(d)
    if not res.ok or res.content is None:
        return templates.TemplateResponse(
        request,
        "teacher/partials/flash.html",
        {
                "level": "error",
                "message": f"发布失败: {res.error} {'; '.join(res.warnings)}",
            },
        )
    ch.published_content = res.content
    ch.content_status = "published"
    ch.updated_at = datetime.now(timezone.utc)
    w = f" 警告: {'; '.join(res.warnings)}" if res.warnings else ""
    return templates.TemplateResponse(
        request,
        "teacher/partials/flash.html",
        {
            "level": "ok",
            "message": f"已发布。{w}",
        },
    )
