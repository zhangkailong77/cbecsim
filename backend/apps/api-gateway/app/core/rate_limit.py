from __future__ import annotations

import logging
import os
import time

from app.core.cache import get_redis_client

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def check_rate_limit(*, key: str, limit: int, window_sec: int) -> tuple[bool, int, int]:
    if limit <= 0 or window_sec <= 0:
        return False, 0, 0
    if not _env_bool("REDIS_RATE_LIMIT_ENABLE", False):
        return False, limit, int(time.time()) + window_sec

    client = get_redis_client()
    if client is None:
        return False, limit, int(time.time()) + window_sec

    now = int(time.time())
    bucket = now // window_sec
    reset_at = (bucket + 1) * window_sec
    bucket_key = f"{key}:{bucket}"
    try:
        current = int(client.incr(bucket_key))
        client.expire(bucket_key, window_sec + 1)
    except Exception:
        logger.exception("Rate limit check failed: key=%s", key)
        return False, limit, reset_at

    limited = current > limit
    remaining = max(0, limit - current)
    return limited, remaining, reset_at
