"""Самопроверка по требованиям ТЗ.

Пункт 7 задания сформулирован как набор проверок — реализуем их буквально
и показываем результат жюри прямо в интерфейсе. Проверки идут на синтетических
артикулах, поэтому не зависят от того, какие данные загружены, и всегда
воспроизводимы на защите.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from app.application.use_cases.replenishment import CalcParams, CalculateOrders
from app.domain.entities import MonthPoint, Sku


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    name: str
    passed: bool
    detail: str


def _history(values: list[float], stocks: list[float] | None = None) -> tuple[MonthPoint, ...]:
    """Собрать историю помесячно, начиная с января 2024."""
    stocks = stocks or [100.0] * len(values)
    points = []
    for i, (sold, stock) in enumerate(zip(values, stocks, strict=True)):
        year = 2024 + i // 12
        month = i % 12 + 1
        points.append(MonthPoint(month=date(year, month, 1), sold=sold, stock_start=stock))
    return tuple(points)


def _sku(history, **kwargs) -> Sku:
    defaults = dict(
        code="TEST", name="Тестовый артикул", supplier="Тест", moq=1,
        free_stock=0.0, in_transit=0.0, history=history,
    )
    defaults.update(kwargs)
    return Sku(**defaults)  # type: ignore[arg-type]


class RunSelfChecks:
    """Пять проверок из ТЗ. Каждая сравнивает результат «до» и «после»."""

    def __init__(self, calculator: CalculateOrders) -> None:
        self._calc = calculator
        self._params = CalcParams(lead_time_days=45, today=date(2026, 9, 1))

    def execute(self) -> list[CheckOutcome]:
        return [
            self._check_in_transit(),
            self._check_seasonality(),
            self._check_stockout(),
            self._check_bulk_order(),
            self._check_reasons(),
        ]

    def _qty(self, sku: Sku) -> int:
        return self._calc.calculate_line(sku, self._params).quantity

    def _check_in_transit(self) -> CheckOutcome:
        """Товар в пути обязан уменьшать заказ (Must have 1)."""
        base = _sku(_history([50.0] * 24))
        with_transit = replace(base, in_transit=300.0)

        before, after = self._qty(base), self._qty(with_transit)
        return CheckOutcome(
            "Товар в пути влияет на результат",
            after < before,
            f"без товара в пути {before} шт, с 300 шт в пути — {after} шт",
        )

    def _check_seasonality(self) -> CheckOutcome:
        """Сезонный товар должен давать сезонный профиль, а не среднее (Must have 2)."""
        seasonal = [10.0] * 9 + [80.0, 90.0, 80.0]  # пик в конце года
        history = _history(seasonal * 2)

        # Срок поставки задаём на артикуле: он определяет месяц прихода,
        # а значит и то, какой сезонный коэффициент применяется.
        to_november = _sku(history, lead_time_days=70)   # приход ~10 ноября
        to_may = _sku(history, lead_time_days=250)       # приход ~май

        november = self._calc.calculate_line(to_november, self._params)
        may = self._calc.calculate_line(to_may, self._params)
        passed = november.monthly_demand > may.monthly_demand * 1.5
        return CheckOutcome(
            "Учитывается сезонность",
            passed,
            f"прогноз на ноябрь (пик) {november.monthly_demand:.0f} шт/мес, "
            f"на май (спад) {may.monthly_demand:.0f} шт/мес",
        )

    def _check_stockout(self) -> CheckOutcome:
        """При провалах наличия потребность должна расти (Must have 3)."""
        sales = [40.0] * 20 + [0.0, 0.0, 40.0, 40.0]
        stocks_ok = [100.0] * 24
        stocks_out = [100.0] * 20 + [0.0, 0.0, 100.0, 100.0]

        raw = _sku(_history(sales, stocks_ok))
        with_stockout = _sku(_history(sales, stocks_out))

        before, after = self._qty(raw), self._qty(with_stockout)
        return CheckOutcome(
            "Компенсируется упущенный спрос",
            after > before,
            f"по сырым продажам {before} шт, с учётом 2 месяцев отсутствия — {after} шт",
        )

    def _check_bulk_order(self) -> CheckOutcome:
        """Разовый крупный заказ не должен раздувать регулярную потребность (Must have 4)."""
        regular = [30.0] * 24
        with_bulk = regular.copy()
        with_bulk[15] = 1500.0  # одна крупная отгрузка одному клиенту

        before = self._qty(_sku(_history(regular)))
        after = self._qty(_sku(_history(with_bulk)))
        growth = (after - before) / before if before else 0
        return CheckOutcome(
            "Разовые крупные заказы исключаются",
            growth < 0.25,
            f"без выброса {before} шт, с выбросом 1500 шт — {after} шт (рост {growth:.0%})",
        )

    def _check_reasons(self) -> CheckOutcome:
        """Каждая строка должна иметь обоснование (Must have 5)."""
        line = self._calc.calculate_line(_sku(_history([25.0] * 24)), self._params)
        return CheckOutcome(
            "Каждая позиция имеет обоснование",
            len(line.reasons) >= 3 and bool(line.explain()),
            f"{len(line.reasons)} компонентов: {line.explain()[:110]}…",
        )
