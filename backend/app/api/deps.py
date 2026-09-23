"""Зависимости FastAPI.

Контейнер лежит в app.state и отдаётся через Depends, а не берётся из глобальной
переменной: только так его можно подменить в тестах. Use case собирается
на запрос — объекты лёгкие, это ничего не стоит.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.application.use_cases.narrate import NarrateOrderLine
from app.application.use_cases.replenishment import CalculateOrders
from app.core.container import Container
from app.domain.exceptions import DomainValidationError


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_calculator(container: Container, method: str = "smoothed") -> CalculateOrders:
    """Собрать расчёт с нужным методом прогноза.

    Метод приходит из запроса, чтобы на демо можно было переключить формулу
    партнёра и наш прогноз и показать разницу вживую.
    """
    forecaster = container.forecasters.get(method)
    if forecaster is None:
        raise DomainValidationError(
            f"Неизвестный метод прогноза {method!r}",
            details={"available": sorted(container.forecasters)},
        )
    return CalculateOrders(container.repo, forecaster)


def get_narrate(container: ContainerDep) -> NarrateOrderLine | None:
    if container.narrator is None:
        return None
    return NarrateOrderLine(container.narrator, container.cache)
