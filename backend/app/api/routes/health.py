"""Health и метрики.

/health отвечает ok только если модель действительно загружена и ни один
компонент не свалился в fallback. Иначе degraded — чтобы деградацию было
видно сразу, а не в момент демонстрации.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import ContainerDep
from app.api.schemas.common import HealthResponse, MetricsResponse

router = APIRouter(tags=["service"])


@router.get("/health", response_model=HealthResponse, summary="Состояние сервиса")
def health(container: ContainerDep) -> HealthResponse:
    return HealthResponse(
        status="degraded" if container.degraded else "ok",
        version=container.settings.version,
        components=container.describe(),
        warnings=container.warnings,
    )


@router.get("/metrics", response_model=MetricsResponse, summary="Латентность и счётчики")
def metrics(request: Request) -> MetricsResponse:
    return MetricsResponse(**request.app.state.metrics.snapshot())
