"""Доменные исключения.

Определены в домене, а мапятся в HTTP-коды в api/errors.py. Благодаря этому
use case может сказать «объект не найден», ничего не зная про существование HTTP.
"""


class DomainError(Exception):
    """Базовое исключение приложения."""

    code = "domain_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    code = "not_found"


class DomainValidationError(DomainError):
    code = "validation_error"


class ConflictError(DomainError):
    """Действие противоречит текущему состоянию объекта: например, утверждение
    версии, которую успели изменить после просмотра."""

    code = "conflict"


class ModelError(DomainError):
    code = "model_error"


class StorageError(DomainError):
    code = "storage_error"
