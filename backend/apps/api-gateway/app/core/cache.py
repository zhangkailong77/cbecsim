import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import redis
except Exception:  # pragma: no cover - optional dependency fallback
    redis = None  # type: ignore[assignment]


_redis_client: "redis.Redis | None" = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _cache_enabled() -> bool:
    if not _env_bool("REDIS_CACHE_ENABLE", False):
        return False
    return bool(os.getenv("REDIS_URL", "").strip())


def _get_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if redis is None or not _cache_enabled():
        return None
    try:
        _redis_client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "").strip(),
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
            health_check_interval=30,
        )
        return _redis_client
    except Exception:
        logger.exception("Redis client init failed")
        _redis_client = None
        return None


def get_redis_client():
    return _get_client()


def cache_get_json(key: str) -> Any | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.exception("Redis cache get failed: key=%s", key)
        return None


def cache_set_json(key: str, value: Any, ttl_sec: int) -> None:
    if ttl_sec <= 0:
        return
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, int(ttl_sec), json.dumps(value, ensure_ascii=False))
    except Exception:
        logger.exception("Redis cache set failed: key=%s", key)


def cache_delete_prefix(prefix: str) -> int:
    client = _get_client()
    if client is None:
        return 0
    deleted = 0
    try:
        for key in client.scan_iter(match=f"{prefix}*"):
            deleted += int(client.delete(key) or 0)
    except Exception:
        logger.exception("Redis cache delete by prefix failed: prefix=%s", prefix)
    return deleted
