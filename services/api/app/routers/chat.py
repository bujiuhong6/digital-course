"""
学生 **聊天代理**（设计 §7：无 RAG；§6/§7：上下文截断、OpenAI 兼容；任务 9）。

- **`POST /v1/student/chat`**：Body `chapterId`, `cellId`, `messages`；可选 `stream` 流式（SSE 文本行）。
- 题面+消息拼入用户提示，截断至 `chat_context_max_chars`。
- 限流见 `chat_limiter`（每生每分钟、可选每日 token 预算）。

环境变量在 **设置** 中对应 `CHAT_LLM_BASE_URL` / `CHAT_LLM_API_KEY` 等，见 `Settings` 字段 Pydantic 名。
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..config import (
    merge_openai_compat_llm_headers,
    normalize_openai_compat_base_url,
    openai_compat_chat_completions_url,
    settings,
)
from ..db.models import Chapter, Student
from ..deps import CurrentStudent, DBSession
from ..services.chat_limiter import check_and_record_request
from ..services.llm_config import get_effective_llm_config

router = APIRouter(prefix="/v1/student", tags=["student", "chat"])


class ChatMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: str = Field(min_length=1, max_length=32)  # user | assistant 等
    content: str = Field(max_length=200_000)


class ChatBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chapter_id: uuid.UUID = Field(alias="chapterId")
    cell_id: str = Field(min_length=1, max_length=128, alias="cellId")
    messages: list[ChatMessage] = Field(min_length=1, max_length=200)
    stream: bool = False
    # 学生当前代码（可空），截断在服务端
    current_code: str | None = Field(default=None, max_length=200_000, alias="currentCode")


def _truncate(s: str, cap: int) -> str:
    if len(s) <= cap:
        return s
    return s[: cap - 1] + "…"


def _build_user_prompt(
    ch: dict | None,
    cell_id: str,
    user_msgs: str,
    code: str | None,
) -> str:
    cap = max(1000, settings.chat_context_max_chars)
    # 轻量题面：只取已发布 `publishedContent` 的短摘要式字符串（不整章外泄过长 HTML）
    ctx_tail = ""
    if ch is not None:
        try:
            raw = json.dumps(ch, default=str, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raw = f'{{"error":"chapter_context_not_json_serializable","detail":"{e!s}"}}'
        ctx_tail = _truncate(raw, min(cap, cap // 2))
    cpart = (code or "").strip()
    cpart = _truncate(cpart, min(cap, cap // 2)) if cpart else ""
    u = _truncate(user_msgs, min(cap, cap - len(ctx_tail) - len(cpart) - 200))
    return (
        f"Chapter context (JSON excerpt, may be trimmed):\n{ctx_tail}\n\n"
        f"Cell id: {cell_id}\n"
        f"User code (may be empty):\n```\n{cpart}\n```\n\n"
        f"User messages (latest conversation):\n{u}"
    )


async def _student_chat_impl(
    me: Student,
    payload: ChatBody,
    db: DBSession,
) -> JSONResponse | StreamingResponse | dict:
    r = await db.execute(
        select(Chapter).where(Chapter.id == payload.chapter_id, Chapter.content_status == "published")
    )
    ch = r.scalar_one_or_none()
    if ch is None or ch.published_content is None:
        raise HTTPException(status_code=404, detail="chapter not found or not published")
    if not isinstance(ch.published_content, dict):
        raise HTTPException(status_code=400, detail="invalid published content")

    plain_msgs = "\n".join(
        f"{m.role}: {m.content[:50_000]}" for m in payload.messages[-30:]
    )
    user_prompt = _build_user_prompt(
        ch.published_content,
        payload.cell_id,
        plain_msgs,
        payload.current_code,
    )

    est = len(user_prompt) // 4
    sid = str(me.id)
    allowed, reason = check_and_record_request(
        sid,
        rpm=settings.chat_rpm,
        est_tokens=est + 500,
        daily_budget=settings.chat_daily_token_budget,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=reason,
        )

    cfg = await get_effective_llm_config(db)
    base = normalize_openai_compat_base_url(cfg.base_url)
    if not base:
        # 未配置上游：不调用外网；正文对学生尽量短，运维见 services/api/.env.example。
        mock_body = {
            "ok": True,
            "mock": True,
            "message": "尚未连接 AI 模型。",
            "at": datetime.now(timezone.utc).isoformat(),
        }
        return JSONResponse(content=mock_body)

    url = openai_compat_chat_completions_url(base)
    api_key = cfg.api_key
    messages = [
        {
            "role": "system",
            "content": "You are a short Python learning assistant. Answer in the user's language. "
            "Do not output huge code dumps unless needed.",
        },
        {"role": "user", "content": _truncate(user_prompt, settings.chat_context_max_chars)},
    ]
    jbody: dict = {
        "model": cfg.chat_model,
        "messages": messages,
    }
    if payload.stream:
        jbody["stream"] = True
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    headers = merge_openai_compat_llm_headers(base, headers)

    if payload.stream:
        return StreamingResponse(
            _stream_chat(url, jbody, headers),
            media_type="text/event-stream",
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=jbody, headers=headers)
    except httpx.RequestError as e:
        # 未连上上游：DNS/超时/断网/TLS 等，勿裸奔为 500
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"upstream_unavailable: {e!s}"[:2000],
        ) from e

    if resp.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="upstream 429"
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502, detail=resp.text[:2000] or f"http {resp.status_code}"
        )
    try:
        out = resp.json()
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"bad upstream json: {e!s}; body: {resp.text[:800]!r}",
        ) from e
    try:
        ch0 = out["choices"][0]
        msg = ch0.get("message") or {}
        text = msg.get("content")
    except (KeyError, IndexError, TypeError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"bad upstream shape: {e!s}; keys={list(out)[:12]}",
        ) from e
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(
            status_code=502,
            detail="empty assistant message from upstream (check model id and account)",
        )
    return {
        "ok": True,
        "message": text,
        "at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/chat")
async def student_chat(
    me: CurrentStudent,
    payload: ChatBody,
    db: DBSession,
):
    try:
        return await _student_chat_impl(me, payload, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"chat_unhandled: {type(e).__name__}: {e!s}"[:2000],
        ) from e


async def _stream_chat(
    url: str, jbody: dict, headers: dict
) -> AsyncIterator[bytes]:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=jbody, headers=headers) as r:
                if r.status_code >= 400:
                    err = (await r.aread())[:2000]
                    err_obj = {
                        "error": f"http {r.status_code}",
                        "body": err.decode("utf-8", errors="replace"),
                    }
                    yield f"data: {json.dumps(err_obj, ensure_ascii=False)}\n\n".encode()
                    return
                async for line in r.aiter_lines():
                    if line == "":
                        continue
                    yield (line if line.endswith("\n") else line + "\n").encode("utf-8")
                yield b"data: [DONE]\n\n"
    except httpx.RequestError as e:
        err_obj = {"error": "upstream_unavailable", "detail": str(e)[:1500]}
        yield f"data: {json.dumps(err_obj, ensure_ascii=False)}\n\n".encode()
