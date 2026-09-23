"""Ручки агента закупщика.

Отдельно от /orders/calculate: запуск агента дороже простого расчёта (дополнительные
проверки, а позже вызовы LLM), и быстрый путь расчёта не должен за это платить.
Результат агента — обычная версия в /drafts: правка, утверждение и выгрузка
идут через те же ручки, агент не получает отдельного пути в обход человека.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep, get_calculator
from app.api.routes.drafts import RESPONSES
from app.api.schemas.drafts import AgentRunRequest, DraftSchema, InboundDelayRequest
from app.application.use_cases.agent import ReplanInboundDelay, RunProcurementAgent
from app.application.use_cases.replenishment import CalcParams

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post(
    "/runs",
    response_model=DraftSchema,
    status_code=201,
    responses=RESPONSES,
    summary="Агент готовит закупку",
    description=(
        "Проверяет данные, считает потребность, ищет аномалии и по флагам запускает "
        "дополнительные проверки. Каждая позиция получает статус ready / needs_review / "
        "insufficient_data, шаги видны в trace. Итог — версия, ожидающая утверждения."
    ),
)
def run_agent(payload: AgentRunRequest, container: ContainerDep) -> DraftSchema:
    agent = RunProcurementAgent(
        get_calculator(container, payload.method), container.repo, container.drafts
    )
    draft = agent.execute(
        goal=payload.goal,
        supplier=payload.supplier,
        category=payload.category,
        params=CalcParams(
            lead_time_days=payload.lead_time_days,
            coverage_months=payload.coverage_months,
            safety_factor=payload.safety_factor,
        ),
        method=payload.method,
        author=payload.author,
    )
    return DraftSchema.from_domain(draft)


@router.post(
    "/runs/{version}/inbound-delay",
    response_model=DraftSchema,
    responses=RESPONSES,
    summary="Что если поставка задерживается",
    description=(
        "Агент пересчитывает позицию тем же расчётом. Если заказ изменился — создаёт "
        "новую версию, которую нужно утвердить заново; иначе возвращает текущую."
    ),
)
def inbound_delay(
    version: int, payload: InboundDelayRequest, container: ContainerDep
) -> DraftSchema:
    replan = ReplanInboundDelay(
        lambda method: get_calculator(container, method), container.repo, container.drafts
    )
    draft, _ = replan.execute(
        version,
        payload.code,
        delayed_quantity=payload.delayed_quantity,
        new_eta=payload.new_eta,
        author=payload.author,
    )
    return DraftSchema.from_domain(draft)
