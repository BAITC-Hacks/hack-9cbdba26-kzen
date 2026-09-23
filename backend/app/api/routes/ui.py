"""Ручки под контракт фронта (FRONTEND_DATA.md, раздел 8).

Роутер только принимает HTTP и отдаёт готовый ответ: правила отображения,
права и статусы — в application/use_cases/ui.py. Всё `def`: расчёт и
пересчёт «что если» нагружают CPU.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Body, Query, Response

from app.api.deps import ContainerDep
from app.api.schemas.common import ErrorResponse
from app.application.use_cases import ui

router = APIRouter(tags=["ui"])
RESPONSES = {code: {"model": ErrorResponse} for code in (403, 404, 409, 422)}
MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
}
Payload = dict[str, Any]


# --- сессия и шапка ---

@router.get("/session", summary="Шапка: склад, дата расчёта, заказ, роль")
def session(container: ContainerDep) -> Payload:
    return ui.header(container)


@router.put("/session/role", responses=RESPONSES, summary="Сменить роль (демо)")
def session_role(container: ContainerDep, payload: Payload = Body(...)) -> Payload:
    return ui.set_role(container, payload.get("role", ""))


@router.post("/session/reset", summary="Сбросить расчёт, правки и версии сессии")
def session_reset(container: ContainerDep, payload: Payload = Body(default={})) -> Payload:
    return ui.reset_session(container)


# --- экран 01 ---

@router.get("/data/overview", summary="Источники, готовность, допущения, настройки")
def data_overview(container: ContainerDep) -> Payload:
    return ui.data_overview(container)


@router.patch("/settings", responses=RESPONSES, summary="Изменить настройки расчёта")
def patch_settings(container: ContainerDep, payload: Payload = Body(...)) -> Payload:
    return ui.patch_settings(container, payload)


@router.post("/calculations", summary="Запустить расчёт (агент закупщика)")
def calculations(container: ContainerDep, payload: Payload = Body(default={})) -> Payload:
    return ui.calculate(container)


# --- экран 02 ---

@router.post("/recommendations/search", responses=RESPONSES,
             summary="Рекомендации по поставщикам: поиск, фильтры, «что если»")
def recommendations(container: ContainerDep, payload: Payload = Body(default={})) -> Payload:
    return ui.search(container, payload)


# --- экран 03 ---

@router.get("/skus/{sku_id}/explanation", responses=RESPONSES, summary="Объяснение позиции")
def sku_explanation(sku_id: str, container: ContainerDep) -> Payload:
    return ui.explanation(container, sku_id)


@router.post("/skus/{sku_id}/actions", responses=RESPONSES, summary="Действие по позиции")
def sku_actions(sku_id: str, container: ContainerDep, payload: Payload = Body(...)) -> Payload:
    return ui.sku_action(container, sku_id, payload)


# --- экран 04 ---

@router.get("/orders/current", responses=RESPONSES, summary="Текущий заказ на проверку")
def order_current(container: ContainerDep) -> Payload:
    return ui.order_current(container)


@router.post("/orders/current/actions", responses=RESPONSES,
             summary="Отправить на согласование / утвердить / вернуть")
def order_actions(container: ContainerDep, payload: Payload = Body(...)) -> Payload:
    return ui.order_action(container, payload)


@router.patch("/orders/current/export-settings", responses=RESPONSES,
              summary="Настройки выгрузки")
def export_settings(container: ContainerDep, payload: Payload = Body(...)) -> Payload:
    return ui.update_export_settings(container, payload)


@router.post("/orders/export", responses=RESPONSES,
             summary="Файл утверждённого заказа для 1С (поставщику не отправляется)")
def order_export(container: ContainerDep, payload: Payload = Body(default={})) -> Response:
    filename, content, fmt = ui.export(container, payload)
    return Response(
        content=content, media_type=MEDIA[fmt],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/orders/versions", summary="Утверждённые версии")
def order_versions(container: ContainerDep) -> list[Payload]:
    return ui.versions(container)


@router.get("/orders/versions/{version}/diff", responses=RESPONSES,
            summary="Отличия версии от текущего списка")
def order_diff(version: int, container: ContainerDep,
               against: str = Query(default="current")) -> Payload:
    return ui.version_diff(container, version)


@router.get("/audit-log", summary="Журнал действий")
def audit_log(container: ContainerDep, page: int = Query(default=1, ge=1),
              page_size: int = Query(default=50, ge=1, le=200)) -> Payload:
    return ui.audit_log(container, page, page_size)


# --- экран 05 ---

@router.get("/validation/scenarios", summary="Проверки из п. 7 ТЗ вживую")
def validation_scenarios(container: ContainerDep) -> Payload:
    return ui.validation_scenarios(container)
