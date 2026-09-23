"""Ручки рабочего процесса закупщика: версии, правки, утверждение, выгрузка.

Все `def`: создание версии гоняет расчёт по ассортименту, а правки берут
threading-замок хранилища — ни то, ни другое нельзя делать в event loop.
Ручки «отправить поставщику» нет и не будет: запрет ТЗ.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Query, Response

from app.api.deps import ContainerDep, get_calculator
from app.api.schemas.common import ErrorResponse
from app.api.schemas.drafts import (
    AdjustRequest,
    ApproveRequest,
    CreateDraftRequest,
    DraftSchema,
    DraftSummarySchema,
)
from app.application.use_cases.drafts import AdjustLine, ApproveDraft, CreateDraft, ExportDraft
from app.application.use_cases.replenishment import CalcParams

router = APIRouter(prefix="/drafts", tags=["drafts"])
RESPONSES = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "",
    response_model=DraftSchema,
    status_code=201,
    summary="Рассчитать и сохранить новую версию заказа",
)
def create_draft(payload: CreateDraftRequest, container: ContainerDep) -> DraftSchema:
    draft = CreateDraft(get_calculator(container, payload.method), container.drafts).execute(
        params=CalcParams(
            lead_time_days=payload.lead_time_days,
            coverage_months=payload.coverage_months,
            safety_factor=payload.safety_factor,
        ),
        supplier=payload.supplier,
        category=payload.category,
        method=payload.method,
        author=payload.author,
    )
    return DraftSchema.from_domain(draft)


@router.get("", response_model=list[DraftSummarySchema], summary="Список версий расчёта")
def list_drafts(container: ContainerDep) -> list[DraftSummarySchema]:
    return [DraftSummarySchema.from_domain(d) for d in container.drafts.list()]


@router.get(
    "/{version}", response_model=DraftSchema, responses=RESPONSES, summary="Версия целиком"
)
def get_draft(version: int, container: ContainerDep) -> DraftSchema:
    return DraftSchema.from_domain(container.drafts.get(version))


@router.patch(
    "/{version}/lines/{code}",
    response_model=DraftSchema,
    responses=RESPONSES,
    summary="Ручная корректировка количества",
    description="Причина обязательна. Правка утверждённой версии снимает утверждение.",
)
def adjust_line(
    version: int, code: str, payload: AdjustRequest, container: ContainerDep
) -> DraftSchema:
    draft = AdjustLine(container.drafts).execute(
        version, code, quantity=payload.quantity, reason=payload.reason, author=payload.author
    )
    return DraftSchema.from_domain(draft)


@router.post(
    "/{version}/approve",
    response_model=DraftSchema,
    responses=RESPONSES,
    summary="Утвердить заказ",
    description="Передайте ревизию с экрана: если заказ успели изменить, вернётся 409.",
)
def approve(version: int, payload: ApproveRequest, container: ContainerDep) -> DraftSchema:
    draft = ApproveDraft(container.drafts).execute(
        version, author=payload.author, revision=payload.revision
    )
    return DraftSchema.from_domain(draft)


@router.get(
    "/{version}/export",
    responses={**RESPONSES, 200: {"content": {"text/csv": {}}}},
    summary="Выгрузить утверждённый заказ в CSV",
    description="Файл для загрузки в 1С. Поставщику ничего не отправляется.",
)
def export(
    version: int,
    container: ContainerDep,
    supplier: str | None = Query(default=None, description="Только один поставщик"),
) -> Response:
    filename, content = ExportDraft(container.drafts).execute(version, supplier=supplier)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
