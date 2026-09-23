"""Кэш в Redis.

Объекты складываем через pickle, потому что кэшируем доменные сущности целиком.
Так делать можно только со своими данными — в Redis пишем только мы.
"""

from __future__ import annotations

import logging
import pickle
from typing import Any

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, url: str, prefix: str = "app") -> None:
        from redis.asyncio import from_url

        self._client = from_url(url, encoding=None, decode_responses=False)
        self._prefix = prefix

    @property
    def backend(self) -> str:
        return "redis"

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(self._key(key))
        if raw is None:
            return None
        try:
            return pickle.loads(raw)
        except Exception as exc:
            logger.warning("Не удалось прочитать кэш %s: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        payload = pickle.dumps(value)
        await self._client.set(self._key(key), payload, ex=ttl)

    async def clear(self) -> None:
        async for k in self._client.scan_iter(f"{self._prefix}:*"):
            await self._client.delete(k)

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"
