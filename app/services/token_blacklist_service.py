import hashlib

from app.cache.redis_client import redis_client


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def blacklist_token(token: str, expires_in: int) -> None:
    if expires_in <= 0:
        return
    redis_client.set(
        f"blacklist:token:{_hash_value(token)}",
        "1",
        ex=expires_in,
    )


def blacklist_jti(jti: str, expires_in: int) -> None:
    if expires_in <= 0:
        return
    redis_client.set(
        f"blacklist:jti:{jti}",
        "1",
        ex=expires_in,
    )


def is_blacklisted(token: str) -> bool:
    return redis_client.get(f"blacklist:token:{_hash_value(token)}") is not None


def is_jti_blacklisted(jti: str) -> bool:
    return redis_client.get(f"blacklist:jti:{jti}") is not None
