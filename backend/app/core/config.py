"""Настройки через переменные окружения.

Ни одного пути, хоста или порога в коде — всё сюда. Каждая новая настройка
должна попадать в .env.example, иначе через два часа никто не вспомнит,
почему сервис у соседа поднимается, а у вас нет.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Hackathon ML Service"
    version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = True

    # --- выбор реализаций (см. core/container.py) ---
    # dummy — заглушка; artifact — обученный пайплайн; llm — оценка языковой моделью без обучения
    model_backend: Literal["dummy", "artifact", "llm"] = "dummy"
    cache_backend: Literal["memory", "redis"] = "memory"
    storage_backend: Literal["memory", "parquet", "postgres"] = "memory"

    # --- модель ---
    model_path: Path = ROOT / "ml" / "artifacts" / "model.joblib"
    model_metadata_path: Path = ROOT / "ml" / "artifacts" / "metadata.json"

    # --- данные ---
    # Каталог с xlsx партнёра. Контейнер читает его при старте; без поля
    # сервис падал в lifespan, а тесты этого не видели — там контейнер подменён.
    data_dir: Path | None = ROOT / "data"
    # Нет данных партнёра — поднимаемся на демо-наборе, чтобы фронт и демо работали.
    # В шапке интерфейса режим честно помечается как demo.
    demo_fallback: bool = True
    dataset_path: Path = ROOT / "data" / "dataset.parquet"
    id_column: str = "subject_id"
    exclude_columns: list[str] = Field(default_factory=lambda: ["target"])

    # --- текстовые объяснения (необязательный блок) ---
    # none     — ручка объяснений выключена
    # template — текст собирается шаблоном, без внешних сервисов
    # openai   — внешняя модель по протоколу OpenAI (OpenAI, NIM, Groq, Ollama — только адрес),
    #            с откатом на шаблон при сбое
    narrator_backend: Literal["none", "template", "openai"] = "template"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    narrator_timeout: float = 8.0
    narrator_cache_ttl: int = 3600
    domain_hint: str = ""  # «отток абонентов связи» — помогает LLM говорить на языке кейса

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- производительность ---
    cache_ttl: int = 300

    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


_settings: Settings | None = None


def get_settings() -> Settings:
    """Синглтон настроек. Читаем .env один раз, а не на каждый запрос."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Сброс для тестов, где настройки подменяются переменными окружения."""
    global _settings
    _settings = None
