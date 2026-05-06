from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
import random

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette import status
from starlette.responses import Response

from ..config import merge_openai_compat_llm_headers, openai_compat_chat_completions_url
from ..db.models import PrestudyChapter, PrestudyResponse, Student
from ..deps import CurrentTeacher, DBSession
from ..services.llm_config import get_effective_llm_config
from ..services.teacher_markdown import teacher_markdown_to_safe_html


router = APIRouter(tags=["admin", "prestudy"])
templates = Jinja2Templates(directory="app/templates")


def _wants_htmx(request: Request) -> bool:
    return (request.headers.get("hx-request") or "").lower() == "true"


def _prestudy_edit_flash(request: Request) -> tuple[str | None, str | None]:
    qp = request.query_params
    if qp.get("error") == "1":
        return (
            "JSON 无法发布，请确认 version、items、id、title、learningGoal 字段完整。",
            "error",
        )
    if qp.get("draft_error") == "1":
        return "草稿保存失败：JSON 无法解析或字段不完整。", "error"
    if qp.get("pub_ok") == "1":
        return "发布成功。", "ok"
    if qp.get("saved") == "1":
        return "草稿已保存。", "ok"
    if qp.get("renamed") == "1":
        return "标题已更新。", "ok"
    if qp.get("rename_err") == "1":
        return "标题无效（须为 1～255 个非空字符）。", "error"
    if qp.get("unpub_ok") == "1":
        return "已取消发布，学生端暂时看不到本预习。", "ok"
    if qp.get("unpub_err") == "1":
        return "当前不是已发布状态。", "warn"
    return None, None


class PrestudyCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    order: int = Field(default=0, ge=0)


class PrestudyPublishBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[dict] = Field(min_length=1, max_length=100)


def _default_content() -> dict:
    return {
        "version": 1,
        "items": [
            {
                "id": "k1",
                "title": "核心知识点",
                "learningGoal": "能说明本知识点的基本概念与应用场景",
            }
        ],
    }


def _json_template_for_editor() -> dict:
    """教师端左侧只读模板（与 AI 课堂助教 JSON 区交互一致，可多条目示例）。"""
    return {
        "version": 1,
        "items": [
            {
                "id": "k1",
                "title": "示例：课程目标 / 本章导读",
                "learningGoal": "能说明本章要解决什么问题，以及前置知识有哪些",
            },
            {
                "id": "k2",
                "title": "示例：核心概念与术语",
                "learningGoal": "能正确复述关键定义，并各举一个应用场景",
            },
        ],
    }


def _validate_content(obj: object) -> dict:
    if isinstance(obj, list):
        obj = {"version": 1, "items": obj}
    if isinstance(obj, dict) and "items" in obj and "version" not in obj:
        obj = {"version": 1, **obj}
    if not isinstance(obj, dict) or obj.get("version") != 1:
        raise HTTPException(status_code=400, detail="prestudy_content_version_must_be_1")
    items = obj.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="prestudy_items_required")
    seen: set[str] = set()
    clean: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="prestudy_item_must_be_object")
        item_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        goal = str(raw.get("learningGoal") or raw.get("learning_goal") or "").strip()
        if not item_id or not title or not goal:
            raise HTTPException(status_code=400, detail="prestudy_item_fields_required")
        if item_id in seen:
            raise HTTPException(status_code=400, detail="prestudy_item_id_duplicate")
        seen.add(item_id)
        clean.append({"id": item_id, "title": title, "learningGoal": goal})
    return {"version": 1, "items": clean}


def _chapter_to_dict(ch: PrestudyChapter) -> dict:
    return {
        "prestudyId": str(ch.id),
        "title": ch.title,
        "order": ch.order,
        "status": ch.status,
        "content": ch.published_content,
        "updatedAt": ch.updated_at.isoformat() if ch.updated_at else None,
    }


async def _get_or_404(db: DBSession, prestudy_id: uuid.UUID) -> PrestudyChapter:
    row = (
        await db.execute(select(PrestudyChapter).where(PrestudyChapter.id == prestudy_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="prestudy_not_found")
    return row


@router.post("/v1/admin/prestudy", status_code=status.HTTP_201_CREATED)
async def create_prestudy(_t: CurrentTeacher, db: DBSession, body: PrestudyCreateBody) -> dict:
    ch = PrestudyChapter(title=body.title, order=body.order, status="draft")
    db.add(ch)
    await db.flush()
    return {"ok": True, **_chapter_to_dict(ch)}


@router.get("/v1/admin/prestudy")
async def list_admin_prestudy(_t: CurrentTeacher, db: DBSession) -> dict:
    rows = (
        await db.execute(select(PrestudyChapter).order_by(PrestudyChapter.order, PrestudyChapter.title))
    ).scalars().all()
    return {"ok": True, "prestudies": [_chapter_to_dict(x) for x in rows]}


@router.post("/v1/admin/prestudy/{prestudy_id}/publish")
async def publish_prestudy(
    _t: CurrentTeacher,
    db: DBSession,
    prestudy_id: uuid.UUID,
    body: PrestudyPublishBody,
) -> dict:
    ch = await _get_or_404(db, prestudy_id)
    content = _validate_content({"version": 1, "items": body.items})
    ch.published_content = content
    ch.status = "published"
    ch.updated_at = datetime.now(timezone.utc)
    return {"ok": True, "prestudy": _chapter_to_dict(ch)}


@router.get("/teacher/prestudy", response_class=HTMLResponse)
async def page_prestudy(request: Request, _t: CurrentTeacher, db: DBSession):
    rows = (
        await db.execute(select(PrestudyChapter).order_by(PrestudyChapter.order, PrestudyChapter.title))
    ).scalars().all()
    return templates.TemplateResponse(
        request,
        "teacher/prestudy_dashboard.html",
        {"prestudies": rows, "flash": request.query_params.get("flash")},
    )


@router.post("/teacher/prestudy/new")
async def post_prestudy_new(_t: CurrentTeacher, db: DBSession, title: str = Form("新预习")):
    ch = PrestudyChapter(title=title.strip() or "新预习", status="draft")
    db.add(ch)
    await db.flush()
    return RedirectResponse(
        url=f"/teacher/prestudy/{ch.id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/teacher/prestudy/{prestudy_id}/edit", response_class=HTMLResponse)
async def page_prestudy_edit(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    prestudy_id: uuid.UUID,
):
    ch = await _get_or_404(db, prestudy_id)
    content = ch.published_content or _default_content()
    ui_flash, ui_flash_level = _prestudy_edit_flash(request)
    return templates.TemplateResponse(
        request,
        "teacher/prestudy_edit.html",
        {
            "prestudy": ch,
            "template_json": json.dumps(_json_template_for_editor(), ensure_ascii=False, indent=2),
            "content_json": json.dumps(content, ensure_ascii=False, indent=2),
            "ui_flash": ui_flash,
            "ui_flash_level": ui_flash_level,
        },
    )


@router.post("/teacher/prestudy/{prestudy_id}/rename")
async def post_prestudy_rename(
    _t: CurrentTeacher,
    db: DBSession,
    prestudy_id: uuid.UUID,
    title: str = Form(""),
):
    ch = await _get_or_404(db, prestudy_id)
    t = (title or "").strip()
    if not t or len(t) > 255:
        return RedirectResponse(
            url=f"/teacher/prestudy/{prestudy_id}/edit?rename_err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.title = t
    ch.updated_at = datetime.now(timezone.utc)
    return RedirectResponse(
        url=f"/teacher/prestudy/{prestudy_id}/edit?renamed=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/teacher/prestudy/{prestudy_id}/save-draft")
async def post_prestudy_save_draft(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    prestudy_id: uuid.UUID,
    draft: str = Form(""),
):
    ch = await _get_or_404(db, prestudy_id)
    htmx = _wants_htmx(request)
    try:
        parsed = json.loads(draft)
        content = _validate_content(parsed)
    except (json.JSONDecodeError, HTTPException):
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {
                    "level": "error",
                    "message": "草稿保存失败：JSON 无法解析或字段不完整。",
                },
            )
        return RedirectResponse(
            url=f"/teacher/prestudy/{prestudy_id}/edit?draft_error=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.published_content = content
    ch.status = "draft"
    ch.updated_at = datetime.now(timezone.utc)
    loc = f"/teacher/prestudy/{prestudy_id}/edit?saved=1"
    if htmx:
        return Response(status_code=200, content=b"", headers={"HX-Redirect": loc})
    return RedirectResponse(url=loc, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/teacher/prestudy/{prestudy_id}/publish")
async def post_prestudy_publish(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    prestudy_id: uuid.UUID,
    draft: str = Form(""),
):
    ch = await _get_or_404(db, prestudy_id)
    htmx = _wants_htmx(request)
    try:
        parsed = json.loads(draft)
        content = _validate_content(parsed)
    except (json.JSONDecodeError, HTTPException):
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {
                    "level": "error",
                    "message": "发布失败：JSON 无法解析或字段不完整。",
                },
            )
        return RedirectResponse(
            url=f"/teacher/prestudy/{prestudy_id}/edit?error=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.published_content = content
    ch.status = "published"
    ch.updated_at = datetime.now(timezone.utc)
    loc = f"/teacher/prestudy/{prestudy_id}/edit?pub_ok=1"
    if htmx:
        return Response(status_code=200, content=b"", headers={"HX-Redirect": loc})
    return RedirectResponse(url=loc, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/teacher/prestudy/{prestudy_id}/unpublish")
async def post_prestudy_unpublish(
    request: Request, _t: CurrentTeacher, db: DBSession, prestudy_id: uuid.UUID
):
    ch = await _get_or_404(db, prestudy_id)
    htmx = _wants_htmx(request)
    if ch.status != "published":
        if htmx:
            return templates.TemplateResponse(
                request,
                "teacher/partials/flash.html",
                {"level": "warn", "message": "当前不是已发布状态。"},
            )
        return RedirectResponse(
            url=f"/teacher/prestudy/{prestudy_id}/edit?unpub_err=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    ch.status = "draft"
    ch.updated_at = datetime.now(timezone.utc)
    loc = f"/teacher/prestudy/{prestudy_id}/edit?unpub_ok=1"
    if htmx:
        return Response(status_code=200, content=b"", headers={"HX-Redirect": loc})
    return RedirectResponse(url=loc, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/teacher/prestudy/{prestudy_id}/delete")
async def post_prestudy_delete(_t: CurrentTeacher, db: DBSession, prestudy_id: uuid.UUID):
    ch = await _get_or_404(db, prestudy_id)
    await db.delete(ch)
    return RedirectResponse(url="/teacher/prestudy?flash=deleted", status_code=303)


def _cap_anonymous_feedback_rows(
    rows: list[dict],
    prestudy_id: uuid.UUID,
) -> list[dict]:
    """Show at most 5 anonymous lines; when several exist pick 2-5 deterministically per chapter."""
    if not rows:
        return []
    seed = int(str(prestudy_id).replace("-", ""), 16) % (2**31)
    if len(rows) <= 5:
        return rows
    cap = min(len(rows), max(2, 2 + (seed % 4)))
    order = list(range(len(rows)))
    rng = random.Random(seed)
    rng.shuffle(order)
    picked = [rows[i] for i in order[:cap]]
    picked.sort(key=lambda r: r["response"].submitted_at, reverse=True)
    return picked


def _feedback_view_data(
    ch: PrestudyChapter,
    responses: list[tuple[PrestudyResponse, Student]],
) -> dict:
    items = ch.published_content.get("items", []) if isinstance(ch.published_content, dict) else []
    item_ids = {str(item.get("id")) for item in items if isinstance(item, dict) and item.get("id")}
    aggregate_dist = {score: 0 for score in range(1, 8)}
    all_scores: list[int] = []
    item_score_map: dict[str, list[int]] = {item_id: [] for item_id in item_ids}
    for resp, _st in responses:
        for rating in resp.ratings:
            item_id = str(rating.get("itemId") or "")
            if item_ids and item_id not in item_ids:
                continue
            raw = rating.get("score")
            if raw is None:
                raw = rating.get("rating")
            try:
                score = int(raw)
            except (TypeError, ValueError):
                score = 0
            if 1 <= score <= 7:
                aggregate_dist[score] += 1
                all_scores.append(score)
                if item_id in item_score_map:
                    item_score_map[item_id].append(score)
    total_ratings = len(all_scores)
    average_score = round(sum(all_scores) / total_ratings, 2) if total_ratings else None
    colors = {
        1: "#16a34a",
        2: "#22c55e",
        3: "#84cc16",
        4: "#eab308",
        5: "#f97316",
        6: "#ef4444",
        7: "#991b1b",
    }
    chart_segments = []
    cursor = 0.0
    for score in range(1, 8):
        count = aggregate_dist[score]
        percent = round(count * 100 / total_ratings, 1) if total_ratings else 0.0
        end = cursor + percent
        chart_segments.append(
            {
                "score": score,
                "count": count,
                "percent": percent,
                "color": colors[score],
                "start": cursor,
                "end": end,
            }
        )
        cursor = end
    pie_gradient = (
        ", ".join(f"{seg['color']} {seg['start']}% {seg['end']}%" for seg in chart_segments if seg["count"])
        if total_ratings
        else "#e2e8f0 0 100%"
    )
    if average_score is None:
        difficulty_label = "暂无评分"
    elif average_score <= 2.5:
        difficulty_label = "整体偏容易"
    elif average_score <= 4.5:
        difficulty_label = "整体中等"
    else:
        difficulty_label = "整体偏难"
    item_averages = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        scores = item_score_map.get(item_id, [])
        avg = round(sum(scores) / len(scores), 2) if scores else None
        item_averages.append(
            {
                "index": idx,
                "id": item_id,
                "title": str(item.get("title") or f"知识点 {idx}"),
                "learning_goal": str(item.get("learningGoal") or item.get("learning_goal") or ""),
                "average": avg,
                "count": len(scores),
                "bar_width": round((avg or 0) * 100 / 7, 1),
            }
        )
    feedback_rows = [
        {"student": st, "response": resp}
        for resp, st in responses
        if (resp.feedback_text or "").strip()
    ]
    feedback_rows = _cap_anonymous_feedback_rows(feedback_rows, ch.id)
    return {
        "rating_summary": {
            "total": total_ratings,
            "average": average_score,
            "difficulty_label": difficulty_label,
            "knowledge_count": len(items),
            "pie_gradient": pie_gradient,
            "segments": chart_segments,
            "item_averages": item_averages,
        },
        "feedback_rows": feedback_rows,
        "response_count": len(responses),
    }


def _cap_llm_text(text: str, limit: int = 12000) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip()


async def _generate_prestudy_teaching_advice(
    db: DBSession,
    *,
    prestudy: PrestudyChapter,
    view_data: dict,
) -> str:
    cfg = await get_effective_llm_config(db)
    if not cfg.base_url:
        raise HTTPException(status_code=502, detail="llm_not_configured")
    summary = view_data["rating_summary"]
    feedback_rows = view_data["feedback_rows"]
    item_lines = [
        (
            f"{item['index']}. {item['title']}：平均难度 "
            f"{item['average'] if item['average'] is not None else '暂无'} / 7，"
            f"评分数 {item['count']}，目标：{item['learning_goal'] or '未填写'}"
        )
        for item in summary["item_averages"]
    ]
    feedback_lines = [
        str(row["response"].feedback_text).strip()
        for row in feedback_rows[:30]
        if str(row["response"].feedback_text or "").strip()
    ]
    prompt = (
        "请根据学生预习反馈统计，为教师生成下一次课的教学建议。"
        "要求：中文，篇幅适中（约 400～600 字为宜，勿冗长罗列）；"
        "可用 Markdown 组织内容（## 小标题、**加粗**、列表、行内 `代码`），不要输出 HTML、不要输出整块代码围栏；"
        "聚焦教学调整、重点讲解、课堂活动和答疑安排；避免编造统计中没有的信息。\n\n"
        f"预习主题：{prestudy.title}\n"
        f"提交人数：{view_data['response_count']}\n"
        f"总评分数：{summary['total']}\n"
        f"整体平均难度：{summary['average'] if summary['average'] is not None else '暂无'} / 7\n"
        f"整体判断：{summary['difficulty_label']}\n\n"
        "各知识点：\n" + "\n".join(item_lines) + "\n\n"
        "匿名文字反馈：\n" + ("\n".join(feedback_lines) if feedback_lines else "暂无文字反馈")
    )
    url = openai_compat_chat_completions_url(cfg.base_url)
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    headers = merge_openai_compat_llm_headers(cfg.base_url, headers)
    body = {
        "model": cfg.chat_model,
        "messages": [
            {
                "role": "system",
                "content": "你是教师教学诊断助手，只输出教学建议正文；使用 Markdown 排版，勿使用 HTML。",
            },
            {"role": "user", "content": prompt},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"upstream_unavailable: {e!s}"[:500]) from e
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=resp.text[:1000] or f"http {resp.status_code}")
    try:
        advice = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise HTTPException(status_code=502, detail=f"bad upstream shape: {e!s}") from e
    return _cap_llm_text(str(advice))


@router.get("/teacher/prestudy/{prestudy_id}/feedback", response_class=HTMLResponse)
async def page_prestudy_feedback(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    prestudy_id: uuid.UUID,
):
    ch = await _get_or_404(db, prestudy_id)
    if ch.published_content is None:
        raise HTTPException(status_code=404, detail="prestudy_not_published")
    responses = (
        await db.execute(
            select(PrestudyResponse, Student)
            .join(Student, Student.id == PrestudyResponse.student_id)
            .where(PrestudyResponse.prestudy_id == prestudy_id)
            .order_by(PrestudyResponse.submitted_at.desc())
        )
    ).all()
    view_data = _feedback_view_data(ch, responses)
    teaching_advice_html = None
    if (ch.teaching_advice_text or "").strip():
        teaching_advice_html = teacher_markdown_to_safe_html(ch.teaching_advice_text)
    return templates.TemplateResponse(
        request,
        "teacher/prestudy_feedback.html",
        {
            "prestudy": ch,
            "teaching_advice_html": teaching_advice_html,
            **view_data,
        },
    )


@router.post("/teacher/prestudy/{prestudy_id}/feedback/advice", response_class=HTMLResponse)
async def post_prestudy_feedback_advice(
    request: Request,
    _t: CurrentTeacher,
    db: DBSession,
    prestudy_id: uuid.UUID,
):
    ch = await _get_or_404(db, prestudy_id)
    if ch.published_content is None:
        raise HTTPException(status_code=404, detail="prestudy_not_published")
    responses = (
        await db.execute(
            select(PrestudyResponse, Student)
            .join(Student, Student.id == PrestudyResponse.student_id)
            .where(PrestudyResponse.prestudy_id == prestudy_id)
            .order_by(PrestudyResponse.submitted_at.desc())
        )
    ).all()
    view_data = _feedback_view_data(ch, responses)
    advice_raw = await _generate_prestudy_teaching_advice(db, prestudy=ch, view_data=view_data)
    ch.teaching_advice_text = advice_raw
    advice_html = teacher_markdown_to_safe_html(advice_raw)
    return templates.TemplateResponse(
        request,
        "teacher/partials/prestudy_teaching_advice.html",
        {"teaching_advice_html": advice_html},
    )
