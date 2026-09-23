"""Готовые сборки сервиса — альтернатива настройке через .env.

Оба способа равноправны:

    app = create_app()                              # по настройкам
    app = create_app(container_factory=demo)        # готовой сборкой

Отличие: переданный явно компонент используется как есть, без подстановки
заглушки при ошибке. Если в коде написано «здесь данные партнёра»,
сервис не должен тихо подняться на пустой номенклатуре.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.container import Container, build_container
from app.infrastructure.cache.memory import MemoryCache
from app.infrastructure.llm.template import TemplateNarrator
from app.infrastructure.storage.memory_repo import MemorySkuRepository


async def dev(settings: Settings) -> Container:
    """Пустая номенклатура: можно поднимать API и писать фронт до готовности парсера."""
    return await build_container(
        settings,
        repo=MemorySkuRepository(),
        cache=MemoryCache(),
        narrator=TemplateNarrator(),
    )


async def demo(settings: Settings) -> Container:
    """Данные партнёра из Excel, кэш в памяти, шаблонные объяснения.

    Конфигурация для защиты. Redis здесь намеренно нет: при одном воркере
    он только добавил бы задержку и ещё одну точку отказа.
    """
    from app.infrastructure.storage.excel_loader import load_repository

    return await build_container(
        settings,
        repo=load_repository(settings.data_dir),
        cache=MemoryCache(),
        narrator=TemplateNarrator(),
    )


PRESETS = {"dev": dev, "demo": demo}
