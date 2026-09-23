"""Порты: что ядру нужно от внешнего мира.

Protocol, а не ABC: реализации не наследуются, достаточно совпадения сигнатур.
Это позволяет подменять их в тестах без импорта домена в тестовый код.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.domain.entities import Forecast, Sku


@runtime_checkable
class ForecasterPort(Protocol):
    """Прогноз спроса по артикулу.

    Две реализации: baseline повторяет текущую формулу партнёра (среднее за
    12 месяцев × рост × сезонность), сглаживание даёт более точную оценку.
    Разница между ними — то, что показывается жюри как измеримое улучшение.
    """

    @property
    def method(self) -> str: ...

    def forecast(self, sku: Sku, target_month: int) -> Forecast: ...


@runtime_checkable
class SkuRepositoryPort(Protocol):
    """Доступ к номенклатуре: история, остатки, товар в пути, кратность."""

    def get(self, code: str) -> Sku | None: ...

    def list_skus(self, supplier: str | None = None, category: str | None = None) -> list[Sku]: ...

    def suppliers(self) -> list[str]: ...

    def stats(self) -> dict[str, Any]: ...


@runtime_checkable
class CachePort(Protocol):
    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    async def clear(self) -> None: ...


@runtime_checkable
class NarratorPort(Protocol):
    """Превращает расчёт в текст для человека.

    Отдельный порт: формулировка стоит сотни миллисекунд против единиц
    у расчёта и обязана быть необязательной. Числа приходят из расчёта,
    LLM только формулирует.
    """

    @property
    def backend(self) -> str: ...

    def narrate(self, context: dict[str, Any]) -> str | None: ...
