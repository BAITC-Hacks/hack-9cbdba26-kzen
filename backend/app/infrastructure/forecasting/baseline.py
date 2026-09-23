"""Baseline: текущая формула партнёра.

Видна в файле «Товар в пути_SystemElectric», лист TDSheet: среднее за последние
12 месяцев, умноженное на коэффициент роста и коэффициент сезонности.

Зачем воспроизводить чужую формулу вместо того, чтобы сразу делать «лучше»:
менеджер узнаёт свои цифры и начинает доверять сервису, а у нас появляется
точка отсчёта, относительно которой измеряется улучшение. Без baseline
фраза «наш прогноз точнее» ничем не подкреплена.
"""

from __future__ import annotations

import statistics

from app.domain.demand import growth_factor, seasonality_factor
from app.domain.entities import Forecast, Sku


class BaselineForecaster:
    """Среднее за 12 месяцев × рост × сезонность."""

    WINDOW = 12

    @property
    def method(self) -> str:
        return "baseline"

    def forecast(self, sku: Sku, target_month: int) -> Forecast:
        points = sku.history[-self.WINDOW :]
        if not points:
            return Forecast(0.0, 0.0, method=self.method)

        base = statistics.fmean([p.sold for p in points])
        growth = growth_factor(sku.history)
        season = seasonality_factor(sku.history, target_month)

        return Forecast(
            monthly_demand=max(0.0, base * growth * season),
            base_demand=base,
            growth_factor=growth,
            seasonality_factor=season,
            method=self.method,
        )
