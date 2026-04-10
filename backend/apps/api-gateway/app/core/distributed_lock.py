from __future__ import annotations

import logging
import uuid

from app.core.cache import get_redis_client

logger = logging.getLogger(__name__)

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


def acquire_distributed_lock(lock_key: str, ttl_sec: int) -> str | None:
    client = get_redis_client()
    if client is None:
        # Redis unavailable: degrade and allow request path.
        return "__no_redis__"
    token = uuid.uuid4().hex
    try:
        ok = client.set(lock_key, token, nx=True, ex=max(1, int(ttl_sec)))
        return token if ok else None
    except Exception:
        logger.exception("Acquire distributed lock failed: key=%s", lock_key)
        return "__no_redis__"


def release_distributed_lock(lock_key: str, token: str | None) -> None:
    if not token or token == "__no_redis__":
        return
    client = get_redis_client()
    if client is None:
        return
    try:
        client.eval(_RELEASE_SCRIPT, 1, lock_key, token)
    except Exception:
        logger.exception("Release distributed lock failed: key=%s", lock_key)
