"""Сценарий: объяснить расчёт словами.

Отдельный use case и отдельная ручка: формулировка стоит сотни миллисекунд
против миллисекунд у расчёта, поэтому она не должна стоять на пути основного
ответа. Менеджер сразу видит таблицу, а текст подтягивается следом.

Числа в текст приходят из расчёта. LLM их только формулирует и не может
изменить: это требование объяснимости из пункта 9 ТЗ.
"""

from __future__ import annotations

from app.domain.entities import OrderLine
from app.domain.ports import CachePort, NarratorPort


class NarrateOrderLine:
    def __init__(
        self,
        narrator: NarratorPort,
        cache: CachePort,
        *,
        fallback: NarratorPort | None = None,
        ttl: int = 3600,
    ) -> None:
        self._narrator = narrator
        self._fallback = fallback
        self._cache = cache
        self._ttl = ttl

    async def execute(self, line: OrderLine) -> tuple[str, str]:
        key = f"narrative:{self._narrator.backend}:{line.sku.code}:{line.quantity}"
        cached = await self._cache.get(key)
        if cached is not None:
            return cached

        context = {
            "code": line.sku.code,
            "name": line.sku.name,
            "supplier": line.sku.supplier,
            "quantity": line.quantity,
            "urgency": line.urgency.value,
            "monthly_demand": line.monthly_demand,
            "coverage_months": line.coverage_months,
            "reasons": [{"label": r.label, "value": r.value} for r in line.reasons],
        }

        text = self._narrator.narrate(context)
        source = self._narrator.backend

        if not text and self._fallback is not None:
            text = self._fallback.narrate(context)
            source = f"{self._fallback.backend} (fallback)"

        result = (text or line.explain(), source)
        await self._cache.set(key, result, ttl=self._ttl)
        return result
