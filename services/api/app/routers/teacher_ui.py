"""
教师 **Web**（Jinja2 + **HTMX**；任务 10）。路径前缀 **`/teacher`**；需 Cookie `teacher_session`。
"""

from __future__ import annotations

import copy
import csv
import io
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, urlencode, urlparse

from fastapi import APIRouter, Cookie, File, Form, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload

from ..config import settings
from ..db.models import (
    AdminConfig,
    Chapter,
    ChapterCompletion,
    Class as ClassModel,
    RosterEntry,
    Student,
)
from ..deps import DBSession, require_bootstrap_token, teacher_cookie_valid
from ..services.chapter_json import validate_for_publish, sample_published_v1

from .admin import (  # noqa: PLC2701
    _get_or_create_class_id,
    _load_rows_from_file,
    _set_teacher_cookie,
    _soft_delete_unassigned_roster,
    _upsert_roster_row,
)
from .admin import _pwd
from .chapter_admin import _SLUG_RE, _slugify

router = APIRouter(prefix="/teacher", tags=["teacher-ui"])
templates = Jinja2Templates(directory="app/templates")


def _redirect_login() -> RedirectResponse:
    return RedirectResponse(url="/teacher/login", status_code=status.HTTP_302_FOUND)


def _chapter_rename_redirect_url(
    request: Request, chapter_id: uuid.UUID, *, success: bool
) -> str:
    """列表页重命名后回 `/teacher?…`；自编辑页提交则回编辑页（Referer 为 `/teacher` 视为列表）。"""
    ref = request.headers.get("referer")
    from_dashboard = False
    if ref:
        try:
            path = urlparse(ref).path.rstrip("/") or "/"
            from_dashboard = path == "/teacher"
        except ValueError:
            pass
    q = "renamed=1" if success else "rename_err=1"
    if from_dashboard:
        return f"/teacher?{q}"
    return f"/teacher/chapters/{chapter_id}/edit?{q}"


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
    r_cls = await db.execute(select(func.count()).select_from(ClassModel))
    class_count = r_cls.scalar_one() or 0
    qp = request.query_params
    ui_flash: str | None = None
    ui_flash_level: str | None = None
    if qp.get("renamed") == "1":
        ui_flash, ui_flash_level = "章标题已更新。", "ok"
    elif qp.get("rename_err") == "1":
        ui_flash, ui_flash_level = (
            "标题未更新：须为非空且不超过 255 个字符。",
            "error",
        )
    return templates.TemplateResponse(
        request,
        "teacher/dashboard.html",
        {
            "chapters": chapters,
            "class_count": class_count,
            "ui_flash": ui_flash,
            "ui_flash_level": ui_flash_level,
        },
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


@router.get("/classes", response_class=HTMLResponse)
async def page_classes(
    request: Request,
    db: DBSession,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(
        select(ClassModel).order_by(ClassModel.name)
    )
    classes = r.scalars().all()
    return templates.TemplateResponse(
        request,
        "teacher/classes.html",
        {"classes": classes},
    )


@router.get("/classes/{class_id}", response_class=HTMLResponse)
async def page_class_detail(
    request: Request,
    db: DBSession,
    class_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(ClassModel).where(ClassModel.id == class_id))
    cl = r.scalar_one_or_none()
    if cl is None:
        return HTMLResponse("班级不存在", status_code=404)
    r_flash: str | None = None
    r_level: str | None = None
    if request.query_params.get("saved") == "1":
        r_level, r_flash = "ok", "已更新班级。"
    r_roster = await db.execute(
        select(RosterEntry)
        .options(selectinload(RosterEntry.class_))
        .where(
            RosterEntry.deleted_at.is_(None),
            RosterEntry.class_id == class_id,
        )
        .order_by(RosterEntry.student_no)
    )
    roster_rows = r_roster.scalars().all()
    r_stu = await db.execute(
        select(Student, ClassModel)
        .outerjoin(ClassModel, Student.class_id == ClassModel.id)
        .where(Student.class_id == class_id)
        .order_by(Student.student_no)
    )
    reg_students = r_stu.all()
    r_cls = await db.execute(
        select(ClassModel).order_by(ClassModel.name)
    )
    all_classes = r_cls.scalars().all()
    return templates.TemplateResponse(
        request,
        "teacher/class_detail.html",
        {
            "cl": cl,
            "roster_rows": roster_rows,
            "reg_students": reg_students,
            "all_classes": all_classes,
            "roster_flash": r_flash,
            "roster_flash_level": r_level,
        },
    )


@router.get("/classes/{class_id}/completions-export")
async def export_class_chapter_completions_csv(
    db: DBSession,
    class_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    """本班学生 × 全章：有完成记录时一行；便于批量查看练习提交情况。UTF-8 BOM。"""
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(ClassModel).where(ClassModel.id == class_id))
    cl = r.scalar_one_or_none()
    if cl is None:
        return HTMLResponse("班级不存在", status_code=404)
    r2 = await db.execute(
        select(Chapter, ChapterCompletion, Student)
        .join(ChapterCompletion, ChapterCompletion.chapter_id == Chapter.id)
        .join(Student, Student.id == ChapterCompletion.student_id)
        .where(Chapter.content_status == "published", Student.class_id == class_id)
        .order_by(Chapter.order, Chapter.title, Student.student_no)
    )
    rows = r2.all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["chapterTitle", "studentNo", "fullName", "completedAtUtc"],
    )
    for ch, cc, st in rows:
        w.writerow(
            [
                ch.title,
                st.student_no,
                st.full_name,
                cc.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )
    body = "\ufeff" + buf.getvalue()
    safe = quote((cl.name or "class")[:40], safe="")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="class-{safe}-completions.csv"',
        },
    )


@router.post("/classes/new", response_class=HTMLResponse)
async def ui_class_new(
    request: Request,
    db: DBSession,
    name: str = Form(""),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    label = (name or "").strip()
    if not label:
        return RedirectResponse(
            url="/teacher/classes?err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ex = (
        await db.execute(select(ClassModel).where(ClassModel.name == label))
    ).scalar_one_or_none()
    if ex is not None:
        return RedirectResponse(
            url="/teacher/classes?dup=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    db.add(ClassModel(name=label))
    return RedirectResponse(
        url="/teacher/classes?ok=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/students/{student_id}/set-class", response_class=HTMLResponse)
async def ui_set_student_class(
    db: DBSession,
    student_id: uuid.UUID,
    class_id: str = Form(""),
    return_to: str = Form("roster"),
    return_class_id: str = Form(""),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    st = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalar_one_or_none()
    if st is None:
        return HTMLResponse("学生不存在", status_code=404)
    if not (class_id or "").strip():
        st.class_id = None
    else:
        try:
            cid = uuid.UUID(class_id.strip())
        except ValueError:
            return RedirectResponse(url="/teacher/roster?err=class", status_code=303)
        c = (await db.execute(select(ClassModel).where(ClassModel.id == cid))).scalar_one_or_none()
        if c is None:
            return RedirectResponse(url="/teacher/roster?err=class", status_code=303)
        st.class_id = c.id
    re_row = (
        await db.execute(select(RosterEntry).where(RosterEntry.student_no == st.student_no))
    ).scalar_one_or_none()
    if re_row is not None and re_row.deleted_at is None:
        re_row.class_id = st.class_id
    if (return_to or "").strip() == "class":
        target: uuid.UUID | None = st.class_id
        raw = (return_class_id or "").strip()
        if raw:
            try:
                target = uuid.UUID(raw)
            except ValueError:
                pass
        if target is not None:
            return RedirectResponse(
                url=f"/teacher/classes/{target}?saved=1",
                status_code=status.HTTP_303_SEE_OTHER,
            )
    rraw = (return_class_id or "").strip()
    loc = "/teacher/roster?saved=1"
    if rraw:
        loc = f"/teacher/roster?saved=1&classId={quote(rraw)}"
    return RedirectResponse(
        url=loc,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/students/bulk-set-class", response_class=HTMLResponse)
async def ui_bulk_set_student_class(
    db: DBSession,
    class_id: str = Form(""),
    student_ids: list[str] | None = Form(None),
    return_class_id: str = Form(""),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    """多选学生批量设班，同步同学号 `roster_entries.class_id`。"""
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    ids: list[uuid.UUID] = []
    for s in (student_ids or []):
        s = (s or "").strip()
        if not s:
            continue
        try:
            ids.append(uuid.UUID(s))
        except ValueError:
            continue
    if not ids:
        err_q = "err=bulk_none"
        rraw = (return_class_id or "").strip()
        if rraw:
            err_q += f"&classId={quote(rraw)}"
        return RedirectResponse(
            url=f"/teacher/roster?{err_q}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    target_cid: uuid.UUID | None
    if not (class_id or "").strip():
        target_cid = None
    else:
        try:
            target_cid = uuid.UUID((class_id or "").strip())
        except ValueError:
            return RedirectResponse(url="/teacher/roster?err=class", status_code=303)
        c = (await db.execute(select(ClassModel).where(ClassModel.id == target_cid))).scalar_one_or_none()
        if c is None:
            return RedirectResponse(url="/teacher/roster?err=class", status_code=303)
    for sid in ids:
        st = (
            await db.execute(select(Student).where(Student.id == sid))
        ).scalar_one_or_none()
        if st is None:
            continue
        st.class_id = target_cid
        re_row = (
            await db.execute(select(RosterEntry).where(RosterEntry.student_no == st.student_no))
        ).scalar_one_or_none()
        if re_row is not None and re_row.deleted_at is None:
            re_row.class_id = target_cid
    rraw = (return_class_id or "").strip()
    loc = "/teacher/roster?saved=1"
    if rraw:
        loc = f"/teacher/roster?saved=1&classId={quote(rraw)}"
    return RedirectResponse(
        url=loc,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/students/bulk-unregister", response_class=HTMLResponse)
async def ui_bulk_unregister_students(
    db: DBSession,
    student_ids: list[str] | None = Form(None),
    return_class_id: str = Form(""),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    """
    删除所选 `Student` 行；`RosterEntry.student_id` 由外键 `SET NULL`，
    并将同学号条目标回 `status=pending` 以便再次注册。子表
    `cell_verifications` / `chapter_completions` 在删除学生时 `CASCADE`。
    """
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    ids: list[uuid.UUID] = []
    for s in student_ids or []:
        s = (s or "").strip()
        if not s:
            continue
        try:
            ids.append(uuid.UUID(s))
        except ValueError:
            continue
    rraw = (return_class_id or "").strip()
    loc_base = "/teacher/roster"
    if rraw:
        loc_base = f"/teacher/roster?classId={quote(rraw)}"
    if not ids:
        sep = "&" if "?" in loc_base else "?"
        return RedirectResponse(
            url=f"{loc_base}{sep}err=unreg_none",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    r = await db.execute(select(Student).where(Student.id.in_(ids)))
    students = r.scalars().all()
    if not students:
        sep = "&" if "?" in loc_base else "?"
        return RedirectResponse(
            url=f"{loc_base}{sep}err=unreg_none",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    student_nos = [st.student_no for st in students]
    to_delete_ids = [st.id for st in students]
    await db.execute(delete(Student).where(Student.id.in_(to_delete_ids)))
    await db.execute(
        update(RosterEntry)
        .where(RosterEntry.student_no.in_(student_nos))
        .values(status="pending", student_id=None)
    )
    n_ok = len(to_delete_ids)
    sep = "&" if "?" in loc_base else "?"
    return RedirectResponse(
        url=f"{loc_base}{sep}unreg_ok={n_ok}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/students/{student_id}/remove-from-class", response_class=HTMLResponse)
async def ui_remove_student_from_class(
    db: DBSession,
    student_id: uuid.UUID,
    from_class_id: str = Form(""),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    """
    将学生从班级移出：清空 `students.class_id` 与同学号 `roster_entries.class_id`，
    学生回到「名单」的当前名单行（未分班）。
    """
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    st = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalar_one_or_none()
    if st is None:
        return HTMLResponse("学生不存在", status_code=404)
    st.class_id = None
    e_r = await db.execute(
        select(RosterEntry).where(RosterEntry.student_no == st.student_no)
    )
    re = e_r.scalar_one_or_none()
    if re is not None and re.deleted_at is None:
        re.class_id = None
    raw = (from_class_id or "").strip()
    try:
        u = uuid.UUID(raw) if raw else None
    except ValueError:
        u = None
    if u is not None:
        return RedirectResponse(
            url=f"/teacher/classes/{u}?saved=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url="/teacher/roster?saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/chapters/{chapter_id}/completions", response_class=HTMLResponse)
async def page_chapter_completions(
    request: Request,
    db: DBSession,
    chapter_id: uuid.UUID,
    class_id: uuid.UUID | None = Query(default=None, alias="classId"),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    """学生「标记本章完成」后的提交记录（按章；可选 `classId` 仅看该班学生）。"""
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        return HTMLResponse("章不存在", status_code=404)
    r_cls2 = await db.execute(
        select(ClassModel).order_by(ClassModel.name)
    )
    all_classes = r_cls2.scalars().all()
    current_class: ClassModel | None = None
    if class_id is not None:
        current_class = (
            await db.execute(select(ClassModel).where(ClassModel.id == class_id))
        ).scalar_one_or_none()
        if current_class is None:
            class_id = None
    q = (
        select(ChapterCompletion, Student)
        .join(Student, Student.id == ChapterCompletion.student_id)
        .where(ChapterCompletion.chapter_id == chapter_id)
    )
    if class_id is not None:
        q = q.where(Student.class_id == class_id)
    r2 = await db.execute(
        q.order_by(ChapterCompletion.completed_at.desc())
    )
    rows = r2.all()
    completions = [
        {
            "student_no": st.student_no,
            "full_name": st.full_name,
            "completed_at": cc.completed_at,
        }
        for cc, st in rows
    ]
    return templates.TemplateResponse(
        request,
        "teacher/chapter_completions.html",
        {
            "ch": ch,
            "completions": completions,
            "submit_count": len(completions),
            "all_classes": all_classes,
            "filter_class_id": str(class_id) if class_id else None,
            "filter_class": current_class,
        },
    )


@router.get("/chapters/{chapter_id}/completions/export")
async def export_chapter_completions_csv(
    db: DBSession,
    chapter_id: uuid.UUID,
    class_id: uuid.UUID | None = Query(default=None, alias="classId"),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    """导出本章「标记完成」学生学号、姓名（CSV，UTF-8 BOM 便于 Excel）；`classId` 时仅该班。"""
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        return HTMLResponse("章不存在", status_code=404)
    if class_id is not None:
        ccheck = (
            await db.execute(select(ClassModel).where(ClassModel.id == class_id))
        ).scalar_one_or_none()
        if ccheck is None:
            class_id = None
    q = (
        select(ChapterCompletion, Student)
        .join(Student, Student.id == ChapterCompletion.student_id)
        .where(ChapterCompletion.chapter_id == chapter_id)
    )
    if class_id is not None:
        q = q.where(Student.class_id == class_id)
    r2 = await db.execute(
        q.order_by(Student.student_no)
    )
    rows = r2.all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["studentNo", "fullName", "completedAtUtc"])
    for cc, st in rows:
        w.writerow(
            [
                st.student_no,
                st.full_name,
                cc.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )
    body = "\ufeff" + buf.getvalue()
    safe = quote(ch.slug[:40] or "chapter", safe="")
    extra = f"-{str(class_id)[:8]}" if class_id is not None else ""
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="completions-{safe}{extra}.csv"',
        },
    )


@router.get("/roster", response_class=HTMLResponse)
async def page_roster(
    request: Request,
    db: DBSession,
    class_id: str | None = Query(
        default=None,
        alias="classId",
        description="筛选：空=全部；`none` 或 `unassigned` 为未分班；否则为班级 UUID。",
    ),
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(
        select(RosterEntry)
        .options(selectinload(RosterEntry.class_))
        .where(
            RosterEntry.deleted_at.is_(None),
            RosterEntry.class_id.is_(None),
        )
        .order_by(RosterEntry.student_no)
    )
    rows = r.scalars().all()
    r_cls = await db.execute(
        select(ClassModel).order_by(ClassModel.name)
    )
    classes = r_cls.scalars().all()
    st_q = select(Student, ClassModel).outerjoin(
        ClassModel, Student.class_id == ClassModel.id
    )
    raw_filter = (class_id or "").strip()
    if raw_filter.lower() in ("none", "unassigned"):
        st_q = st_q.where(Student.class_id.is_(None))
    elif raw_filter:
        try:
            fcid = uuid.UUID(raw_filter)
        except ValueError:
            fcid = None
        if fcid is not None:
            st_q = st_q.where(Student.class_id == fcid)
    st_q = st_q.order_by(Student.student_no)
    r_stu = await db.execute(st_q)
    student_rows = r_stu.all()
    reg_students: list[dict] = [
        {
            "id": st.id,
            "student_no": st.student_no,
            "full_name": st.full_name,
            "class": cls_,
            "class_id": st.class_id,
        }
        for st, cls_ in student_rows
    ]
    r_flash: str | None = None
    r_level: str | None = None
    if request.query_params.get("saved") == "1":
        r_level, r_flash = "ok", "已更新班级。"
    elif request.query_params.get("err") == "class":
        r_level, r_flash = "err", "班级无效，请重试。"
    elif request.query_params.get("err") == "bulk_none":
        r_level, r_flash = "err", "请至少勾选一名学生后再批量设班。"
    elif request.query_params.get("err") == "unreg_none":
        r_level, r_flash = "err", "请至少勾选一名已注册学生后再批量取消注册。"
    elif request.query_params.get("unreg_ok"):
        try:
            un = int(request.query_params.get("unreg_ok") or "0")
        except ValueError:
            un = 0
        if un > 0:
            r_level, r_flash = "ok", f"已取消 {un} 名学生的注册，其可凭原名单行再次注册。"
    elif request.query_params.get("roster_del") == "1":
        n = request.query_params.get("n", "0")
        r_level, r_flash = "ok", f"已删除 {n} 条未分班名单行。"
    elif request.query_params.get("roster_del_err") == "empty":
        r_level, r_flash = "err", "请先勾选要删除的名单行。"
    return templates.TemplateResponse(
        request,
        "teacher/roster.html",
        {
            "rows": rows,
            "classes": classes,
            "reg_students": reg_students,
            "roster_flash": r_flash,
            "roster_flash_level": r_level,
            "roster_class_id_filter": raw_filter,
        },
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
    await _soft_delete_unassigned_roster(db)
    n = 0
    for sn, fn, class_label in rows:
        if not sn or not fn:
            continue
        cid = await _get_or_create_class_id(db, class_label)
        await _upsert_roster_row(db, sn, fn, cid)
        n += 1
    msg = f"已用新文件覆盖未分班名单，并处理 {n} 行有效记录。"
    resp = templates.TemplateResponse(
        request,
        "teacher/partials/roster_result.html",
        {
            "ok": True,
            "message": msg,
        },
    )
    if _wants_htmx(request):
        resp.headers["HX-Refresh"] = "true"
    return resp


@router.post("/roster/entries/delete", response_class=HTMLResponse)
async def ui_roster_delete_unassigned(
    request: Request,
    db: DBSession,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
):
    """软删除所选**未分班**的 `roster_entries` 行（`class_id` 须为空）。"""
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    form = await request.form()
    raw_ids = form.getlist("entry_id")
    if not raw_ids:
        return RedirectResponse(
            url="/teacher/roster?roster_del_err=empty",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    now = datetime.now(timezone.utc)
    n_ok = 0
    for raw in raw_ids:
        s = (raw or "").strip()
        if not s:
            continue
        try:
            eid = uuid.UUID(s)
        except ValueError:
            continue
        r = await db.execute(select(RosterEntry).where(RosterEntry.id == eid))
        entry = r.scalar_one_or_none()
        if entry is None or entry.deleted_at is not None:
            continue
        if entry.class_id is not None:
            continue
        entry.deleted_at = now
        n_ok += 1
    if n_ok == 0:
        return RedirectResponse(
            url="/teacher/roster?roster_del_err=empty",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"/teacher/roster?roster_del=1&n={n_ok}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _wants_htmx(request: Request) -> bool:
    return (request.headers.get("hx-request") or "").lower() == "true"


def _merge_raw_reference_answers(preview: dict | None, raw: dict | None) -> dict | None:
    """
    教师「发布预览」：当 `draft_preview` 缺失而回退到旧 `published_content` 时，
    已发布快照可能缺少或为空字符串的参考类字段，若当前草稿 `raw` 已填写，则按格并入以便教师核对。

    对 `guideCell` / `extensionCell` 同格按字段从草稿合并，字段包括：
    `referenceAnswer`；`codeBackdropCode`、`codeBackdropLabel`（当预览中缺省或空白而草稿有非空
    字符串时写入；基础题常用 `codeBackdrop*`，扩展题以 `referenceAnswer` 为主）。

    按 **块 `id`** 与草稿对应块配对；仅当块 id 缺失或找不到时再按**列表下标**回退，
    避免草稿调整块顺序后与已发布快照错行，导致扩展/基础参考合错格。预览中已有非空内容不覆盖。
    """
    if preview is None or not isinstance(preview, dict):
        return preview
    if not isinstance(raw, dict):
        return preview
    out = copy.deepcopy(preview)
    raw_blocks = raw.get("blocks")
    blks = out.get("blocks")
    if not isinstance(raw_blocks, list) or not isinstance(blks, list):
        return out
    raw_by_id: dict[str, dict] = {}
    for rb in raw_blocks:
        if not isinstance(rb, dict):
            continue
        rid = rb.get("id")
        if isinstance(rid, str) and rid.strip():
            raw_by_id[rid] = rb
    n_raw = len(raw_blocks)
    merge_fields = ("referenceAnswer", "codeBackdropCode", "codeBackdropLabel")
    for i, b in enumerate(blks):
        if not isinstance(b, dict):
            continue
        bid = b.get("id")
        rblk: dict | None = None
        if isinstance(bid, str) and bid.strip():
            rblk = raw_by_id.get(bid)
        if rblk is None and i < n_raw and isinstance(raw_blocks[i], dict):
            rblk = raw_blocks[i]
        if not isinstance(rblk, dict):
            continue
        for key in ("guideCell", "extensionCell"):
            pcell, rcell = b.get(key), rblk.get(key)
            if not isinstance(pcell, dict) or not isinstance(rcell, dict):
                continue
            for field in merge_fields:
                s = rcell.get(field)
                if not isinstance(s, str) or not s.strip():
                    continue
                cur = pcell.get(field)
                if cur is not None and isinstance(cur, str) and cur.strip():
                    continue
                pcell[field] = s
    return out


def _draft_template_file_text() -> str:
    """`teacher_ui` → `app` → `api` → `services` → repo root; then `docs/chapter-v1-notebook-template.json`."""
    root = Path(__file__).resolve().parent.parent.parent.parent.parent
    path = root / "docs" / "chapter-v1-notebook-template.json"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return json.dumps(sample_published_v1(), indent=2, ensure_ascii=False)


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
    qp = request.query_params
    ui_flash: str | None = None
    ui_flash_level: str | None = None
    if qp.get("saved") == "1":
        ui_flash, ui_flash_level = "草稿已保存。", "ok"
    elif qp.get("draft_error") == "1":
        ui_flash, ui_flash_level = "草稿未保存：JSON 格式无法解析。请检查大括号/引号后重试。", "error"
    elif qp.get("pub_ok") == "1":
        if qp.get("has_warn") == "1":
            ui_flash, ui_flash_level = "已发布。发布时存在校验警告，请检查草稿与预览。", "ok"
        else:
            ui_flash, ui_flash_level = "已发布。", "ok"
    elif qp.get("pub_same") == "1":
        ui_flash, ui_flash_level = "当前内容已发布，请勿重复发布", "warn"
    elif qp.get("pub_err") == "1":
        ui_flash, ui_flash_level = "发布未成功。请检查草稿或「发布」校验信息。", "error"
    elif qp.get("unpub_ok") == "1":
        ui_flash, ui_flash_level = "已取消发布，学生端将不再显示本章节练习。", "ok"
    elif qp.get("unpub_err") == "1":
        ui_flash, ui_flash_level = "未查到已发布的章节练习", "error"
    elif qp.get("material_saved") == "1":
        ui_flash, ui_flash_level = "章素材已保存。", "ok"
    elif qp.get("renamed") == "1":
        ui_flash, ui_flash_level = "章标题已更新。", "ok"
    elif qp.get("rename_err") == "1":
        ui_flash, ui_flash_level = "标题未更新：须为非空且不超过 255 个字符。", "error"

    draft_preview: dict | None = None
    draft_preview_warnings: list[str] = []
    if isinstance(ch.ai_generated_draft, dict):
        res = validate_for_publish(ch.ai_generated_draft)
        if res.ok and res.content is not None:
            draft_preview = res.content
            draft_preview_warnings = list(res.warnings)
    base_preview = draft_preview or ch.published_content
    preview_content = _merge_raw_reference_answers(
        base_preview,
        ch.ai_generated_draft if isinstance(ch.ai_generated_draft, dict) else None,
    )
    has_preview = bool(
        preview_content
        and preview_content.get("version") == 1
        and preview_content.get("blocks"),
    )
    invalid_draft_for_preview = isinstance(ch.ai_generated_draft, dict) and draft_preview is None
    return templates.TemplateResponse(
        request,
        "teacher/chapter_edit.html",
        {
            "ch": ch,
            "draft_json": draft_json,
            "draft_template_text": _draft_template_file_text(),
            "source_material_text": ch.source_material or "",
            "ui_flash": ui_flash,
            "ui_flash_level": ui_flash_level,
            "draft_preview": draft_preview,
            "draft_preview_warnings": draft_preview_warnings,
            "preview_content": preview_content,
            "has_preview": has_preview,
            "invalid_draft_for_preview": invalid_draft_for_preview,
        },
    )


@router.post("/chapters/{chapter_id}/rename", response_class=HTMLResponse)
async def ui_chapter_rename(
    request: Request,
    db: DBSession,
    chapter_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
    title: str = Form(""),
):
    """教师 Web：更新 `Chapter.title`（与 `ChapterUpdateBody.title` 一致：1–255 字符）。"""
    if not await teacher_cookie_valid(teacher_session, db):
        return _redirect_login()
    r = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    ch = r.scalar_one_or_none()
    if ch is None:
        return HTMLResponse("章不存在", status_code=404)
    t = (title or "").strip()
    if not t or len(t) > 255:
        return RedirectResponse(
            url=_chapter_rename_redirect_url(request, chapter_id, success=False),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.title = t
    ch.updated_at = datetime.now(timezone.utc)
    return RedirectResponse(
        url=_chapter_rename_redirect_url(request, chapter_id, success=True),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/chapters/{chapter_id}/save-material", response_class=HTMLResponse)
async def ui_save_source_material(
    request: Request,
    db: DBSession,
    chapter_id: uuid.UUID,
    teacher_session: str | None = Cookie(default=None, alias="teacher_session"),
    source_material: str = Form(""),
):
    """教师 Web：保存 `sourceMaterial`（章素材，可与 API 生章等流程配合）。"""
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
            {"level": "ok", "message": "章素材已保存。"},
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
    # Commit before the response is sent. Request-scoped `get_db` runs its commit only
    # after the response completes; HTMX then GETs the edit page and would otherwise
    # often read the previous `ai_generated_draft` and show a stale 发布预览.
    await db.commit()
    if htmx:
        return Response(
            status_code=200,
            content=b"",
            headers={
                "HX-Redirect": f"/teacher/chapters/{chapter_id}/edit?saved=1",
            },
        )
    return RedirectResponse(
        url=f"/teacher/chapters/{chapter_id}/edit?saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/chapters/{chapter_id}/publish", response_class=HTMLResponse)
async def ui_publish(
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
    raw = (draft or "").strip()
    d: object | None
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            if htmx:
                return templates.TemplateResponse(
                    request,
                    "teacher/partials/flash.html",
                    {
                        "level": "error",
                        "message": f"发布失败: JSON 无法解析（{e!s}）。",
                    },
                )
            return RedirectResponse(
                url=f"/teacher/chapters/{chapter_id}/edit?pub_err=1",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        if not isinstance(parsed, dict):
            if htmx:
                return templates.TemplateResponse(
                    request,
                    "teacher/partials/flash.html",
                    {
                        "level": "error",
                        "message": "发布失败: 章 JSON 根须为对象。",
                    },
                )
            return RedirectResponse(
                url=f"/teacher/chapters/{chapter_id}/edit?pub_err=1",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        d = parsed
        ch.ai_generated_draft = parsed
    else:
        d = ch.ai_generated_draft
    if d is None or not isinstance(d, dict):
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "error", "message": "无有效草稿。请先在编辑区填写章 JSON 或点「保存草稿」。"},
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
    if ch.content_status == "published" and ch.published_content == res.content:
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {
                    "level": "warn",
                    "message": "当前内容已发布，请勿重复发布",
                },
            )
        return RedirectResponse(
            url=f"/teacher/chapters/{chapter_id}/edit?pub_same=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.published_content = res.content
    ch.content_status = "published"
    ch.updated_at = datetime.now(timezone.utc)
    await db.commit()
    q: dict[str, str] = {"pub_ok": "1"}
    if res.warnings:
        q["has_warn"] = "1"
    loc = f"/teacher/chapters/{chapter_id}/edit?{urlencode(q)}"
    if htmx:
        return Response(
            status_code=200,
            content=b"",
            headers={"HX-Redirect": loc},
        )
    return RedirectResponse(
        url=loc,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/chapters/{chapter_id}/unpublish", response_class=HTMLResponse)
async def ui_unpublish(
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
    if ch.content_status != "published" or not ch.published_content:
        msg = "未查到已发布的章节练习"
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "error", "message": msg},
            )
        return RedirectResponse(
            url=f"/teacher/chapters/{chapter_id}/edit?unpub_err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.published_content = None
    ch.content_status = "draft"
    ch.updated_at = datetime.now(timezone.utc)
    await db.commit()
    if htmx:
        return Response(
            status_code=200,
            content=b"",
            headers={
                "HX-Redirect": f"/teacher/chapters/{chapter_id}/edit?unpub_ok=1",
            },
        )
    return RedirectResponse(
        url=f"/teacher/chapters/{chapter_id}/edit?unpub_ok=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
