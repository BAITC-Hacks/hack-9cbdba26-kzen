"""Кэш в памяти процесса.

Дефолтная реализация: при одном воркере она быстрее Redis, потому что нет
ни сети, ни сериализации. Redis нужен, только когда воркеров несколько
и кэш должен быть общим.
"""

from __future__ import annotations

import time
from typing import Any


class MemoryCache:
    def __init__(self, max_items: int = 50_000) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}
        self._max_items = max_items

    @property
    def backend(self) -> str:
        return "memory"

    async def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and expires_at < time.monotonic():
            self._data.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if len(self._data) >= self._max_items:
            # Простейшее вытеснение: на хакатоне сложная политика не окупается.
            self._data.pop(next(iter(self._data)), None)
        expires_at = time.monotonic() + ttl if ttl else None
        self._data[key] = (value, expires_at)

    async def clear(self) -> None:
        self._data.clear()
