from app.core.config import settings
from app.cache.redis_client import redis_client
from app.services.token_blacklist_service import blacklist_jti


def _version_key(user_id: str) -> str:
    return f"user:token_version:{user_id}"


def _session_key(user_id: str) -> str:
    return f"user:refresh_jti:{user_id}"


def get_token_version(user_id: str) -> int:
    value = redis_client.get(_version_key(user_id))
    return int(value) if value else 1


def bump_token_version(user_id: str) -> int:
    return int(redis_client.incr(_version_key(user_id)))


def set_active_refresh_jti(user_id: str, jti: str, ttl_seconds: int) -> None:
    redis_client.set(_session_key(user_id), jti, ex=ttl_seconds)
    redis_client.set(f"refresh_jti:{jti}", user_id, ex=ttl_seconds)


def get_active_refresh_jti(user_id: str) -> str | None:
    return redis_client.get(_session_key(user_id))


def clear_user_session(user_id: str) -> None:
    active_jti = get_active_refresh_jti(user_id)
    if active_jti:
        redis_client.delete(f"refresh_jti:{active_jti}")
    redis_client.delete(_session_key(user_id))


def rotate_refresh_session(
    user_id: str,
    old_jti: str,
    new_jti: str,
    ttl_seconds: int,
) -> None:
    active_jti = get_active_refresh_jti(user_id)
    if active_jti != old_jti:
        revoke_all_user_sessions(user_id, old_jti_ttl=ttl_seconds)
        raise ValueError("refresh_token_reused")

    blacklist_jti(old_jti, ttl_seconds)
    set_active_refresh_jti(user_id, new_jti, ttl_seconds)


def revoke_all_user_sessions(user_id: str, old_jti_ttl: int | None = None) -> int:
    active_jti = get_active_refresh_jti(user_id)
    if active_jti:
        ttl = old_jti_ttl or settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        blacklist_jti(active_jti, ttl)
    clear_user_session(user_id)
    return bump_token_version(user_id)
