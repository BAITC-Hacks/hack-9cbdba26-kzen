"""Общие схемы ответов."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["Объект 'A-17' не найден в датасете"])
    request_id: str = Field(examples=["3f1c2b9a"])
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Единый формат ошибки для всех ручек: фронт пишет один обработчик."""

    error: ErrorPayload


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok", "degraded"])
    version: str
    components: dict[str, str]
    warnings: list[str] = Field(default_factory=list)


class MetricsResponse(BaseModel):
    requests_total: int
    errors_total: int
    latency_ms: dict[str, float] = Field(
        description="p50 / p95 / p99 и максимум по последним запросам"
    )
    by_endpoint: dict[str, int]
