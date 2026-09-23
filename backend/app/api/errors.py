"""Преобразование доменных исключений в HTTP-ответы.

Роутеры и use cases ничего не знают про коды ответов: они бросают доменное
исключение, а маппинг живёт здесь. Пользователю уходит понятное сообщение
и request_id, трейсбек — только в лог.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import request_id_ctx
from app.domain.exceptions import (
    ConflictError,
    DomainError,
    DomainValidationError,
    ForbiddenError,
    ModelError,
    NotFoundError,
    StorageError,
)

logger = logging.getLogger(__name__)

STATUS_BY_EXCEPTION: dict[type[DomainError], int] = {
    NotFoundError: 404,
    DomainValidationError: 422,
    ConflictError: 409,
    ForbiddenError: 403,
    ModelError: 503,
    StorageError: 503,
}


def _payload(
    code: str, message: str, details: dict | None = None, field: str | None = None
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "request_id": request_id_ctx.get(),
            "details": details or {},
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        status = STATUS_BY_EXCEPTION.get(type(exc), 400)
        if status >= 500:
            logger.error("Доменная ошибка: %s", exc.message, exc_info=exc)
        else:
            logger.info("Доменная ошибка: %s", exc.message)
        return JSONResponse(
            status_code=status,
            content=_payload(exc.code, exc.message, exc.details, getattr(exc, "field", None)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload("validation_error", "Некорректный запрос", {"fields": exc.errors()}),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Необработанная ошибка", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_payload("internal_error", "Внутренняя ошибка сервиса"),
        )
