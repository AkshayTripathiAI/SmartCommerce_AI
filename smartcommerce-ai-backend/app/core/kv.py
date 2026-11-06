"""Small async key-value store: Redis when REDIS_URL is set, in-process otherwise.

The in-process store keeps the app runnable on single-instance free hosting
(no Redis add-on needed). Data is lost on restart, which is fine for
embedding caches and short-lived chat history.
"""
import time
from typing import Any, Dict, Optional, Tuple

from app.config import settings


class InMemoryKV:
    """Minimal subset of the redis.asyncio API used by this app."""

    def __init__(self, max_keys: int = 5000):
        self._data: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._max_keys = max_keys

    def _alive(self, key: str) -> bool:
        item = self._data.get(key)
        if item is None:
            return False
        _, expires = item
        if expires is not None and expires < time.monotonic():
            del self._data[key]
            return False
        return True

    async def get(self, key: str):
        return self._data[key][0] if self._alive(key) else None

    async def setex(self, key: str, ttl_seconds: int, value: Any):
        if len(self._data) >= self._max_keys and key not in self._data:
            # Drop the oldest inserted key (dicts keep insertion order).
            self._data.pop(next(iter(self._data)))
        self._data[key] = (value, time.monotonic() + ttl_seconds)

    async def delete(self, key: str):
        self._data.pop(key, None)

    async def close(self):
        pass


_memory_kv = InMemoryKV()
_redis_clients: Dict[bool, Any] = {}


def get_kv(decode_responses: bool = True):
    """Return a shared KV client."""
    if not settings.redis_url:
        return _memory_kv
    if decode_responses not in _redis_clients:
        import redis.asyncio as redis

        _redis_clients[decode_responses] = redis.from_url(
            settings.redis_url, decode_responses=decode_responses
        )
    return _redis_clients[decode_responses]
