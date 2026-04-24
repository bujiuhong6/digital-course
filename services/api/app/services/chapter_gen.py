"""
章内容 **LLM 生成**（任务 7）。

- 环境变量 **`CHAPTER_GEN_MOCK=1`**（或 `true`/`yes`）：返回**固定**合法 **§4.2** JSON（`sample_published_v1`），供测试与无密钥开发。
- **`CHAPTER_GEN_MOCK=0`**：强制**非** mock；若未显式设 env，则使用 `Settings.chapter_gen_mock`（默认 True = mock）。

- **非 mock**：`httpx` **POST** `{LLM_BASE_URL}/v1/chat/completions`，`Authorization: Bearer {LLM_API_KEY}`；
  需配置 **`LLM_BASE_URL`**（无则返回错误，不静默回退样例）。**429** 与部分网络错误：**指数退避**重试（最多 4 次尝试）。

厂家、模型名由 `LLM_BASE_URL`、`CHAPTER_GEN_MODEL`（或 `settings.chapter_gen_model`）决定。
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx

from ..config import (
    merge_openai_compat_llm_headers,
    normalize_openai_compat_base_url,
    settings,
)
from .chapter_json import sample_published_v1

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "prompts" / "chapter-generate.v1.md"
)


def _mock_from_env_and_settings() -> bool:
    raw = os.environ.get("CHAPTER_GEN_MOCK")
    if raw is not None:
        v = raw.strip()
        if v == "1" or v.lower() in ("true", "yes", "on"):
            return True
        if v in ("0", "") or v.lower() in ("false", "no", "off"):
            return False
    return bool(settings.chapter_gen_mock)


def _prompt_instruction() -> str:
    try:
        text = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return "Output a single JSON object: version 1, blocks with camelCase keys per API doc."
    return text[:12000]


async def generate_chapter_draft(
    source_material: str | None,
    *,
    model: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """
    返回 `(parsed_object_or_none, raw_model_text, error_string_or_none)`。

    成功：`parsed` 为 dict、`raw` 为模型原文或 JSON 串、`error` 为 None。
    """
    if _mock_from_env_and_settings():
        d = sample_published_v1()
        s = json.dumps(d, ensure_ascii=False)
        return d, s, None

    base = normalize_openai_compat_base_url(settings.llm_base_url)
    if not base:
        return (
            None,
            None,
            "LLM_BASE_URL is required when chapter generation is not in mock mode (set CHAPTER_GEN_MOCK=1 to use fixed JSON).",
        )

    m = model or settings.chapter_gen_model
    url = f"{base}/v1/chat/completions"
    sys_rules = _prompt_instruction()
    user_block = f"{sys_rules}\n\n--- source_material ---\n{source_material or ''}"
    body = {
        "model": m,
        "messages": [
            {"role": "system", "content": "You output only valid JSON. No markdown fences."},
            {"role": "user", "content": user_block},
        ],
    }
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    headers = merge_openai_compat_llm_headers(base, headers)

    delay = 1.0
    last_err: str | None = "exhausted retries"
    for attempt in range(4):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as e:
            last_err = f"http error: {e!s}"[:2000]
            await asyncio.sleep(delay)
            delay = min(delay * 2.0, 16.0)
            continue

        raw_http = r.text
        if r.status_code == 429:
            last_err = f"429 {raw_http[:800]}"
            await asyncio.sleep(delay)
            delay = min(delay * 2.0, 16.0)
            continue
        if r.status_code >= 400:
            return None, raw_http, f"http {r.status_code}: {raw_http[:500]}"

        try:
            outer = r.json()
            txt = outer["choices"][0]["message"]["content"]
        except (KeyError, json.JSONDecodeError, IndexError, TypeError) as e:
            return None, raw_http, f"llm response shape: {e!s}"

        if not isinstance(txt, str) or not txt.strip():
            return None, raw_http, "empty content"

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
