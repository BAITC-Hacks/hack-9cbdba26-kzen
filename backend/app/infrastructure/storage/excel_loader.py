"""Загрузка данных партнёра из Excel.

ЗАГЛУШКА: здесь будет парсер шести типов файлов (помесячные продажи, остатки,
транзакции, товар в пути, MOQ, сезонность). Пока возвращает пустой репозиторий,
чтобы сервис поднимался и API работал до готовности парсера.

Ловушки, которые парсер обязан учесть (проверены на реальных файлах, подробности
в CASE.md): многоуровневые шапки, продажи положительными числами, транзакции
короче помесячной истории, stockout выводится из остатков, MOQ=0 означает 1.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.infrastructure.storage.memory_repo import MemorySkuRepository

logger = logging.getLogger(__name__)


def load_repository(data_dir: Path) -> MemorySkuRepository:
    logger.warning("Парсер Excel ещё не реализован, данные из %s не загружены", data_dir)
    return MemorySkuRepository()
