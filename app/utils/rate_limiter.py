from fastapi import HTTPException

from app.core.config import settings
from app.cache.redis_client import redis_client


def _increment_or_block(key: str, limit: int, window_seconds: int) -> None:
    attempts = redis_client.get(key)

    if attempts is None:
        redis_client.set(key, 1, ex=window_seconds)
        return

    attempts = int(attempts)
    if attempts >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again later.",
        )

    redis_client.incr(key)


def check_login_rate_limit(ip: str, email: str) -> None:
    _increment_or_block(
        f"login_attempts:ip:{ip}",
        settings.LOGIN_RATE_LIMIT,
        settings.LOGIN_RATE_WINDOW_SECONDS,
    )
    _increment_or_block(
        f"login_attempts:email:{email.lower()}",
        settings.LOGIN_RATE_LIMIT,
        settings.LOGIN_RATE_WINDOW_SECONDS,
    )


def reset_login_rate_limit(ip: str, email: str) -> None:
    redis_client.delete(f"login_attempts:ip:{ip}")
    redis_client.delete(f"login_attempts:email:{email.lower()}")


def check_register_rate_limit(ip: str) -> None:
    _increment_or_block(
        f"register_attempts:ip:{ip}",
        settings.REGISTER_RATE_LIMIT,
        settings.REGISTER_RATE_WINDOW_SECONDS,
    )
