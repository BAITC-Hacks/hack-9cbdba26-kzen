"""Загрузка выгрузок 1С через интерфейс.

Роутер только принимает multipart и отдаёт состояние задачи; проверки формы,
запись файлов и фоновый разбор — в application/use_cases/imports.py.
Ручка `def`: чтение тела и запись на диск — блокирующие операции, им место
в пуле потоков, а не в event loop.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import ContainerDep
from app.api.schemas.common import ErrorResponse
from app.application.use_cases import imports

router = APIRouter(prefix="/imports", tags=["imports"])
RESPONSES = {code: {"model": ErrorResponse} for code in (404, 422)}
Payload = dict[str, Any]


@router.post("", status_code=202, responses=RESPONSES,
             summary="Загрузить xlsx одного поставщика и запустить разбор в фоне")
def create_import(
    container: ContainerDep,
    supplier: str = Form(..., description="IEK или Systeme Electric"),
    files: list[UploadFile] = File(..., description="1–6 файлов .xlsx"),
) -> Payload:
    uploads = [(upload.filename or "", upload.file.read()) for upload in files]
    return imports.start_import(container, supplier, uploads)


@router.get("", summary="Последние импорты, новые первыми")
def list_imports(container: ContainerDep) -> list[Payload]:
    return imports.list_imports(container)


@router.get("/{import_id}", responses=RESPONSES, summary="Состояние импорта и отчёт о данных")
def get_import(import_id: str, container: ContainerDep) -> Payload:
    return imports.get_import(container, import_id)
