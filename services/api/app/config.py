from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 32 字节全零的 base64，仅作本地/脚手架默认；生产环境务必用 `STUDENT_PASSWORD_KEY` 覆盖。
_DEFAULT_STUDENT_PASSWORD_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def normalize_openai_compat_base_url(url: str) -> str:
    """
    章生成与聊天均拼接 `{base}/v1/chat/completions`；若把官方示例里的
    `.../v1` 写进 `LLM_BASE_URL`，会重复为 `/v1/v1/...`。
    这里去掉尾部的 `/v1` 与尾斜杠；空串保持空。
    """
    s = (url or "").strip()
    if not s:
        return ""
    s = s.rstrip("/")
    if s.lower().endswith("/v1"):
        s = s[:-3].rstrip("/")
    return s


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/teach.db"
    jwt_secret: str = "change-me-in-prod"
    student_password_key: str = Field(
        default=_DEFAULT_STUDENT_PASSWORD_KEY,
        description="32 字节随机密钥的 base64（AES-GCM 加密学生可逆密码，设计称 STUDENT_PASSWORD_ENCRYPTION_KEY）。",
        validation_alias=AliasChoices("STUDENT_PASSWORD_KEY", "STUDENT_PASSWORD_ENCRYPTION_KEY"),
    )
    admin_bootstrap_token: str | None = None
    # 生产 HTTPS 下设为 true，使 `teacher_session` 带 Secure；本地 http 可 false。
    admin_cookie_secure: bool = False
    # 学生 JWT 有效期（分钟）；设计 §3.2：短效。
    student_jwt_exp_minutes: int = 15
    # 任务 7：章 LLM。`CHAPTER_GEN_MOCK=1` 见 `chapter_gen._mock_from_env` / Settings。
    chapter_gen_mock: bool = Field(
        default=True,
        description="为 False 且未设 CHAPTER_GEN_MOCK=1 时用 httpx 调 LLM。",
    )
    llm_base_url: str = Field(
        default="",
        description="OpenAI 兼容 API 基址，无尾斜杠，如 https://api.openai.com；空则真机模式不发起请求。",
    )
    llm_api_key: str = Field(default="", description="Bearer token；章生成等。")
    chapter_gen_model: str = Field(
        default="gpt-4o-mini",
        description="chat/completions 的 model 名。环境变量同字段名大写。",
    )
    chapter_extension_starter_code_max_len: int = 8000
    generator_prompt_version: str = "v1"
    # 发布时：扩展题 passRule 仅 `no_exception` 时是否拒绝（设计 §4.2 建议 stronger 规则）
    chapter_publish_reject_extension_no_exception: bool = True
    # 任务 9 / 设计 §7；环境名与设计文档一致
    chat_llm_base_url: str = Field(
        default="",
        description="OpenAI 兼容聊天 API 基址。",
        validation_alias=AliasChoices("CHAT_LLM_BASE_URL",),
    )
    chat_llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("CHAT_LLM_API_KEY",),
    )
    chat_model: str = Field(
        default="gpt-4o-mini",
    )
    chat_context_max_chars: int = Field(
        default=12_000,
        validation_alias=AliasChoices("CHAT_CONTEXT_MAX_CHARS",),
    )
    chat_rpm: int = Field(
        default=20,
    )
    chat_daily_token_budget: int = Field(
        default=0,
        description="0 表示不限制。",
    )
    # OpenRouter 可选头（见 openrouter.ai 文档；用于在排行榜展示来源，非鉴权所必需）
    openrouter_http_referer: str = Field(
        default="",
        description="发向 openrouter.ai 时可选的 HTTP-Referer。",
        validation_alias=AliasChoices("OPENROUTER_HTTP_REFERER", "OPENROUTER_REFERER"),
    )
    openrouter_title: str = Field(
        default="",
        description="发向 openrouter.ai 时可选的 X-OpenRouter-Title。",
        validation_alias=AliasChoices("OPENROUTER_TITLE",),
    )

    @field_validator("llm_base_url", "chat_llm_base_url", mode="before")
    @classmethod
    def _normalize_openai_base_urls(cls, v: object) -> object:
        if v is None or not isinstance(v, str):
            return v
        return normalize_openai_compat_base_url(v)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def extra_headers_for_openai_compat_provider(base_url_normalized: str) -> dict[str, str]:
    """
    对 OpenAI 兼容网关追加厂商推荐的可选头（当前仅对 OpenRouter 基址识别）。
    """
    b = (base_url_normalized or "").lower()
    h: dict[str, str] = {}
    if "openrouter.ai" not in b:
        return h
    s = settings
    r = (s.openrouter_http_referer or "").strip()
    t = (s.openrouter_title or "").strip()
    if r:
        h["HTTP-Referer"] = r
    if t:
        h["X-OpenRouter-Title"] = t
    return h


def merge_openai_compat_llm_headers(
    base_url_normalized: str, headers: dict[str, str]
) -> dict[str, str]:
    return {**headers, **extra_headers_for_openai_compat_provider(base_url_normalized)}


settings = Settings()
