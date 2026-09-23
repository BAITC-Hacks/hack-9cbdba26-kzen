"""Конфигурация обучения.

Все пути, сиды и гиперпараметры здесь. Схема валидации тоже: её выбирают
один раз в начале дня и не меняют, иначе метрики разных экспериментов
становятся несравнимы и улучшения превращаются в угадайку.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "ml" / "artifacts"

SEED = 42

TaskType = Literal["binary_classification", "regression"]
ValidationStrategy = Literal["stratified", "time_based", "group"]


@dataclass
class TrainConfig:
    # --- данные ---
    data_path: Path = DATA_DIR / "dataset.parquet"
    target: str = "target"
    id_column: str = "subject_id"
    time_column: str | None = "snapshot_date"
    group_column: str | None = None
    drop_columns: list[str] = field(default_factory=list)

    # --- задача и валидация ---
    task_type: TaskType = "binary_classification"
    validation: ValidationStrategy = "time_based"
    n_folds: int = 5
    holdout_fraction: float = 0.2

    # --- модель ---
    iterations: int = 600
    learning_rate: float = 0.05
    depth: int = 6
    l2_leaf_reg: float = 3.0
    early_stopping_rounds: int = 50
    thread_count: int = 1  # для инференса по одному объекту многопоточность только мешает

    # --- вывод ---
    artifacts_dir: Path = ARTIFACTS_DIR
    seed: int = SEED

    @property
    def model_path(self) -> Path:
        return self.artifacts_dir / "model.joblib"

    @property
    def metadata_path(self) -> Path:
        return self.artifacts_dir / "metadata.json"
