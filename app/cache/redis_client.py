import importlib

from app.core.config import settings

# Tránh xung đột nếu có folder tên redis trong PYTHONPATH
_redis = importlib.import_module("redis")
Redis = _redis.Redis

redis_client = Redis(
    host=settings.REDIS_HOST,
    port=int(settings.REDIS_PORT) if settings.REDIS_PORT else 6379,
    decode_responses=True,
)
