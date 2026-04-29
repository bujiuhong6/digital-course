from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import (
    normalize_openai_compat_base_url,
    settings,
)
from ..db.models import LLMConfig
from .crypto import decrypt_secret, encrypt_secret


PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {"label": "DeepSeek", "baseUrl": "https://api.deepseek.com"},
    "qwen": {
        "label": "通义千问 Qwen",
        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode",
    },
    "minimax": {"label": "MiniMax", "baseUrl": "https://api.minimax.chat"},
    "kimi": {"label": "Kimi / Moonshot", "baseUrl": "https://api.moonshot.cn"},
    "glm": {"label": "智谱 GLM", "baseUrl": "https://open.bigmodel.cn/api/paas"},
    "custom": {"label": "自定义 OpenAI 兼容", "baseUrl": ""},
}


@dataclass(frozen=True)
class EffectiveLLMConfig:
    provider: str
    base_url: str
    api_key: str
    chapter_model: str
    chat_model: str
    enabled: bool
    source: str


def mask_api_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return value[:2] + "****"
    return f"{value[:4]}****{value[-4:]}"


def _normalize_provider(provider: str | None) -> str:
    p = (provider or "custom").strip().lower()
    return p if p in PROVIDER_PRESETS else "custom"


def _safe_decrypt(ciphertext: str | None) -> str:
    if not ciphertext:
        return ""
    try:
        return decrypt_secret(ciphertext)
    except Exception:
        return ""


async def get_llm_config_row(db: AsyncSession) -> LLMConfig | None:
    r = await db.execute(select(LLMConfig).where(LLMConfig.id == 1))
    return r.scalar_one_or_none()


async def upsert_llm_config(
    db: AsyncSession,
    *,
    provider: str,
    base_url: str,
    api_key: str | None,
    clear_api_key: bool,
    chapter_model: str,
    chat_model: str,
    enabled: bool,
) -> LLMConfig:
    row = await get_llm_config_row(db)
    if row is None:
        row = LLMConfig(id=1)
        db.add(row)
    row.provider = _normalize_provider(provider)
    row.base_url = normalize_openai_compat_base_url((base_url or "").strip())
    row.chapter_model = (chapter_model or settings.chapter_gen_model).strip()
    row.chat_model = (chat_model or settings.chat_model).strip()
    row.enabled = bool(enabled)
    if clear_api_key:
        row.api_key_ciphertext = None
    elif api_key is not None and api_key.strip():
        row.api_key_ciphertext = encrypt_secret(api_key.strip())
    await db.flush()
    return row


def llm_config_to_public_dict(row: LLMConfig | None) -> dict:
    if row is None:
        return {
            "provider": "deepseek",
            "baseUrl": "",
            "apiKeyMasked": "",
            "chapterModel": settings.chapter_gen_model,
            "chatModel": settings.chat_model,
            "enabled": False,
        }
    secret = _safe_decrypt(row.api_key_ciphertext)
    return {
        "provider": row.provider,
        "baseUrl": row.base_url,
        "apiKeyMasked": mask_api_key(secret),
        "chapterModel": row.chapter_model,
        "chatModel": row.chat_model,
        "enabled": row.enabled,
    }


async def get_effective_llm_config(db: AsyncSession) -> EffectiveLLMConfig:
    row = await get_llm_config_row(db)
    if row is not None and row.enabled:
        return EffectiveLLMConfig(
            provider=row.provider,
            base_url=normalize_openai_compat_base_url(row.base_url),
            api_key=_safe_decrypt(row.api_key_ciphertext),
            chapter_model=row.chapter_model,
            chat_model=row.chat_model,
            enabled=True,
            source="db",
        )
    return EffectiveLLMConfig(
        provider="env",
        base_url=normalize_openai_compat_base_url(settings.chat_llm_base_url or settings.llm_base_url),
        api_key=settings.chat_llm_api_key or settings.llm_api_key,
        chapter_model=settings.chapter_gen_model,
        chat_model=settings.chat_model,
        enabled=bool(settings.chat_llm_base_url or settings.llm_base_url),
        source="env",
    )


async def get_effective_chapter_llm_config(db: AsyncSession) -> EffectiveLLMConfig:
    row = await get_llm_config_row(db)
    if row is not None and row.enabled:
        return EffectiveLLMConfig(
            provider=row.provider,
            base_url=normalize_openai_compat_base_url(row.base_url),
            api_key=_safe_decrypt(row.api_key_ciphertext),
            chapter_model=row.chapter_model,
            chat_model=row.chat_model,
            enabled=True,
            source="db",
        )
    return EffectiveLLMConfig(
        provider="env",
        base_url=normalize_openai_compat_base_url(settings.llm_base_url),
        api_key=settings.llm_api_key,
        chapter_model=settings.chapter_gen_model,
        chat_model=settings.chat_model,
        enabled=bool(settings.llm_base_url),
        source="env",
    )
