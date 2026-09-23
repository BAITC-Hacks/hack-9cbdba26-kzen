"""Расчётное ядро вызывается напрямую, без FastAPI и хранилища."""

from dataclasses import replace
from datetime import date

import pytest
from tests.conftest import history

from app.application.use_cases.replenishment import (
    CalcParams,
    CalculateOrders,
    calculate_recommendations,
)
from app.domain.entities import Sku
from app.domain.exceptions import DomainValidationError
from app.infrastructure.forecasting.baseline import BaselineForecaster
from app.infrastructure.storage.memory_repo import MemorySkuRepository


def test_normalized_skus_are_calculated_without_http():
    sku = Sku(
        code="SKU-1",
        name="Тест",
        supplier="IEK",
        unit="шт",
        moq=12,
        on_hand_stock=40,
        reserved_stock=10,
        free_stock=30,
        in_transit=12,
        history=history([30.0] * 24),
    )

    orders = calculate_recommendations(
        [sku],
        BaselineForecaster(),
        CalcParams(lead_time_days=30, coverage_months=1, safety_factor=0, today=date(2026, 9, 1)),
    )

    line = orders[0].lines[0]
    assert line.quantity == 24
    labels = {reason.label for reason in line.reasons}
    assert {"Остаток на складе", "Зарезервировано", "Свободный остаток", "Товар в пути"} <= labels
def test_invalid_direct_parameters_are_rejected():
    with pytest.raises(DomainValidationError):
        CalcParams(lead_time_days=0)
    with pytest.raises(DomainValidationError):
        CalcParams(coverage_months=13)
    with pytest.raises(DomainValidationError):
        CalcParams(safety_factor=1.1)


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
