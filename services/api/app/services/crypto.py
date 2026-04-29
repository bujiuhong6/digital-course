"""学生登录密码的 AES-256-GCM 可逆加密（设计 §3.2；库内 **base64(nonce + ciphertext+tag)**）。"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import settings


def _raw_key() -> bytes:
    raw = base64.b64decode(settings.student_password_key)
    if len(raw) != 32:
        raise ValueError("STUDENT_PASSWORD_KEY (base64) must decode to 32 bytes")
    return raw


def encrypt_password(plain: str) -> str:
    key = _raw_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plain.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_password(ciphertext_b64: str) -> str:
    raw = base64.b64decode(ciphertext_b64)
    if len(raw) < 13:
        raise ValueError("invalid ciphertext")
    nonce, data = raw[:12], raw[12:]
    aesgcm = AESGCM(_raw_key())
    return aesgcm.decrypt(nonce, data, None).decode("utf-8")


def encrypt_secret(plain: str) -> str:
    return encrypt_password(plain)


def decrypt_secret(ciphertext_b64: str) -> str:
    return decrypt_password(ciphertext_b64)
