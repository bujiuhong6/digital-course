"""
章内容 **LLM 生成**（任务 7；任务 6 通过此模块拉草稿）。

- **`CHAPTER_GEN_MOCK=1` 或 `Settings.chapter_gen_mock`**：返回**固定**合法 **§4.2** JSON（`sample_published_v1`）。
- 否则：`httpx` **POST** `LLM_BASE_URL`（默认 `/v1/chat/completions` 拼在基址后，OpenAI 兼容）；`429` **指数退避**重试（最多 4 次尝试）。
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from ..config import settings
from .chapter_json import sample_published_v1


def _mock_enabled() -> bool:
    v = os.environ.get("CHAPTER_GEN_MOCK", "").strip()
    if v == "1" or (v and v.lower() in ("true", "yes")):
        return True
    return bool(settings.chapter_gen_mock)


async def generate_chapter_draft(
    source_material: str | None,
    *,
    model: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """
    返回 `(parsed_object_or_none, raw_model_text, error_string_or_none)`。

    设计 §4.3：可解析的 dict 与原文用于 `ai_generated_draft` / `ai_generated_raw`。
    """
    if _mock_enabled():
        d = sample_published_v1()
        s = json.dumps(d, ensure_ascii=False)
        return d, s, None

    base = (settings.llm_base_url or "").rstrip()
    if not base:
        d = sample_published_v1()
        s = json.dumps(d, ensure_ascii=False)
        return d, s, "LLM base URL empty; returned in-process sample (configure LLM_BASE_URL for live)"

    url = f"{base}/v1/chat/completions"
    body = {
        "model": model or "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": "Reply with ONLY valid JSON, version 1 chapter blocks, no markdown, keys camelCase. "
                f"Source material:\n{source_material or ''}",
            }
        ],
    }
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    delay = 1.0
    last_err: str | None = "no response"
    for _ in range(4):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as e:
            last_err = str(e)[:2000]
            await asyncio.sleep(delay)
            delay *= 2.0
            continue
        raw = r.text
        if r.status_code == 429:
            last_err = "429 " + raw[:500]
            await asyncio.sleep(delay)
            delay *= 2.0
            continue
        if r.status_code >= 400:
            return None, raw, f"http {r.status_code}"
        try:
            outer = r.json()
            txt = outer["choices"][0]["message"]["content"]
        except (KeyError, json.JSONDecodeError, IndexError) as e:
            return None, raw, f"llm response shape: {e!s}"
        if not isinstance(txt, str) or not txt.strip():
            return None, raw, "empty content"
        # 模型有时包 ```json
        t = txt.strip()
        if t.startswith("```"):
            t = t.removeprefix("```json").removeprefix("```").strip()
            if t.endswith("```"):
                t = t[: -3].strip()
        try:
            parsed = json.loads(t)
        except json.JSONDecodeError as e:
            return None, txt, f"content json: {e!s}"
        if not isinstance(parsed, dict):
            return None, txt, "root not object"
        return parsed, txt, None
    return None, None, last_err
