"""Фикстуры тестов.

Тесты не требуют ни Redis, ни файлов партнёра: всё внешнее подменяется
реализациями в памяти. Это и есть практическая польза портов.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import Container
from app.domain.entities import MonthPoint, Sku
from app.infrastructure.cache.memory import MemoryCache
from app.infrastructure.forecasting.baseline import BaselineForecaster
from app.infrastructure.forecasting.smoothed import SmoothedForecaster
from app.infrastructure.llm.template import TemplateNarrator
from app.infrastructure.storage.memory_repo import MemorySkuRepository
from app.main import create_app


def history(values: list[float], stocks: list[float] | None = None) -> tuple[MonthPoint, ...]:
    """История помесячно с января 2024."""
    stocks = stocks or [100.0] * len(values)
    return tuple(
        MonthPoint(
            month=date(2024 + i // 12, i % 12 + 1, 1),
            sold=sold,
            stock_start=stock,
        )
        for i, (sold, stock) in enumerate(zip(values, stocks, strict=True))
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return Settings(cache_backend="memory", narrator_backend="template", log_json=False)


@pytest.fixture
def repo() -> MemorySkuRepository:
    return MemorySkuRepository(
        [
            Sku(
                code="300200428_",
                name="A398 Роз. с з/к 16А",
                supplier="Systeme Electric",
                article="ATN000343",
                category="1",
                moq=10,
                free_stock=50.0,
                in_transit=0.0,
                history=history([40.0] * 24),
            ),
            Sku(
                code="200400085_",
                name="F/UTP кат.5Е",
                supplier="IEK",
                article="LC1-C5E04-311",
                moq=1,
                free_stock=5000.0,
                in_transit=0.0,
                history=history([6000.0] * 24),
            ),
        ]
    )


@pytest.fixture
def client(settings, repo) -> TestClient:
    container = Container(
        settings=settings,
        repo=repo,
        cache=MemoryCache(),
        forecasters={"baseline": BaselineForecaster(), "smoothed": SmoothedForecaster()},
        narrator=TemplateNarrator(),
    )
    app = create_app(settings, container=container)
    with TestClient(app) as test_client:
        yield test_client
