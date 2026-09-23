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
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta

from app.domain.demand import prepare
from app.domain.entities import (
    Forecast,
    Inbound,
    OrderLine,
    ReasonPart,
    Sku,
    SupplierOrder,
    Urgency,
    urgency_for,
)
from app.domain.exceptions import DomainValidationError
from app.domain.ports import ForecasterPort, SkuRepositoryPort

MONTH_DAYS = 30.0

# Категории Systeme — приоритет пополнения из модели менеджера. Для более
# приоритетных категорий держим дополнительный страховой запас; коэффициенты
# фиксированы как бизнес-политика и всегда показываются в обосновании.
CATEGORY_SAFETY_UPLIFT = {"1": 0.10, "2": 0.05, "3": 0.0}


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

    def __post_init__(self) -> None:
        if self.lead_time_days <= 0:
            raise DomainValidationError("Срок поставки должен быть положительным")
        if not 0 <= self.coverage_months <= 12:
            raise DomainValidationError("Целевой запас должен быть от 0 до 12 месяцев")
        if not 0 <= self.safety_factor <= 1:
            raise DomainValidationError("Страховой коэффициент должен быть от 0 до 1")

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
        skus = self._repo.list_skus(supplier=supplier, category=category)
        return calculate_recommendations(
            skus, self._forecaster, params, only_needed=only_needed
        )

    def calculate_line(self, sku: Sku, params: CalcParams) -> OrderLine:
        return calculate_order_line(sku, params, self._forecaster)


def calculate_order_line(
    sku: Sku, params: CalcParams, forecaster: ForecasterPort
) -> OrderLine:
    """Рассчитать одну нормализованную позицию без HTTP и репозитория."""
    today = params.today or date.today()
    arrival = today + timedelta(days=sku.lead_time_days or params.lead_time_days)

    cleaned = prepare(sku.history, sku.bulk_orders)
    # Прогноз строится по очищенной истории: это и есть вклад Must have 3 и 4
    forecast = forecaster.forecast(
        replace(sku, history=cleaned.points),
        arrival.month,
    )

    lead_months = (sku.lead_time_days or params.lead_time_days) / MONTH_DAYS
    horizon = lead_months + params.coverage_months
    configured_uplift = (
        CATEGORY_SAFETY_UPLIFT.get(sku.category, 0.0)
        if sku.supplier == "Systeme Electric"
        else 0.0
    )
    effective_safety = min(1.0, params.safety_factor + configured_uplift)
    category_uplift = effective_safety - params.safety_factor
    need_without_category = forecast.monthly_demand * horizon * (1 + params.safety_factor)
    need = forecast.monthly_demand * horizon * (1 + effective_safety)
    category_effect = need - need_without_category
    counted_inbound, late_inbound = _split_inbound(sku, arrival)
    available = sku.free_stock + counted_inbound
    raw_qty = need - available

    quantity = _round_to_moq(raw_qty, sku.moq)
    coverage = (
        sku.free_stock / forecast.monthly_demand if forecast.monthly_demand > 0 else 999.0
    )
    urgency = urgency_for(coverage, lead_months) if quantity > 0 else Urgency.NONE

    return OrderLine(
        sku=sku,
        quantity=quantity,
        urgency=urgency,
        monthly_demand=round(forecast.monthly_demand, 2),
        coverage_months=round(min(coverage, 999.0), 2),
        reasons=_build_reasons(
            sku,
            cleaned,
            forecast,
            params,
            need,
            available,
            quantity,
            effective_safety,
            category_uplift,
            category_effect,
            counted_inbound,
            late_inbound,
        ),
        method=forecast.method,
    )


def calculate_recommendations(
    skus: Iterable[Sku],
    forecaster: ForecasterPort,
    params: CalcParams | None = None,
    *,
    only_needed: bool = True,
) -> list[SupplierOrder]:
    """Рассчитать рекомендации из нормализованных сущностей без HTTP и хранилища."""
    params = params or CalcParams()
    lines = [calculate_order_line(sku, params, forecaster) for sku in skus]
    if only_needed:
        lines = [line for line in lines if line.needed]

    grouped: dict[str, list[OrderLine]] = {}
    for line in lines:
        grouped.setdefault(line.sku.supplier, []).append(line)

    orders = []
    for name, items in grouped.items():
        items.sort(key=lambda item: (_urgency_rank(item.urgency), -item.quantity))
        orders.append(SupplierOrder(supplier=name, lines=items))
    orders.sort(key=lambda order: -order.critical_positions)
    return orders


def _split_inbound(sku: Sku, arrival: date) -> tuple[float, tuple[Inbound, ...]]:
    """Разделить путь на успевающий к нашей поставке и опаздывающий."""
    if not sku.inbound:
        return max(0.0, sku.in_transit), ()

    counted = sum(
        item.quantity for item in sku.inbound if item.eta is None or item.eta <= arrival
    )
    late = tuple(item for item in sku.inbound if item.eta is not None and item.eta > arrival)
    return counted, late


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


def _build_reasons(
    sku,
    cleaned,
    forecast: Forecast,
    params,
    need,
    available,
    quantity,
    effective_safety,
    category_uplift,
    category_effect,
    counted_inbound,
    late_inbound,
):
    """Обоснование строки (Must have 5).

    Каждое число берётся из расчёта выше. Ни одно не сочиняется — поэтому
    менеджер может проверить любую цифру вручную и получить то же самое.
    """
    unit = sku.unit
    reasons = [
        ReasonPart("Средние продажи", f"{forecast.base_demand:.1f} {unit}/мес"),
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
                f"{cleaned.stockout_months} мес, +{cleaned.compensated:.0f} {unit}",
                effect=cleaned.compensated,
            )
        )

    if sku.supplier == "Systeme Electric" and sku.category in CATEGORY_SAFETY_UPLIFT:
        reasons.append(
            ReasonPart(
                "Категория",
                f"{sku.category}: страховой запас {effective_safety:.0%} "
                f"({category_uplift:+.0%} к базовому)",
                effect=category_effect,
            )
        )

    if cleaned.removed_bulk > 0:
        reasons.append(
            ReasonPart(
                "Исключены разовые крупные продажи",
                f"−{cleaned.removed_bulk:.0f} {unit}",
                effect=-cleaned.removed_bulk,
            )
        )

    if sku.on_hand_stock is not None:
        reasons.append(ReasonPart("Остаток на складе", f"{sku.on_hand_stock:.0f} {unit}"))
    if sku.reserved_stock > 0:
        reasons.append(ReasonPart("Зарезервировано", f"{sku.reserved_stock:.0f} {unit}"))

    reasons += [
        ReasonPart("Срок поставки", f"{sku.lead_time_days or params.lead_time_days} дн"),
        ReasonPart("Потребность на период", f"{need:.0f} {unit}"),
        ReasonPart("Свободный остаток", f"{sku.free_stock:.0f} {unit}"),
        ReasonPart("Учтено в пути", f"{counted_inbound:.0f} {unit}"),
    ]

    if late_inbound:
        details = "; ".join(
            f"{item.document or 'поставка'}, {item.eta:%d.%m} — {item.quantity:.0f} {unit}"
            for item in late_inbound
        )
        reasons.append(ReasonPart("Не успевает", details))

    if quantity and sku.moq > 1:
        reasons.append(ReasonPart("Кратность отгрузки", f"{sku.moq} {unit}"))

    return reasons
