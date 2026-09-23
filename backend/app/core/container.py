"""Composition root: единственное место, где выбираются конкретные реализации.

Остальной код работает с протоколами из domain/ports.py. Второй принцип:
сервис поднимается всегда. Нет данных — работаем на пустом репозитории,
нет Redis — на памяти, нет LLM — на шаблоне. В /health при этом честно
пишется degraded. Упавшее на защите демо стоит дороже, чем демо без кэша.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import Settings
from app.domain.ports import CachePort, ForecasterPort, NarratorPort, SkuRepositoryPort

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    repo: SkuRepositoryPort
    cache: CachePort
    forecasters: dict[str, ForecasterPort]
    narrator: NarratorPort | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def degraded(self) -> bool:
        return bool(self.warnings)

    def describe(self) -> dict[str, str]:
        stats = self.repo.stats()
        return {
            "repo": getattr(self.repo, "backend", "unknown"),
            "skus": str(stats.get("skus", 0)),
            "suppliers": ", ".join(stats.get("suppliers", [])) or "нет данных",
            "forecasters": ", ".join(sorted(self.forecasters)),
            "cache": getattr(self.cache, "backend", self.settings.cache_backend),
            "narrator": getattr(self.narrator, "backend", "none"),
        }


async def build_container(
    settings: Settings,
    *,
    repo: SkuRepositoryPort | None = None,
    cache: CachePort | None = None,
    narrator: NarratorPort | None = None,
) -> Container:
    """Собрать контейнер по настройкам или из готовых компонентов.

    Переданный явно компонент используется как есть: если в коде написано
    «здесь такой репозиторий», подменять его на заглушку нельзя.
    """
    warnings: list[str] = []
    repo = repo if repo is not None else _build_repo(settings, warnings)
    cache = cache if cache is not None else await _build_cache(settings, warnings)
    narrator = narrator if narrator is not None else _build_narrator(settings, warnings)

    container = Container(
        settings=settings,
        repo=repo,
        cache=cache,
        forecasters=_build_forecasters(),
        narrator=narrator,
        warnings=warnings,
    )
    logger.info("Контейнер собран", extra={"components": container.describe()})
    for message in warnings:
        logger.warning(message)
    return container


def _build_forecasters() -> dict[str, ForecasterPort]:
    """Оба метода доступны всегда: их сравнение — часть демонстрации."""
    from app.infrastructure.forecasting.baseline import BaselineForecaster
    from app.infrastructure.forecasting.smoothed import SmoothedForecaster

    return {"baseline": BaselineForecaster(), "smoothed": SmoothedForecaster()}


def _build_repo(settings: Settings, warnings: list[str]) -> SkuRepositoryPort:
    from app.infrastructure.storage.memory_repo import MemorySkuRepository

    if settings.data_dir is None or not settings.data_dir.exists():
        warnings.append(
            f"Каталог данных не найден ({settings.data_dir}); работаем на пустой номенклатуре"
        )
        return MemorySkuRepository()

    try:
        from app.infrastructure.storage.excel_loader import load_repository

        return load_repository(settings.data_dir)
    except Exception as exc:
        warnings.append(f"Данные не загружены ({exc}); работаем на пустой номенклатуре")
        return MemorySkuRepository()


async def _build_cache(settings: Settings, warnings: list[str]) -> CachePort:
    from app.infrastructure.cache.memory import MemoryCache

    if settings.cache_backend == "memory":
        return MemoryCache()

    try:
        from app.infrastructure.cache.redis_cache import RedisCache

        cache = RedisCache(settings.redis_url)
        await cache.ping()
        return cache
    except Exception as exc:
        warnings.append(f"Redis недоступен ({exc}); кэш работает в памяти")
        return MemoryCache()


def _build_narrator(settings: Settings, warnings: list[str]) -> NarratorPort | None:
    if settings.narrator_backend == "none":
        return None

    from app.infrastructure.llm.template import TemplateNarrator

    if settings.narrator_backend == "template":
        return TemplateNarrator()

    try:
        from app.infrastructure.llm.nvidia_nim import NvidiaNarrator

        return NvidiaNarrator(
            settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model=settings.nvidia_model,
            timeout=settings.narrator_timeout,
        )
    except Exception as exc:
        warnings.append(f"LLM не подключён ({exc}); объяснения будут шаблонными")
        return TemplateNarrator()
