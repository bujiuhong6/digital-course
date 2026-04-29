from __future__ import annotations

import json

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import merge_openai_compat_llm_headers, openai_compat_chat_completions_url
from .llm_config import get_effective_llm_config


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.removeprefix("```json").removeprefix("```").strip()
        if t.endswith("```"):
            t = t[:-3].strip()
    return t


async def grade_post_exercise(
    db: AsyncSession,
    *,
    content: dict,
    answers: list[dict],
) -> tuple[int, str, str]:
    cfg = await get_effective_llm_config(db)
    if not cfg.base_url:
        raise HTTPException(status_code=502, detail="llm_not_configured")
    url = openai_compat_chat_completions_url(cfg.base_url)
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    headers = merge_openai_compat_llm_headers(cfg.base_url, headers)
    prompt = (
        "你是课程课后作业批改员。请根据题目、标准答案、评分规则和学生答案，"
        "输出严格 JSON：{\"score\": 0-100整数, \"feedback\": \"给学生的简短反馈\"}。\n\n"
        f"题目JSON：{json.dumps(content, ensure_ascii=False)}\n\n"
        f"学生答案JSON：{json.dumps(answers, ensure_ascii=False)}"
    )
    body = {
        "model": cfg.chat_model,
        "messages": [
            {"role": "system", "content": "只输出 JSON，不要 markdown。"},
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
    raw = resp.text
    try:
        outer = resp.json()
        text = outer["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_fences(text))
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        raise HTTPException(status_code=502, detail=f"bad_grader_response: {e!s}") from e
    score = int(parsed.get("score", 0))
    score = max(0, min(100, score))
    feedback = str(parsed.get("feedback") or "")
    return score, feedback, raw
