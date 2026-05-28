from app.redis.redis_client import redis_client


def blacklist_token(
    token: str,
    expires_in: int
):
    """
    Lưu token vào Redis blacklist
    """

    redis_client.set(
        f"blacklist:{token}",
        "1",
        ex=expires_in
    )


def is_blacklisted(
    token: str
):
    """
    Kiểm tra token có bị blacklist không
    """

    result = redis_client.get(
        f"blacklist:{token}"
    )

    return result is not None