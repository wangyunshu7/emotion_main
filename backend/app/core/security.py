import hashlib
import hmac
import json
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import get_settings

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(24))


def digest(value: str, purpose: str = "session") -> str:
    return hmac.new(
        get_settings().session_token_pepper.encode(), f"{purpose}:{value}".encode(), hashlib.sha256
    ).hexdigest()


def fingerprint(data) -> str:
    return digest(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str), "request")


def verify_password(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False
