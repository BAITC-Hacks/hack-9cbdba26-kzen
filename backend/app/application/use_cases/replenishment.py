"""Сценарий: расчёт рекомендованных заказов поставщикам.

Здесь собирается вся логика кейса. Порядок шагов взят из ТЗ и из формулы,
которой партнёр пользуется сейчас:

    история → очистка от выбросов → компенсация провалов наличия
    → прогноз (рост, сезонность) → потребность на срок поставки и целевой запас
    → минус свободный остаток и товар в пути → округление до кратности
    → срочность и обоснование

Заказ никогда не уходит поставщику сам: сервис только рекомендует,
подтверждает человек. Это прямой запрет из ТЗ.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.demand import prepare
from app.domain.entities import (
    Forecast,
    OrderLine,
    ReasonPart,
    Sku,
    SupplierOrder,
    Urgency,
    urgency_for,
)
from app.domain.ports import ForecasterPort, SkuRepositoryPort

MONTH_DAYS = 30.0


@dataclass(frozen=True, slots=True)
class CalcParams:
    """Параметры расчёта. Всё, что менеджер может покрутить в интерфейсе.

    lead_time_days вынесен в параметры, потому что в данных партнёра
    сроков поставки нет — их нужно уточнять и удобно моделировать «что если».
    """

    lead_time_days: int = 45
    coverage_months: float = 1.0   # целевой запас сверх срока поставки
    safety_factor: float = 0.2     # страховой запас, доля от потребности
    today: date | None = None

    @property
    def lead_time_months(self) -> float:
        return self.lead_time_days / MONTH_DAYS


class CalculateOrders:
    """Расчёт заказов по всем артикулам, сгруппированных по поставщикам."""

    def __init__(self, repo: SkuRepositoryPort, forecaster: ForecasterPort) -> None:
        self._repo = repo
        self._forecaster = forecaster

    def execute(
        self,
        *,
        supplier: str | None = None,
        category: str | None = None,
        params: CalcParams | None = None,
        only_needed: bool = True,
    ) -> list[SupplierOrder]:
        params = params or CalcParams()
        lines = [
            self.calculate_line(sku, params)
            for sku in self._repo.list_skus(supplier=supplier, category=category)
        ]
        if only_needed:
            lines = [line for line in lines if line.needed]

        grouped: dict[str, list[OrderLine]] = {}
        for line in lines:
            grouped.setdefault(line.sku.supplier, []).append(line)

        orders = []
        for name, items in grouped.items():
            # Сначала критичные: менеджер смотрит список сверху вниз
            items.sort(key=lambda x: (_urgency_rank(x.urgency), -x.quantity))
            orders.append(SupplierOrder(supplier=name, lines=items))

        orders.sort(key=lambda o: -o.critical_positions)
        return orders

    def calculate_line(self, sku: Sku, params: CalcParams) -> OrderLine:
        today = params.today or date.today()
        arrival = today + timedelta(days=sku.lead_time_days or params.lead_time_days)

        cleaned = prepare(sku.history)
        # Прогноз строится по очищенной истории: это и есть вклад Must have 3 и 4
        forecast = self._forecaster.forecast(
            Sku(
                code=sku.code, name=sku.name, supplier=sku.supplier, article=sku.article,
                category=sku.category, moq=sku.moq, free_stock=sku.free_stock,
                in_transit=sku.in_transit, lead_time_days=sku.lead_time_days,
                history=cleaned.points,
            ),
            arrival.month,
        )

        lead_months = (sku.lead_time_days or params.lead_time_days) / MONTH_DAYS
        horizon = lead_months + params.coverage_months
        need = forecast.monthly_demand * horizon * (1 + params.safety_factor)
        available = sku.free_stock + sku.in_transit
        raw_qty = need - available

        quantity = _round_to_moq(raw_qty, sku.moq)
        coverage = available / forecast.monthly_demand if forecast.monthly_demand > 0 else 999.0
        urgency = urgency_for(coverage, lead_months) if quantity > 0 else Urgency.NONE

        return OrderLine(
            sku=sku,
            quantity=quantity,
            urgency=urgency,
            monthly_demand=round(forecast.monthly_demand, 2),
            coverage_months=round(min(coverage, 999.0), 2),
            reasons=_build_reasons(sku, cleaned, forecast, params, need, available, quantity),
            method=forecast.method,
        )


def _round_to_moq(quantity: float, moq: int) -> int:
    """Округление вверх до кратности отгрузки.

    moq в данных может быть 0 (у Systeme в колонке «Кратность») — трактуем как 1,
    иначе деление развалится.
    """
    if quantity <= 0:
        return 0
    step = max(1, moq)
    return int(math.ceil(quantity / step) * step)


def _urgency_rank(urgency: Urgency) -> int:
    order = {Urgency.CRITICAL: 0, Urgency.HIGH: 1, Urgency.NORMAL: 2, Urgency.NONE: 3}
    return order[urgency]


def _build_reasons(sku, cleaned, forecast: Forecast, params, need, available, quantity):
    """Обоснование строки (Must have 5).

    Каждое число берётся из расчёта выше. Ни одно не сочиняется — поэтому
    менеджер может проверить любую цифру вручную и получить то же самое.
    """
    reasons = [
        ReasonPart("Средние продажи", f"{forecast.base_demand:.1f} шт/мес"),
    ]

    if abs(forecast.growth_factor - 1) > 0.05:
        pct = (forecast.growth_factor - 1) * 100
        reasons.append(ReasonPart("Тренд", f"{pct:+.0f}%", effect=pct))

    if abs(forecast.seasonality_factor - 1) > 0.05:
        pct = (forecast.seasonality_factor - 1) * 100
        reasons.append(ReasonPart("Сезонность месяца поставки", f"{pct:+.0f}%", effect=pct))

    if cleaned.stockout_months:
        reasons.append(
            ReasonPart(
                "Компенсация отсутствия товара",
                f"{cleaned.stockout_months} мес, +{cleaned.compensated:.0f} шт",
                effect=cleaned.compensated,
            )
        )

    if cleaned.removed_bulk > 0:
        reasons.append(
            ReasonPart(
                "Исключены разовые крупные продажи",
                f"−{cleaned.removed_bulk:.0f} шт",
                effect=-cleaned.removed_bulk,
            )
        )

    reasons += [
        ReasonPart("Срок поставки", f"{sku.lead_time_days or params.lead_time_days} дн"),
        ReasonPart("Потребность на период", f"{need:.0f} шт"),
        ReasonPart("Свободный остаток и товар в пути", f"{available:.0f} шт"),
    ]

    if quantity and sku.moq > 1:
        reasons.append(ReasonPart("Кратность отгрузки", f"{sku.moq} шт"))

    return reasons
