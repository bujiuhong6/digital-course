from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 32 字节全零的 base64，仅作本地/脚手架默认；生产环境务必用 `STUDENT_PASSWORD_KEY` 覆盖。
_DEFAULT_STUDENT_PASSWORD_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


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
    # 章生成：任务 6–7；`CHAPTER_GEN_MOCK=1` 在 `chapter_gen` 内单独读取
    chapter_gen_mock: bool = True
    llm_base_url: str = "https://api.example.com"
    llm_api_key: str = ""
    chapter_extension_starter_code_max_len: int = 8000
    generator_prompt_version: str = "v1"
    # 发布时：扩展题 passRule 仅 `no_exception` 时是否拒绝（设计 §4.2 建议更强规则）
    chapter_publish_reject_extension_no_exception: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
