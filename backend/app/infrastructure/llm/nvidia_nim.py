"""Адаптер NVIDIA NIM (build.nvidia.com).

API совместим с OpenAI Chat Completions, поэтому отдельный SDK не нужен —
хватает httpx. Базовый адрес https://integrate.api.nvidia.com/v1, ключ вида
nvapi-... передаётся в заголовке Authorization.

Где это уместно в проекте. LLM здесь не принимает решение — решение принимает
ваша табличная модель за единицы миллисекунд. LLM только переводит готовый
результат на человеческий язык: «почему клиент в зоне риска и что с этим делать».
Такое разделение даёт и скорость, и объяснимость, и его легко защищать перед жюри:
цифра приходит от модели, обученной на данных кейса, а не выдумывается языковой моделью.

Что критично для демо:
  * вызов идёт ОТДЕЛЬНОЙ ручкой, а не внутри /predict — иначе бюджет ответа
    вырастает с 10 мс до сотен;
  * жёсткий таймаут: недоступный интернет на площадке не должен вешать сервис;
  * кэш по ключу оценки: на защите один и тот же объект показывают много раз;
  * при любой ошибке возвращается None, и сервис отдаёт шаблонное объяснение.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты помогаешь аналитику разобраться в решении скоринговой модели.
Тебе дают: оценку риска, группу решения и факторы влияния с их вкладом
(положительный вклад повышает риск, отрицательный понижает).

Правила:
- опирайся только на переданные факты, ничего не придумывай и не добавляй цифр;
- 2-3 предложения, деловой тон, без маркированных списков;
- назови главную причину и одно конкретное действие;
- не упоминай слова «модель», «SHAP», «признак» — пиши на языке бизнеса."""


class NvidiaNarrator:
    """Объяснение оценки текстом через NVIDIA NIM."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        model: str = "meta/llama-3.3-70b-instruct",
        timeout: float = 8.0,
        max_tokens: int = 220,
        temperature: float = 0.2,
    ) -> None:
        if not api_key:
            raise ValueError("Нужен ключ NVIDIA (nvapi-...). Возьмите его на build.nvidia.com")

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
        return f"nvidia:{self._model}"

    def narrate(self, context: dict[str, Any]) -> str | None:
        """Вернуть текст объяснения или None, если сервис недоступен.

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
                        {"role": "user", "content": _build_prompt(context)},
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
            logger.warning("NVIDIA NIM недоступен: %s", exc)
            return None

    def close(self) -> None:
        self._client.close()


def _build_prompt(context: dict[str, Any]) -> str:
    """Факты для модели.

    Всё числовое уже посчитано вашей моделью: LLM получает готовые значения
    и только формулирует. Так исключается ситуация, когда языковая модель
    придумывает собственную оценку риска.
    """
    factors = context.get("factors") or []
    lines = [
        f"Объект: {context.get('subject_id', 'без идентификатора')}",
        f"Оценка риска: {context.get('score_pct', 0)}%",
        f"Группа решения: {context.get('band', 'unknown')}",
        "Факторы влияния:",
    ]
    for factor in factors:
        direction = "повышает" if factor.get("impact", 0) > 0 else "понижает"
        lines.append(
            f"  - {factor.get('feature')} = {factor.get('value')} "
            f"({direction} риск, вклад {abs(float(factor.get('impact', 0))):.3f})"
        )
    if domain := context.get("domain"):
        lines.append(f"Предметная область: {domain}")
    return "\n".join(lines)
