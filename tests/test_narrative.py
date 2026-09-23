"""Обоснование словами: LLM формулирует, но не может добавить ни одного числа."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.application.use_cases.narrate import (
    NarrateOrderLine, has_unsupported_adjustment_claim, is_grounded,
)
from app.core.container import Container
from app.domain.workflow import DraftLine
from app.infrastructure.cache.memory import MemoryCache
from app.infrastructure.forecasting.baseline import BaselineForecaster
from app.infrastructure.forecasting.smoothed import SmoothedForecaster
from app.infrastructure.llm.openai_compat import build_prompt
from app.infrastructure.llm.template import TemplateNarrator
from app.infrastructure.storage.demo_data import build_demo_repository
from app.main import create_app

B = "/api/v1"

CONTEXT: dict[str, Any] = {
    "code": "081100392_", "name": "LED Лампа T8 18w 230v 4000K G13", "supplier": "IEK",
    "quantity": 5, "unit": "шт", "urgency": "high", "monthly_demand": 6.5,
    "coverage_months": 1.2,
    "reasons": [{"label": "исключена разовая накладная", "value": "400 шт"},
                {"label": "сезонность октября", "value": "+18%"}],
}


class FakeNarrator:
    """LLM, которая отвечает заранее заданным текстом (или молчит)."""

    def __init__(self, text: str | None) -> None:
        self.text = text
        self.calls = 0

    @property
    def backend(self) -> str:
        return "fake-llm"

    def narrate(self, context: dict[str, Any]) -> str | None:
        self.calls += 1
        return self.text


def _client(settings, narrator):
    container = Container(
        settings=settings, repo=build_demo_repository(), cache=MemoryCache(),
        forecasters={"baseline": BaselineForecaster(), "smoothed": SmoothedForecaster()},
        narrator=narrator,
    )
    return TestClient(create_app(settings, container=container))


def _first_sku(ui) -> str:
    ui.post(f"{B}/calculations")
    return ui.post(f"{B}/recommendations/search", json={}).json()["groups"][0]["rows"][0][
        "sku_id"]


def test_prompt_is_about_procurement_not_scoring():
    prompt = build_prompt(CONTEXT)
    assert "Рекомендовано заказать: 5 шт" in prompt
    assert "6.5 шт в месяц" in prompt
    assert "исключена разовая накладная: 400 шт" in prompt
    # Промпт каркаса был про скоринг оттока; в кейсе закупок таких слов быть не должно
    assert "риск" not in prompt.lower()


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("Заказать 5 шт: спрос 6,5 шт в месяц, накладная на 400 шт исключена.", True),
        ("Запаса хватит на 1.2 мес, сезонность +18%.", True),
        ("Заказать 50 шт, спрос вырос до 12 шт в месяц.", False),  # чисел нет в расчёте
        ("Позиция T8 18w 230v: заказать 5 шт.", True),  # числа из названия — тоже факты
    ],
)
def test_numbers_must_come_from_calculation(text, ok):
    assert is_grounded(text, CONTEXT) is ok


def test_narrative_rejects_adjustments_missing_from_calculation():
    context = {**CONTEXT, "reasons": []}
    assert has_unsupported_adjustment_claim("Разовая продажа исключена.", context)
    assert has_unsupported_adjustment_claim("Спрос восстановлен за месяцы без товара.", context)
    assert not has_unsupported_adjustment_claim("Свободный остаток исчерпан.", context)
    assert not has_unsupported_adjustment_claim("Разовая продажа исключена.", CONTEXT)
    compensated = {**context, "reasons": [{"label": "Компенсация отсутствия товара"}]}
    assert not has_unsupported_adjustment_claim(
        "Спрос восстановлен за месяцы без товара.", compensated
    )


def test_template_narrator_uses_russian_decimal_separator():
    text = TemplateNarrator().narrate({**CONTEXT, "monthly_demand": 0.01})
    assert "0,01 шт/мес" in text
    assert "0.01" not in text


def test_narrative_falls_back_when_llm_invents_adjustment():
    line = DraftLine(
        code="test", name="Позиция", supplier="IEK", article="", moq=1,
        urgency="normal", recommended=1, quantity=1, explanation="Факт расчёта",
        monthly_demand=0.01, reasons=(("Средние продажи", "0,03 шт/мес"),),
    )
    narrator = NarrateOrderLine(
        FakeNarrator("Разовая продажа исключена."), MemoryCache(),
        fallback=TemplateNarrator(),
    )
    text, source = asyncio.run(narrator.execute(line))
    assert "Разовая продажа исключена" not in text
    assert source.startswith("template")


def test_narrative_returns_llm_text_when_grounded(settings):
    # Текст без чисел проходит проверку при любом расчёте
    text = "Остатка мало, заказать в этом цикле."
    narrator = FakeNarrator(text)
    with _client(settings, narrator) as ui:
        sku_id = _first_sku(ui)
        body = ui.get(f"{B}/skus/{sku_id}/narrative").json()
        assert body == {"text": text, "source": "fake-llm"}
        # второй показ той же позиции — из кэша, LLM не дёргается
        ui.get(f"{B}/skus/{sku_id}/narrative")
        assert narrator.calls == 1


def test_narrative_falls_back_when_llm_invents_numbers(settings):
    with _client(settings, FakeNarrator("Заказать 99999 шт, спрос 777 в месяц.")) as ui:
        sku_id = _first_sku(ui)
        body = ui.get(f"{B}/skus/{sku_id}/narrative").json()
        explanation = ui.get(f"{B}/skus/{sku_id}/explanation").json()["explanation_text"]
    assert body["text"] == explanation
    assert body["source"].startswith("template")


def test_narrative_falls_back_when_llm_is_down(settings):
    with _client(settings, FakeNarrator(None)) as ui:
        sku_id = _first_sku(ui)
        body = ui.get(f"{B}/skus/{sku_id}/narrative").json()
    assert body["source"] == "template (LLM недоступна)"
    assert body["text"]


def test_narrative_without_narrator_is_plain_explanation(settings):
    with _client(settings, None) as ui:
        sku_id = _first_sku(ui)
        body = ui.get(f"{B}/skus/{sku_id}/narrative").json()
    assert body["source"] == "none"
    assert body["text"]
