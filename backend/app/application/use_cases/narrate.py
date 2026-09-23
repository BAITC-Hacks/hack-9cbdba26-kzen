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


def has_unsupported_adjustment_claim(text: str, context: dict[str, Any]) -> bool:
    """Не показывать заявленную моделью поправку, которой нет в расчёте."""
    labels = " ".join(
        str(reason.get("label", "")) for reason in context.get("reasons") or []
    ).lower()
    claim = text.lower()
    one_off_claims = re.finditer(
        r"разов\w*.{0,60}исключ\w*|исключ\w*.{0,60}разов\w*", claim
    )
    if "разов" not in labels and any(
        not _is_negated_adjustment(claim, match, "исключ") for match in one_off_claims
    ):
        return True
    stockout_claims = re.finditer(
        r"восстанов\w*.{0,60}спрос|спрос.{0,60}восстанов\w*|компенсац\w*.{0,60}отсутств",
        claim,
    )
    return "компенсац" not in labels and any(
        not _is_negated_adjustment(claim, match, "восстанов|компенсац")
        for match in stockout_claims
    )


def _is_negated_adjustment(text: str, match: re.Match[str], action: str) -> bool:
    """Отрицание относится к самой поправке, а не к соседнему факту."""
    start = max(text.rfind(mark, 0, match.start()) for mark in (".", ";", ",", "\n")) + 1
    ends = [text.find(mark, match.end()) for mark in (".", ";", ",", "\n")]
    end = min((pos for pos in ends if pos >= 0), default=len(text))
    action_match = re.search(rf"(?:{action})\w*", match.group())
    if action_match is None:
        return False
    action_start = match.start() + action_match.start()
    action_end = match.start() + action_match.end()
    before = text[start:action_start]
    after = text[action_end:end]
    # «не были исключены» и «спрос не восстановлен» не заявляют поправку.
    if re.search(r"\b(?:не|нет|без)\s+(?:\w+\s+){0,2}$", before):
        return True
    # Существительное с явным отрицанием: «исключение ... не проводилось».
    return bool(re.search(
        r"\bне\s+(?:был\w*|проводил\w*|выполнял\w*|применял\w*|"
        r"производил\w*|учитывал\w*)\b", after,
    ))


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
        «llm:<модель>», «template» или «template (числа LLM не сошлись)»."""
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
        elif text and has_unsupported_adjustment_claim(text, context):
            logger.warning("LLM заявила поправку, которой нет в расчёте; текст отброшен",
                           extra={"code": line.code})
            text, source = None, "template (LLM добавила неподтверждённую поправку)"
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
