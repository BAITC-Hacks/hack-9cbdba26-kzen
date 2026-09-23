"""Версии расчёта в памяти.

Эндпоинты объявлены через `def`, значит FastAPI выполняет их в пуле потоков,
и две правки одного черновика могут прийти одновременно. Без блокировки
вторая перезапишет первую: оба потока прочитали ревизию 5, оба записали 6,
одна правка потеряна. Поэтому чтение-изменение-запись идёт под одним замком.

Чтение замка не требует: черновик неизменяемый, а подмена ссылки в словаре
атомарна, так что читатель получает либо старую версию, либо новую целиком.

Память, а не база: на демо один процесс и десятки версий. При перезапуске
версии пропадают — это осознанная цена, для прода нужна таблица в Postgres.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from app.domain.exceptions import NotFoundError
from app.domain.workflow import OrderDraft


class MemoryDraftStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._drafts: dict[int, OrderDraft] = {}
        self._next_version = 1

    def create(self, build: Callable[[int], OrderDraft]) -> OrderDraft:
        """Номер версии выдаётся под замком, иначе два параллельных расчёта
        получат одинаковый номер и один затрёт другой."""
        with self._lock:
            draft = build(self._next_version)
            self._drafts[draft.version] = draft
            self._next_version += 1
            return draft

    def get(self, version: int) -> OrderDraft:
        draft = self._drafts.get(version)
        if draft is None:
            raise NotFoundError(
                f"Версия расчёта {version} не найдена", details={"version": version}
            )
        return draft

    def list(self) -> list[OrderDraft]:
        return sorted(self._drafts.values(), key=lambda d: d.version, reverse=True)

    def clear(self) -> None:
        """Нумерация версий тоже с начала: после сброса это новая сессия."""
        with self._lock:
            self._drafts.clear()
            self._next_version = 1

    def update(self, version: int, change: Callable[[OrderDraft], OrderDraft]) -> OrderDraft:
        with self._lock:
            updated = change(self.get(version))
            self._drafts[version] = updated
            return updated
