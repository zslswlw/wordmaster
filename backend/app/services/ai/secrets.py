import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    secret = os.getenv(
        "APP_SECRET_KEY",
        "wordmaster-secret-key-change-in-production",
    )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    if not value or value.startswith(_PREFIX):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    if not value or not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("API Key 无法解密，请使用当前 APP_SECRET_KEY 或重新保存密钥") from exc
