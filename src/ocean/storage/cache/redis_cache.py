"""Cache em Redis com prefixo próprio (`mcp:`) para não colidir com o rate limit da API.

Falha de forma silenciosa: sem Redis, o cache simplesmente não existe e a fonte é consultada.
"""

import json
import logging
from typing import Any

import redis

from ocean.shared.config import get_settings

log = logging.getLogger(__name__)


class Cache:
    def __init__(self, url: str | None = None, prefix: str = "mcp:") -> None:
        self._url = url or get_settings().redis_url
        self._prefix = prefix
        self._client: redis.Redis | None = None

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
            return None
        try:
            raw = client.get(self._prefix + key)
        except redis.RedisError:
            log.warning("cache indisponível (get)", extra={"key": key})
            return None
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            client.set(self._prefix + key, json.dumps(value, default=str), ex=ttl_seconds)
        except redis.RedisError:
            log.warning("cache indisponível (set)", extra={"key": key})
