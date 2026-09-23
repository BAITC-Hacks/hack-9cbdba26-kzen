"""Совместимый вход загрузчика для composition root."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.storage.excel_normalizer import LoadedDataset, load_dataset
from app.infrastructure.storage.memory_repo import MemorySkuRepository


def load_repository(data_dir: Path) -> MemorySkuRepository:
    return load_dataset(data_dir).repository


__all__ = ["LoadedDataset", "load_dataset", "load_repository"]
