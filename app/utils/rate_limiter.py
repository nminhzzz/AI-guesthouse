from fastapi import HTTPException

from app.redis.redis_client import redis_client

RATE_LIMIT = 5
WINDOW_SECONDS = 15 * 60


def check_rate_limit(ip: str) -> None:
    key = f"login_attempts:{ip}"

    attempts = redis_client.get(key)

    if attempts is None:
        redis_client.set(key, 1, ex=WINDOW_SECONDS)
        return

    attempts = int(attempts)

    if attempts >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )

    redis_client.incr(key)


def reset_rate_limit(ip: str) -> None:
    redis_client.delete(f"login_attempts:{ip}")