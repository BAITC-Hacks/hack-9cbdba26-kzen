"""Точка входа.

Единственное место, где собирается приложение. Тяжёлая инициализация —
загрузка модели, индексация датасета, подключение Redis — происходит один раз
в lifespan при старте, а не на каждом запросе.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import MetricsCollector, register_middleware
from app.api.routes import agent, drafts, health, orders
from app.core.config import Settings, get_settings
from app.core.container import Container, build_container
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)

# Фабрика контейнера: принимает настройки, возвращает собранный контейнер.
# Под эту сигнатуру подходят и build_container, и любой пресет из app.core.presets.
ContainerFactory = Callable[[Settings], Awaitable[Container]]

DESCRIPTION = """
Расчёт рекомендованных заказов поставщикам для ТОО «Электрокомплект».

**Как устроено.** Прогноз, хранилище и объяснения подключаются через порты,
реализации собираются в `core/container.py`. Ядро (`domain`) не зависит
ни от FastAPI, ни от pandas.

**Методы прогноза.** `baseline` повторяет текущую формулу партнёра
(среднее за 12 месяцев × рост × сезонность), `smoothed` — экспоненциальное
сглаживание с отдельной веткой для редких продаж. Их можно переключать
в запросе и сравнивать результат.

**Проверки ТЗ.** Ручка `/api/v1/selfcheck` прогоняет вживую пять требований
из пункта 7 технического задания.
"""


def create_app(
    settings: Settings | None = None,
    *,
    container: Container | None = None,
    container_factory: ContainerFactory | None = None,
) -> FastAPI:
    """Собрать приложение.

    Состав сервиса задаётся одним из трёх способов:

    * ничего не передано — реализации берутся из настроек (.env);
    * `container_factory` — готовая сборка из app.core.presets или своя функция;
    * `container` — уже собранный контейнер, как в тестах.

    Явно переданное всегда сильнее настроек.
    """
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=DESCRIPTION,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.metrics = MetricsCollector()
    app.state.container = container
    app.state.container_factory = container_factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time", "X-Request-ID"],
    )
    register_middleware(app, app.state.metrics)
    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(orders.router, prefix=settings.api_prefix)
    app.include_router(drafts.router, prefix=settings.api_prefix)
    app.include_router(agent.router, prefix=settings.api_prefix)
    return app


async def _lifespan(app: FastAPI):
    settings: Settings = app.state.settings

    if app.state.container is None:
        factory = app.state.container_factory or build_container
        app.state.container = await factory(settings)
    logger.info(
        "Сервис запущен",
        extra={"components": app.state.container.describe(), "prefix": settings.api_prefix},
    )
    yield
    logger.info("Сервис остановлен")


# Точка, где задаётся состав сервиса.
#
# По умолчанию реализации берутся из .env — удобно переключать на ходу.
# Чтобы зафиксировать сборку в коде, замените строку ниже на пресет:
#
#     from app.core.presets import demo
#     app = create_app(container_factory=demo)
#
# Пресеты лежат в app/core/presets.py: dev (заглушки), demo (артефакт +
# parquet + кэш в памяти), scaled (то же с Redis). Свою сборку пишите там же.
app = create_app()
