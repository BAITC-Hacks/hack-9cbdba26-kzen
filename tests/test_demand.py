"""Подготовка спроса — четыре требования Must have.

Это самая важная часть логики: если очистка истории работает неверно,
весь расчёт заказа неверен, и по итоговой цифре этого не видно.
"""

from datetime import date

import pytest
from tests.conftest import history

from app.domain.assessment import assess
from app.domain.demand import (
    compensate_stockouts,
    growth_factor,
    prepare,
    remove_bulk_orders,
    seasonality_factor,
)
from app.domain.entities import BulkOrderEvent, MonthPoint, OrderLine, Sku, Urgency


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


@pytest.mark.parametrize(
    ("sales", "stocks", "expected"),
    [
        (
            [1.0] * 8 + [0.0] * 25,
            [100.0] * 8 + [0.0] * 25,
            "В 25 из 33 мес начальный остаток нулевой или не указан; "
            "спрос восстановлен оценкой в 25 мес",
        ),
        (
            [1.0] * 7 + [0.0] * 25 + [1.0],
            [100.0] * 7 + [0.0] * 26,
            "В 26 из 33 мес начальный остаток нулевой или не указан; "
            "спрос восстановлен оценкой в 25 мес",
        ),
    ],
)
def test_stockout_warning_distinguishes_zero_stock_from_compensation(sales, stocks, expected):
    points = history(sales, stocks)
    sku = Sku(code="010300239_", name="Тест", supplier="IEK", history=points)
    cleaned = prepare(points)
    line = OrderLine(
        sku=sku, quantity=0, urgency=Urgency.NONE,
        monthly_demand=1.0, coverage_months=0.0,
    )

    issue = next(item for item in assess(sku, line, cleaned).issues
                 if item.code == "frequent_stockout")

    assert issue.message == expected


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


def test_confirmed_invoice_bulk_is_removed_from_its_month():
    """Номер накладной подтверждает клиентский сценарий, а не заменяет историю."""
    values = [30.0] * 24
    values[15] = 1030.0
    event = BulkOrderEvent(
        month=date(2025, 4, 1),
        invoice="CLIENT-42",
        quantity=1000.0,
        regular_quantity=30.0,
    )

    result = prepare(history(values), (event,))

    assert result.removed_bulk >= 970.0
    assert result.bulk_invoices == ("CLIENT-42",)
    assert result.points[15].sold <= 60.0


def test_missing_stock_history_is_not_a_confirmed_stockout():
    """Отсутствующая строка остатков не даёт права придумывать упущенный спрос."""
    points = tuple(
        MonthPoint(date(2024, month, 1), sold=0.0, stock_start=0.0, stock_known=False)
        for month in range(1, 7)
    )

    _, added, count = compensate_stockouts(points)

    assert added == 0.0
    assert count == 0
