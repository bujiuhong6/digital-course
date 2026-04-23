"""Signed HttpOnly cookie `teacher_session` (设计 §3.1).

格式：`v1.<base64url(payload_json)>.<base64url(hmac_sha256)>`。密钥使用 `Settings.jwt_secret`。
非 Bearer：教师端仅接受此 Cookie（实现计划 任务 3）。
"""

from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256
from typing import Any

from ..config import settings

V = 1
COOKIE_TTL_S = 7 * 24 * 3600
SUBJECT_ADMIN = "admin"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s.encode("ascii"))


def _signing_key() -> bytes:
    return sha256(settings.jwt_secret.encode("utf-8")).digest()


def create_teacher_session_value() -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "v": V,
        "sub": SUBJECT_ADMIN,
        "exp": now + COOKIE_TTL_S,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    p = _b64url_encode(raw)
    msg = f"v{V}.{p}".encode("ascii")
    sig = hmac.new(_signing_key(), msg, sha256).digest()
    s = _b64url_encode(sig)
    return f"v{V}.{p}.{s}"


def parse_teacher_session_value(token: str) -> dict[str, Any] | None:
    if not token or not token.startswith("v1."):
        return None
    parts = token.split(".", 2)
    if len(parts) != 3:
        return None
    ver, p, s = parts
    if ver != "v1":
        return None
    try:
        sig_expected = _b64url_decode(s)
        msg = f"{ver}.{p}".encode("ascii")
        sig = hmac.new(_signing_key(), msg, sha256).digest()
        if not hmac.compare_digest(sig_expected, sig):
            return None
        data = json.loads(_b64url_decode(p).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if data.get("v") != V or data.get("sub") != SUBJECT_ADMIN:
        return None
    exp = data.get("exp")
    if not isinstance(exp, int) or exp <= int(time.time()):
        return None
    return data
