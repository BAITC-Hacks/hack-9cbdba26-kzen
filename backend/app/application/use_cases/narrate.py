"""Сценарий: объяснить строку заказа словами.

Отдельный use case и отдельная ручка: формулировка стоит сотни миллисекунд
против миллисекунд у расчёта, поэтому она не должна стоять на пути основного
ответа. Менеджер сразу видит таблицу и карточку, текст подтягивается следом.

Числа в текст приходят из расчёта. LLM их только формулирует и не может
изменить: это требование объяснимости из пункта 9 ТЗ. Гарантия здесь не на
честном слове промпта: после ответа проверяется, что каждое число в тексте
есть во входных фактах. Если модель добавила своё — текст отбрасывается,
и менеджер видит шаблон, собранный из компонентов расчёта.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.domain.ports import CachePort, NarratorPort
from app.domain.workflow import DraftLine

logger = logging.getLogger(__name__)

# Число с дробной частью через точку или запятую («6.5», «6,5», «400»)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_in(text: str) -> set[float]:
    """Все числа из текста в виде float: «6,5» и «6.5» — одно и то же число."""
    return {float(m.replace(",", ".")) for m in _NUMBER.findall(text)}


def is_grounded(text: str, context: dict[str, Any]) -> bool:
    """Правда ли, что каждое число в тексте LLM встречается во входных фактах.

    Факты сравниваются как числа, а не как строки, поэтому «120 шт» и «120,0»
    совпадают. Ноль разрешён всегда: «в пути 0» модель пишет и без подсказки.
    """
    allowed = numbers_in(_flatten(context)) | {0.0}
    return numbers_in(text) <= allowed


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, list | tuple):
        return " ".join(_flatten(v) for v in value)
    return str(value)


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

    async def execute(self, line: DraftLine) -> tuple[str, str]:
        """Вернуть (текст, источник). Источник нужен интерфейсу и защите:
        «nvidia», «template» или «template (числа LLM не сошлись)»."""
        key = f"narrative:{self._narrator.backend}:{line.code}:{line.quantity}"
        cached = await self._cache.get(key)
        if cached is not None:
            return cached

        context = build_context(line)
        # Сетевой вызов синхронный (httpx.Client); в отдельном потоке он не блокирует
        # event loop, и таблица с карточкой отвечают, пока LLM думает
        text = await asyncio.to_thread(self._narrator.narrate, context)
        source = self._narrator.backend

        if text and not is_grounded(text, context):
            logger.warning("LLM добавила числа, которых нет в расчёте; текст отброшен",
                           extra={"code": line.code})
            text, source = None, "template (LLM добавила числа, текст отброшен)"
        elif not text:
            source = "template (LLM недоступна)"

        if not text and self._fallback is not None:
            text = self._fallback.narrate(context)

        # Шаблон из компонентов расчёта — последний рубеж: числа в нём только из расчёта
        result = (text or line.explanation, source)
        await self._cache.set(key, result, ttl=self._ttl)
        return result


def build_context(line: DraftLine) -> dict[str, Any]:
    """Факты для нарратора из сохранённой строки версии.

    Берётся строка версии, а не свежий пересчёт: текст должен описывать то
    количество, которое менеджер видит и утверждает.
    """
    return {
        "code": line.code,
        "name": line.name,
        "supplier": line.supplier,
        "quantity": line.quantity,
        "unit": line.unit,
        "urgency": line.urgency,
        "monthly_demand": line.monthly_demand,
        "coverage_months": line.coverage_months,
        "reasons": [{"label": label, "value": value} for label, value in line.reasons],
    }
