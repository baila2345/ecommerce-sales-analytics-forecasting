from hashlib import sha256

from redis import Redis
from redis.exceptions import RedisError


class AnalyticsCache:
    def __init__(self, redis_url: str) -> None:
        self.client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
        )

    @staticmethod
    def dashboard_key(query_json: str) -> str:
        digest = sha256(query_json.encode()).hexdigest()
        return f"analytics:dashboard:v1:{digest}"

    def get(self, key: str) -> str | None:
        try:
            value = self.client.get(key)
            return value if isinstance(value, str) else None
        except RedisError:
            return None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            self.client.setex(key, ttl_seconds, value)
        except RedisError:
            pass
