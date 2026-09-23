"""Проверки расчётного ядра без HTTP."""

from dataclasses import replace
from datetime import date

from tests.conftest import history

from app.application.use_cases.replenishment import CalcParams, CalculateOrders
from app.domain.entities import Sku
from app.infrastructure.forecasting.baseline import BaselineForecaster
from app.infrastructure.storage.memory_repo import MemorySkuRepository


def test_systeme_category_changes_safety_stock_and_quantity():
    """Категория — вход расчёта, а не только фильтр списка (Must have 1)."""
    base = Sku(
        code="SE-1",
        name="Тест",
        supplier="Systeme Electric",
        category="3",
        history=history([100.0] * 24),
    )
    calculator = CalculateOrders(MemorySkuRepository(), BaselineForecaster())
    params = CalcParams(
        lead_time_days=30,
        coverage_months=1,
        safety_factor=0,
        today=date(2026, 9, 1),
    )

    category_1 = calculator.calculate_line(replace(base, category="1"), params)
    category_2 = calculator.calculate_line(replace(base, category="2"), params)
    category_3 = calculator.calculate_line(base, params)

    assert category_1.quantity > category_2.quantity > category_3.quantity
    assert any(reason.label == "Категория" for reason in category_1.reasons)
