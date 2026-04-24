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


@router.post("/chapters/{chapter_id}/delete", response_class=HTMLResponse)
async def ui_chapter_delete(
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
    await db.delete(ch)
    return RedirectResponse(url="/teacher", status_code=status.HTTP_303_SEE_OTHER)


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


def _wants_htmx(request: Request) -> bool:
    return (request.headers.get("hx-request") or "").lower() == "true"


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
    published_json: str | None = None
    if ch.published_content is not None:
        published_json = json.dumps(
            ch.published_content, ensure_ascii=False, indent=2
        )
    qp = request.query_params
    ui_flash: str | None = None
    ui_flash_level: str | None = None
    if qp.get("saved") == "1":
        ui_flash, ui_flash_level = "草稿已保存。", "ok"
    elif qp.get("draft_error") == "1":
        ui_flash, ui_flash_level = "草稿未保存：JSON 格式无法解析。请检查大括号/引号后重试。", "error"
    elif qp.get("gen_ok") == "1":
        ui_flash, ui_flash_level = "已生成草稿。请检查并发布。", "ok"
    elif qp.get("gen_err") == "1":
        ui_flash, ui_flash_level = "生成未成功。请检查素材与 LLM 配置。", "error"
    elif qp.get("pub_ok") == "1":
        ui_flash, ui_flash_level = "已发布。", "ok"
    elif qp.get("pub_err") == "1":
        ui_flash, ui_flash_level = "发布未成功。请检查草稿或「发布」校验信息。", "error"
    elif qp.get("material_saved") == "1":
        ui_flash, ui_flash_level = "章素材已保存。", "ok"
    return templates.TemplateResponse(
        request,
        "teacher/chapter_edit.html",
        {
            "ch": ch,
            "draft_json": draft_json,
            "source_material_text": ch.source_material or "",
            "published_json": published_json,
            "ui_flash": ui_flash,
            "ui_flash_level": ui_flash_level,
        },
    )


@router.post("/chapters/{chapter_id}/save-material", response_class=HTMLResponse)
async def ui_save_source_material(
    request: Request,
    db: DBSession,
    chapter_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
    source_material: str = Form(""),
):
    """教师 Web：保存 `sourceMaterial`（给「从素材用 LLM 生成」用）。"""
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        return HTMLResponse("章不存在", status_code=404)
    ch.source_material = source_material if source_material.strip() else None
    ch.updated_at = datetime.now(timezone.utc)
    htmx = _wants_htmx(request)
    if htmx:
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {"level": "ok", "message": "章素材已保存。可点「从素材用 LLM 生成」。"},
        )
    return RedirectResponse(
        url=f"/teacher/chapters/{chapter_id}/edit?material_saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
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
    htmx = _wants_htmx(request)
    try:
        parsed = json.loads(draft)
    except json.JSONDecodeError as e:
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "error", "message": f"JSON 错误: {e!s}"},
            )
        return RedirectResponse(
            url=f"/teacher/chapters/{chapter_id}/edit?draft_error=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if not isinstance(parsed, (dict, list)):
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "error", "message": "草稿须为 JSON 对象或数组。"},
            )
        return RedirectResponse(
            url=f"/teacher/chapters/{chapter_id}/edit?draft_error=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.ai_generated_draft = parsed
    ch.content_status = "draft"
    ch.updated_at = datetime.now(timezone.utc)
    if htmx:
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {"level": "ok", "message": "草稿已保存。"},
        )
    return RedirectResponse(
        url=f"/teacher/chapters/{chapter_id}/edit?saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
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
    htmx = _wants_htmx(request)
    parsed, raw, err = await generate_chapter_draft(ch.source_material, model=None)
    ch.generator_prompt_version = settings.generator_prompt_version
    ch.generator_model = settings.chapter_gen_model
    ch.updated_at = datetime.now(timezone.utc)
    if err and parsed is None:
        ch.ai_generated_raw = raw
        ch.ai_generated_draft = None
        ch.content_status = "draft_invalid"
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "error", "message": err or "生成失败"},
            )
        return RedirectResponse(
            url=f"/teacher/chapters/{chapter_id}/edit?gen_err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if parsed is not None:
        ch.ai_generated_draft = parsed
        ch.ai_generated_raw = raw
        ch.content_status = "draft"
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "ok", "message": "已生成草稿。请检查并发布。"},
            )
        return RedirectResponse(
            url=f"/teacher/chapters/{chapter_id}/edit?gen_ok=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.content_status = "draft_invalid"
    if htmx:
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {"level": "error", "message": err or "unknown"},
        )
    return RedirectResponse(
        url=f"/teacher/chapters/{chapter_id}/edit?gen_err=1",
        status_code=status.HTTP_303_SEE_OTHER,
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
    htmx = _wants_htmx(request)
    d = ch.ai_generated_draft
    if d is None or not isinstance(d, dict):
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "error", "message": "无有效草稿。请先「保存 JSON」或「从素材生成」。"},
            )
        return RedirectResponse(
            url=f"/teacher/chapters/{chapter_id}/edit?pub_err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    res = validate_for_publish(d)
    if not res.ok or res.content is None:
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {
                    "level": "error",
                    "message": f"发布失败: {res.error} {'; '.join(res.warnings)}",
                },
            )
        return RedirectResponse(
            url=f"/teacher/chapters/{chapter_id}/edit?pub_err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.published_content = res.content
    ch.content_status = "published"
    ch.updated_at = datetime.now(timezone.utc)
    w = f" 警告: {'; '.join(res.warnings)}" if res.warnings else ""
    if htmx:
        return templates.TemplateResponse(
            request,
            "teacher/partials/flash.html",
            {
                "level": "ok",
                "message": f"已发布。{w}",
            },
        )
    return RedirectResponse(
        url=f"/teacher/chapters/{chapter_id}/edit?pub_ok=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
