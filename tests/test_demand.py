"""Подготовка спроса — четыре требования Must have.

Это самая важная часть логики: если очистка истории работает неверно,
весь расчёт заказа неверен, и по итоговой цифре этого не видно.
"""

from datetime import date

import pytest
from tests.conftest import history

from app.domain.demand import (
    compensate_stockouts,
    growth_factor,
    prepare,
    remove_bulk_orders,
    seasonality_factor,
)


def test_bulk_order_is_trimmed_to_expected_level():
    """Разовая крупная продажа срезается до обычного уровня (Must have 4)."""
    values = [30.0] * 24
    values[15] = 1500.0
    cleaned, removed, months = remove_bulk_orders(history(values))

    assert removed == pytest.approx(1470.0)
    assert months == [date(2025, 4, 1)]
    assert cleaned[15].sold == pytest.approx(30.0)


def test_seasonal_peak_is_not_treated_as_bulk():
    """Сезонный пик — не разовая сделка.

    Здесь конфликтуют два требования ТЗ: исключение выбросов и учёт сезонности.
    Если сравнивать со средним по всей истории, декабрьский пик будет срезан,
    и сезонность исчезнет.
    """
    seasonal = [10.0] * 9 + [80.0, 90.0, 80.0]
    cleaned, removed, _ = remove_bulk_orders(history(seasonal * 2))

    assert removed == 0.0
    assert cleaned[10].sold == pytest.approx(90.0)


def test_stockout_months_are_compensated():
    """Месяцы без товара поднимаются до обычного уровня (Must have 3)."""
    sales = [40.0] * 20 + [0.0, 0.0, 40.0, 40.0]
    stocks = [100.0] * 20 + [0.0, 0.0, 100.0, 100.0]
    cleaned, added, count = compensate_stockouts(history(sales, stocks))

    assert count == 2
    assert added == pytest.approx(80.0)
    assert cleaned[20].sold == pytest.approx(40.0)


def test_stockout_with_sales_is_not_lowered():
    """Если в месяц без остатка всё равно продали много, занижать нельзя."""
    sales = [10.0] * 23 + [100.0]
    stocks = [100.0] * 23 + [0.0]
    cleaned, _, _ = compensate_stockouts(history(sales, stocks))

    assert cleaned[23].sold == pytest.approx(100.0)


def test_seasonality_reflects_month_profile():
    """Коэффициент сезонности отражает профиль месяца (Must have 2)."""
    seasonal = [10.0] * 9 + [80.0, 90.0, 80.0]
    points = history(seasonal * 2)

    assert seasonality_factor(points, 11) > 2.0   # ноябрь — пик
    assert seasonality_factor(points, 5) < 0.6    # май — спад


def test_seasonality_needs_two_observations():
    """На одном наблюдении сезонность не строится: это был бы шум."""
    assert seasonality_factor(history([10.0] * 6), 3) == 1.0


def test_growth_factor_detects_trend():
    """Устойчивый рост попадает в коэффициент (Must have 2)."""
    # окно сравнения — 6 месяцев против предыдущих 6, поэтому рост берём свежий
    growing = history([10.0] * 6 + [20.0] * 6)
    flat = history([10.0] * 24)

    assert growth_factor(growing) == pytest.approx(2.0)
    assert growth_factor(flat) == pytest.approx(1.0)


def test_growth_factor_is_capped():
    """Новая позиция не должна давать бесконечный рост."""
    exploding = history([0.0] * 6 + [500.0] * 6)
    assert growth_factor(exploding) <= 2.0


def test_prepare_removes_bulk_before_compensating():
    """Порядок важен: иначе выброс задерёт уровень, по которому считается компенсация."""
    sales = [30.0] * 24
    sales[10] = 900.0     # разовая отгрузка
    sales[20] = 0.0       # месяц без товара
    stocks = [100.0] * 24
    stocks[20] = 0.0

    result = prepare(history(sales, stocks))

    assert result.removed_bulk > 0
    assert result.stockout_months == 1
    # компенсация считается по нормальному уровню (~30), а не по раздутому выбросом
    assert result.compensated < 100
