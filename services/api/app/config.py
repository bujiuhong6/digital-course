from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 32 字节全零的 base64，仅作本地/脚手架默认；生产环境务必用 `STUDENT_PASSWORD_KEY` 覆盖。
_DEFAULT_STUDENT_PASSWORD_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/teach.db"
    jwt_secret: str = "change-me-in-prod"
    student_password_key: str = Field(
        default=_DEFAULT_STUDENT_PASSWORD_KEY,
        description="32 字节随机密钥的 base64（AES-GCM 加密学生可逆密码）。",
    )
    admin_bootstrap_token: str | None = None
    # 生产 HTTPS 下设为 true，使 `teacher_session` 带 Secure；本地 http 可 false。
    admin_cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
