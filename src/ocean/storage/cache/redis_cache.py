"""Cache em Redis com prefixo próprio (`mcp:`) para não colidir com o rate limit da API.

Falha de forma silenciosa: sem Redis, o cache simplesmente não existe e a fonte é consultada.
"""

import json
import logging
import threading
import time
from typing import Any

import redis

from ocean.shared.config import get_settings

log = logging.getLogger(__name__)


class Cache:
    def __init__(self, url: str | None = None, prefix: str = "mcp:") -> None:
        self._url = get_settings().redis_url if url is None else url or None
        self._prefix = prefix
        self._client: redis.Redis | None = None
        self._memory: dict[str, tuple[float, str]] = {}
        self._memory_lock = threading.Lock()

    def _redis(self) -> redis.Redis | None:
        if not self._url:
            return None
        if self._client is None:
            self._client = redis.Redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
        return self._client

    def get_json(self, key: str) -> Any | None:
        client = self._redis()
        if client is None:
            return self._get_memory(key)
        try:
            raw = client.get(self._prefix + key)
        except redis.RedisError:
            log.warning("cache indisponível (get)", extra={"key": key})
            return self._get_memory(key)
        if raw:
            value = json.loads(raw)
            self._set_memory(key, value, ttl_seconds=6 * 3600)
            return value
        return self._get_memory(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        client = self._redis()
        self._set_memory(key, value, ttl_seconds)
        if client is not None:
            try:
                client.set(self._prefix + key, json.dumps(value, default=str), ex=ttl_seconds)
            except redis.RedisError:
                log.warning("cache indisponível (set)", extra={"key": key})

    def _get_memory(self, key: str) -> Any | None:
        with self._memory_lock:
            entry = self._memory.get(key)
            if entry is None:
                return None
            expires_at, raw = entry
            if expires_at <= time.monotonic():
                self._memory.pop(key, None)
                return None
        return json.loads(raw)

    def _set_memory(self, key: str, value: Any, ttl_seconds: int) -> None:
        raw = json.dumps(value, default=str)
        with self._memory_lock:
            self._memory[key] = (time.monotonic() + ttl_seconds, raw)
