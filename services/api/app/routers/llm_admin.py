from __future__ import annotations

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from starlette import status

from ..config import merge_openai_compat_llm_headers, openai_compat_chat_completions_url
from ..deps import CurrentTeacher, DBSession
from ..services.llm_config import (
    PROVIDER_PRESETS,
    get_effective_llm_config,
    get_llm_config_row,
    llm_config_to_public_dict,
    upsert_llm_config,
)


router = APIRouter(tags=["admin", "llm-config"])
templates = Jinja2Templates(directory="app/templates")


class LLMConfigBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str = Field(default="deepseek", max_length=64)
    base_url: str = Field(default="", max_length=512, alias="baseUrl")
    api_key: str | None = Field(default=None, max_length=4096, alias="apiKey")
    clear_api_key: bool = Field(default=False, alias="clearApiKey")
    chapter_model: str = Field(default="gpt-4o-mini", max_length=128, alias="chapterModel")
    chat_model: str = Field(default="gpt-4o-mini", max_length=128, alias="chatModel")
    enabled: bool = False


@router.get("/v1/admin/llm-config")
async def get_config(_t: CurrentTeacher, db: DBSession) -> dict:
    row = await get_llm_config_row(db)
    return {
        "ok": True,
        "presets": PROVIDER_PRESETS,
        "config": llm_config_to_public_dict(row),
    }


@router.post("/v1/admin/llm-config")
async def save_config(_t: CurrentTeacher, db: DBSession, body: LLMConfigBody) -> dict:
    row = await upsert_llm_config(
        db,
        provider=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
        clear_api_key=body.clear_api_key,
        chapter_model=body.chapter_model,
        chat_model=body.chat_model,
        enabled=body.enabled,
    )
    return {"ok": True, "config": llm_config_to_public_dict(row)}


@router.post("/v1/admin/llm-config/test")
async def test_config(_t: CurrentTeacher, db: DBSession) -> dict:
    cfg = await get_effective_llm_config(db)
    if not cfg.base_url:
        return {"ok": False, "error": "请先填写 URL 并启用配置。"}
    url = openai_compat_chat_completions_url(cfg.base_url)
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    headers = merge_openai_compat_llm_headers(cfg.base_url, headers)
    body = {
        "model": cfg.chat_model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"连接失败：{e!s}"[:500]}
    if resp.status_code >= 400:
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:500]}"}
    return {"ok": True}


@router.get("/teacher/llm-settings", response_class=HTMLResponse)
async def page_llm_settings(request: Request, _t: CurrentTeacher, db: DBSession):
    row = await get_llm_config_row(db)
    return templates.TemplateResponse(
        request,
        "teacher/llm_settings.html",
        {
            "presets": PROVIDER_PRESETS,
            "config": llm_config_to_public_dict(row),
            "saved": request.query_params.get("saved") == "1",
        },
    )


@router.post("/teacher/llm-settings")
async def post_llm_settings(
    _t: CurrentTeacher,
    db: DBSession,
    provider: str = Form("deepseek"),
    base_url: str = Form("", alias="baseUrl"),
    api_key: str = Form("", alias="apiKey"),
    clear_api_key: str | None = Form(default=None, alias="clearApiKey"),
    chapter_model: str = Form("gpt-4o-mini", alias="chapterModel"),
    chat_model: str = Form("gpt-4o-mini", alias="chatModel"),
    enabled: str | None = Form(default=None),
):
    await upsert_llm_config(
        db,
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        clear_api_key=clear_api_key == "1",
        chapter_model=chapter_model,
        chat_model=chat_model,
        enabled=enabled == "1",
    )
    return RedirectResponse(
        url="/teacher/llm-settings?saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
