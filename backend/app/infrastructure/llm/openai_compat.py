"""Адаптер к любому провайдеру с протоколом OpenAI Chat Completions.

Провайдер задаётся адресом и моделью в .env: сейчас это OpenAI
(https://api.openai.com/v1, gpt-4o-mini), тот же код работает с NIM, Groq и
локальной моделью (Ollama, vLLM) внутри контура партнёра. Отдельный SDK не
нужен — хватает httpx, ключ передаётся в заголовке Authorization.

Где это уместно в проекте. LLM здесь не принимает решение и не считает:
количество считает расчётное ядро за миллисекунды. LLM только переводит
готовые компоненты обоснования на язык менеджера. Такое разделение даёт
и скорость, и объяснимость (п. 9 ТЗ): каждое число в тексте приходит из расчёта,
а use case дополнительно проверяет, что модель не добавила своих.

Что критично для демо:
  * вызов идёт ОТДЕЛЬНОЙ ручкой, а не внутри карточки позиции — иначе
    4 мс превращаются в сотни;
  * жёсткий таймаут: недоступный интернет на площадке не должен вешать сервис;
  * кэш по коду и количеству: на защите одну позицию показывают много раз;
  * при любой ошибке возвращается None, и сервис отдаёт шаблонное объяснение.

В облако уходят только код артикула, название, поставщик и компоненты расчёта.
Ни клиентов, ни накладных, ни цен — данные партнёра остаются на нашем сервере.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты помогаешь менеджеру отдела закупа понять, почему сервис
рекомендует заказать у поставщика именно такое количество товара.
Тебе дают: позицию, рекомендованное количество, срочность и компоненты расчёта
(регулярный спрос, сезонность, рост, компенсация отсутствия товара, исключённые
разовые продажи, свободный остаток, товар в пути, кратность отгрузки).

Правила:
- опирайся только на переданные факты; не добавляй ни одного числа, которого нет
  во входных данных, и не пересчитывай их;
- 2-3 предложения, деловой тон, без маркированных списков и заголовков;
- начни с итога (сколько заказать и почему сейчас), затем назови главный фактор;
- если разовая продажа исключена или спрос восстановлен за месяцы без товара —
  скажи об этом явно, это важно для проверки менеджером;
- не упоминай слова «модель», «алгоритм», «LLM» — пиши на языке закупок."""

URGENCY_TEXT = {
    "critical": "критическая: товара нет или не хватит до поставки",
    "high": "высокая: запаса хватит впритык",
    "normal": "плановое пополнение",
    "none": "заказ не требуется",
}


class OpenAINarrator:
    """Обоснование строки заказа текстом через внешнюю модель (протокол OpenAI)."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 8.0,
        max_tokens: int = 260,
        temperature: float = 0.2,
    ) -> None:
        if not api_key:
            raise ValueError("Нужен ключ провайдера LLM в OPENAI_API_KEY (OpenAI: sk-...)")

        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    @property
    def backend(self) -> str:
        # Подпись источника видит менеджер в карточке: имя модели важнее имени
        # провайдера, тем более что по этому адаптеру ходят и OpenAI, и NIM, и Ollama
        return f"llm:{self._model}"

    def narrate(self, context: dict[str, Any]) -> str | None:
        """Вернуть текст обоснования или None, если сервис недоступен.

        None вместо исключения — сознательное решение: вызывающий код
        подставит шаблонное объяснение, и пользователь вообще не заметит сбоя.
        """
        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_prompt(context)},
                    ],
                    "temperature": self._temperature,
                    "max_tokens": self._max_tokens,
                    "stream": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return payload["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            logger.warning("LLM недоступна: %s", exc)
            return None

    def close(self) -> None:
        self._client.close()


def build_prompt(context: dict[str, Any]) -> str:
    """Факты для модели — ровно те, что посчитало ядро.

    Публичная функция, а не приватная: её проверяет тест, что в промпт
    попадают компоненты расчёта и не попадает ничего лишнего.
    """
    unit = context.get("unit") or "шт"
    urgency = URGENCY_TEXT.get(str(context.get("urgency")), "не определена")
    lines = [
        f"Позиция: {context.get('name', 'без названия')} (код {context.get('code', '—')})",
        f"Поставщик: {context.get('supplier', '—')}",
        f"Рекомендовано заказать: {context.get('quantity', 0)} {unit}",
        f"Срочность: {urgency}",
    ]
    demand = context.get("monthly_demand")
    if demand:
        # Это спрос месяца поставки с сезонностью и ростом, а не среднее по истории:
        # среднее приходит отдельно в компонентах расчёта
        lines.append(f"Прогноз спроса на месяц поставки: {demand} {unit} в месяц")
    coverage = context.get("coverage_months")
    if coverage is not None:
        lines.append(f"Текущего запаса хватит на: {coverage} мес.")
    reasons = context.get("reasons") or []
    if reasons:
        lines.append("Компоненты расчёта:")
        lines.extend(f"  - {r.get('label')}: {r.get('value')}" for r in reasons)
    return "\n".join(lines)
