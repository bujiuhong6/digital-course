"""学生访问令牌：HS256 JWT，`sub` 为学生 UUID 字符串；`exp` 见 `Settings.student_jwt_exp_minutes`。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from ..config import settings

STUDENT_TOKEN_TYP = "student_v1"
ALG = "HS256"


def create_student_token(student_id: uuid.UUID) -> tuple[str, int]:
    """返回 (access_token, expires_in 秒)。"""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.student_jwt_exp_minutes)
    jti = str(uuid.uuid4())
    payload: dict = {
        "sub": str(student_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "typ": STUDENT_TOKEN_TYP,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALG)
    if isinstance(token, bytes):
        token = token.decode("ascii")
    return token, int((exp - now).total_seconds())


def decode_student_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALG],
        )
    except InvalidTokenError as e:
        raise ValueError("invalid token") from e
    if payload.get("typ") != STUDENT_TOKEN_TYP:
        raise ValueError("invalid token type")
    return payload
