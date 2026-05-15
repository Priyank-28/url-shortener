import redis
from app.config import settings

redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    decode_responses=True
)

CACHE_TTL = 3600  # 1 hour

def get_cached_url(short_code: str) -> str | None:
    return redis_client.get(f"url:{short_code}")

def set_cached_url(short_code: str, original_url: str) -> None:
    redis_client.setex(f"url:{short_code}", CACHE_TTL, original_url)

def increment_clicks(short_code: str) -> None:
    redis_client.incr(f"clicks:{short_code}")