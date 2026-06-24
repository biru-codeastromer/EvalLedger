from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from app.config import get_settings
from app.errors import AppError

settings = get_settings()

JWT_ISSUER = "evalledger"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expiry_minutes: int | None = None,
) -> str:
    now = datetime.now(UTC)
    minutes = expiry_minutes if expiry_minutes is not None else settings.jwt_expiration_minutes
    payload: dict[str, Any] = {
        "sub": subject,
        "iss": JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=JWT_ISSUER,
        )
    except jwt.PyJWTError as exc:
        raise AppError("invalid_token", "Invalid or expired access token", status_code=401) from exc
    if not isinstance(payload, dict):
        raise AppError("invalid_token", "Invalid token payload", status_code=401)
    return payload


def generate_api_key() -> str:
    return f"el_{uuid4().hex}{uuid4().hex}"


def hash_api_key(api_key: str) -> str:
    return sha256(api_key.encode("utf-8")).hexdigest()
