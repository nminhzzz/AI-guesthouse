from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from jose import JWTError, jwt

from app.core.config import settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_expires(minutes: int = 0, days: int = 0) -> int:
    expire_at = _utc_now() + timedelta(minutes=minutes, days=days)
    return int(expire_at.timestamp())


def create_access_token(data: dict, token_version: int) -> tuple[str, str, int]:
    jti = str(uuid4())
    expires_at = _build_expires(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        **data,
        "jti": jti,
        "token_version": token_version,
        "exp": expires_at,
        "type": "access",
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def create_refresh_token(data: dict, token_version: int) -> tuple[str, str, int]:
    jti = str(uuid4())
    expires_at = _build_expires(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        **data,
        "jti": jti,
        "token_version": token_version,
        "exp": expires_at,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    return token, jti, ttl


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        return None


def verify_token_type(token: str, expected_type: str) -> Optional[dict]:
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def get_token_ttl(payload: dict) -> int:
    exp = payload.get("exp")
    if not exp:
        return 0
    return max(int(exp - _utc_now().timestamp()), 0)
