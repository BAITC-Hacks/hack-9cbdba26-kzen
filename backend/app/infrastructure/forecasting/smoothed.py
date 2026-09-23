"""Экспоненциальное сглаживание — улучшенный прогноз.

Отличие от baseline: свежие месяцы весят больше старых. Для дистрибьютора это
важно, потому что ассортимент живой — позиция могла вырасти или начать уходить,
а простое среднее за 12 месяцев узнаёт об этом с полугодовым опозданием.

Для редких позиций (продажи реже чем в половине месяцев) отдельная ветка:
там среднее по всем месяцам занижает потребность, потому что нули между
продажами — это не спрос, это интервалы. Считаем средний размер продажи
и частоту отдельно, как в методе Кростона.

Обучения здесь нет: всё считается за микросекунды по 36 числам.
"""

from __future__ import annotations

import statistics

from app.domain.demand import growth_factor, seasonality_factor
from app.domain.entities import Forecast, Sku


class SmoothedForecaster:
    """Экспоненциальное сглаживание плюс отдельная ветка для редких продаж."""

    def __init__(self, alpha: float = 0.3) -> None:
        # alpha=0.3 — компромисс: реагирует на изменения, но не дёргается от шума
        self._alpha = alpha

    @property
    def method(self) -> str:
        return "smoothed"

    def forecast(self, sku: Sku, target_month: int) -> Forecast:
        points = sku.history
        if not points:
            return Forecast(0.0, 0.0, method=self.method)

        sold = [p.sold for p in points]
        base = self._intermittent(sold) if self._is_rare(sold) else self._smooth(sold)
        growth = growth_factor(points)
        season = seasonality_factor(points, target_month)

        return Forecast(
            monthly_demand=max(0.0, base * growth * season),
            base_demand=base,
            growth_factor=growth,
            seasonality_factor=season,
            method=self.method,
        )

    def _smooth(self, values: list[float]) -> float:
        level = values[0]
        for value in values[1:]:
            level = self._alpha * value + (1 - self._alpha) * level
        return level

    @staticmethod
    def _is_rare(values: list[float]) -> bool:
        if not values:
            return True
        return sum(1 for v in values if v > 0) / len(values) < 0.5

    @staticmethod
    def _intermittent(values: list[float]) -> float:
        """Средний размер продажи, делённый на средний интервал между продажами."""
        nonzero = [v for v in values if v > 0]
        if not nonzero:
            return 0.0
        interval = len(values) / len(nonzero)
        return statistics.fmean(nonzero) / interval
