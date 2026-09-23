"""Ручки расчёта заказов.

Роутер только принимает HTTP и возвращает схему: вся логика кейса —
в use case. Эндпоинты объявлены через `def`, потому что расчёт по всему
ассортименту нагружает CPU и в корутине заблокировал бы весь сервис.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import ContainerDep, get_calculator
from app.api.schemas.common import ErrorResponse
from app.api.schemas.orders import (
    CalcRequest,
    CalcResponse,
    OrderLineSchema,
    SelfCheckResponse,
    StatsResponse,
    SupplierOrderSchema,
)
from app.application.use_cases.replenishment import CalcParams
from app.application.use_cases.selfcheck import RunSelfChecks
from app.domain.exceptions import NotFoundError

router = APIRouter(tags=["orders"])
RESPONSES = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


@router.post(
    "/orders/calculate",
    response_model=CalcResponse,
    summary="Рассчитать рекомендованные заказы",
    description=(
        "Возвращает список заказов, сгруппированный по поставщикам, с обоснованием "
        "по каждой позиции. Заказ поставщику не отправляется: сервис только "
        "рекомендует, утверждает менеджер."
    ),
)
def calculate(payload: CalcRequest, container: ContainerDep) -> CalcResponse:
    calculator = get_calculator(container, payload.method)
    orders = calculator.execute(
        supplier=payload.supplier,
        category=payload.category,
        params=CalcParams(
            lead_time_days=payload.lead_time_days,
            coverage_months=payload.coverage_months,
            safety_factor=payload.safety_factor,
        ),
    )
    return CalcResponse(
        suppliers=[SupplierOrderSchema.from_domain(o) for o in orders],
        total_positions=sum(o.positions for o in orders),
        method=payload.method,
    )


@router.get(
    "/orders/{code}",
    response_model=OrderLineSchema,
    responses=RESPONSES,
    summary="Расчёт по одному артикулу",
    description="Карточка позиции: сколько заказать и почему именно столько.",
)
def calculate_one(
    code: str,
    container: ContainerDep,
    lead_time_days: int = Query(default=45, ge=1, le=365),
    method: str = Query(default="smoothed"),
) -> OrderLineSchema:
    sku = container.repo.get(code)
    if sku is None:
        raise NotFoundError(f"Артикул {code!r} не найден", details={"code": code})

    calculator = get_calculator(container, method)
    line = calculator.calculate_line(sku, CalcParams(lead_time_days=lead_time_days))
    return OrderLineSchema.from_domain(line)


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Сводка по номенклатуре",
    description="Сколько артикулов, поставщиков, месяцев истории и какая доля месяцев без товара.",
)
def stats(container: ContainerDep) -> StatsResponse:
    return StatsResponse(**container.repo.stats())


@router.get(
    "/selfcheck",
    response_model=SelfCheckResponse,
    summary="Самопроверка по требованиям ТЗ",
    description=(
        "Прогоняет вживую пять проверок из пункта 7 технического задания: "
        "влияние товара в пути, сезонность, компенсация stockout, устойчивость "
        "к разовым заказам, наличие обоснования."
    ),
)
def selfcheck(container: ContainerDep) -> SelfCheckResponse:
    results = RunSelfChecks(get_calculator(container, "smoothed")).execute()
    return SelfCheckResponse(
        passed=sum(1 for r in results if r.passed),
        total=len(results),
        checks=[{"name": r.name, "passed": r.passed, "detail": r.detail} for r in results],  # type: ignore[list-item]
    )
