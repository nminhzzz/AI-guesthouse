import redis

from app.core.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=int(settings.REDIS_PORT) if settings.REDIS_PORT else 6379,
    decode_responses=True,
)
