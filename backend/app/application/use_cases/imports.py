"""Загрузка выгрузок 1С через интерфейс вместо папки `data/` при старте.

Чтение шести xlsx одного поставщика на реальных данных идёт до 30 секунд,
поэтому ручка отвечает сразу, а разбор идёт в отдельном потоке. Состояние
задач живёт в памяти процесса (реестр на контейнере) — как версии расчёта:
один воркер, перезапуск обнуляет историю, для прода нужна таблица.

Можно загрузить любой поднабор файлов, хоть один: недостающие типы берутся
из текущего набора поставщика — папки `data/` при старте или каталога последнего
применённого импорта. Загрузчик по-прежнему требует все шесть файлов, поэтому
слияние делается на уровне каталога, а не внутри нормализатора.

Успешный импорт заменяет данные только своего поставщика: второй поставщик
остаётся как был. Версии и правки сбрасываются — они привязаны к старому
снимку данных, и оставлять их значило бы показывать заказ, посчитанный
по другим числам.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.domain.exceptions import DomainError, DomainValidationError, NotFoundError

if TYPE_CHECKING:
    from app.core.container import Container

logger = logging.getLogger(__name__)

SUPPLIERS = ("IEK", "Systeme Electric")
MAX_FILES = 6
MAX_TOTAL_BYTES = 60 * 1024 * 1024
HISTORY_LIMIT = 20


@dataclass
class ImportJob:
    import_id: str
    supplier: str
    files: list[str]
    directory: Path
    started_at: datetime
    status: str = "running"  # running | done | failed
    finished_at: datetime | None = None
    report: dict[str, Any] | None = None
    error: str | None = None
    applied: bool = False
    # Файлы, взятые из прошлого набора вместо загруженных: менеджер должен видеть,
    # на каких данных считается заказ
    reused_files: list[str] = field(default_factory=list)
    # Событие, а не опрос статуса: тесты и вызывающий код ждут завершения без sleep
    done: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self, *, with_report: bool = True) -> dict[str, Any]:
        payload = {
            "import_id": self.import_id,
            "status": self.status,
            "supplier": self.supplier,
            "files": list(self.files),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "applied": self.applied,
            "reused_files": list(self.reused_files),
        }
        if with_report:
            payload["report"] = self.report
        return payload


class ImportRegistry:
    """Задачи импорта текущего процесса: создание, статус, ожидание.

    Запись под замком: ручка создаёт задачу из пула потоков FastAPI, а
    завершает её фоновый поток. Чтение словаря без замка безопасно — ссылки
    подменяются целиком.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, ImportJob] = {}
        # Каталог последнего применённого импорта по поставщику: источник
        # недостающих файлов для следующего частичного импорта
        self._sources: dict[str, Path] = {}

    def source(self, supplier: str) -> Path | None:
        return self._sources.get(supplier)

    def keep_source(self, supplier: str, directory: Path) -> Path | None:
        """Запомнить каталог применённого импорта; вернуть предыдущий для удаления."""
        with self._lock:
            previous = self._sources.get(supplier)
            self._sources[supplier] = directory
        return previous

    def create(self, supplier: str, files: list[str], directory: Path) -> ImportJob:
        job = ImportJob(
            import_id=uuid.uuid4().hex[:12],
            supplier=supplier,
            files=files,
            directory=directory,
            started_at=datetime.now(UTC),
        )
        with self._lock:
            self._jobs[job.import_id] = job
            # Старые задачи не нужны фронту, а их временные каталоги уже удалены
            for stale in list(self._jobs)[:-HISTORY_LIMIT]:
                del self._jobs[stale]
        return job

    def get(self, import_id: str) -> ImportJob:
        job = self._jobs.get(import_id)
        if job is None:
            raise NotFoundError(f"Импорт {import_id!r} не найден", details={"import_id": import_id})
        return job

    def list(self) -> list[ImportJob]:
        return sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)[
            :HISTORY_LIMIT
        ]

    def finish(self, job: ImportJob, *, report: dict[str, Any] | None, error: str | None) -> None:
        with self._lock:
            job.report = report
            job.error = error
            job.applied = error is None
            job.status = "failed" if error else "done"
            job.finished_at = datetime.now(UTC)
        job.done.set()

    def wait(self, import_id: str, timeout: float = 60.0) -> ImportJob:
        job = self.get(import_id)
        if not job.done.wait(timeout):
            raise TimeoutError(f"Импорт {import_id!r} не завершился за {timeout} с")
        return job

    def last_applied(self, supplier: str | None = None) -> ImportJob | None:
        for job in self.list():
            if job.applied and (supplier is None or job.supplier == supplier):
                return job
        return None


# ---------- проверки формы ----------

def validate_upload(supplier: str, filenames: list[str], total_bytes: int) -> None:
    """Всё, что можно отклонить до записи файлов на диск и запуска потока."""
    if supplier not in SUPPLIERS:
        raise DomainValidationError(
            f"Неизвестный поставщик {supplier!r}",
            code="UNKNOWN_SUPPLIER", field="supplier", details={"allowed": list(SUPPLIERS)},
        )
    if not filenames:
        raise DomainValidationError("Не передано ни одного файла", code="NO_FILES", field="files")
    if len(filenames) > MAX_FILES:
        raise DomainValidationError(
            f"Максимум {MAX_FILES} файлов за один импорт", code="TOO_MANY_FILES", field="files",
        )
    wrong = [name for name in filenames if not name.casefold().endswith(".xlsx")]
    if wrong:
        raise DomainValidationError(
            "Принимаются только файлы .xlsx", code="BAD_FILE_TYPE", field="files",
            details={"files": wrong},
        )
    if total_bytes > MAX_TOTAL_BYTES:
        raise DomainValidationError(
            f"Суммарный размер файлов больше {MAX_TOTAL_BYTES // (1024 * 1024)} МБ",
            code="FILE_TOO_LARGE", field="files", details={"total_bytes": total_bytes},
        )


def _safe_name(filename: str) -> str:
    """Только basename: путь из формы нельзя пускать на диск как есть."""
    return Path(filename.replace("\\", "/")).name or "file.xlsx"


# ---------- запуск и выполнение ----------

Loader = Callable[[str, Path], Any]


def _default_loader(supplier: str, directory: Path) -> Any:
    from app.infrastructure.storage.excel_normalizer import load_supplier_dataset

    return load_supplier_dataset(supplier, directory)


def _current_files(c: Container, supplier: str) -> list[Path]:
    """Файлы поставщика, по которым сервис считает сейчас."""
    from app.infrastructure.storage.excel_normalizer import SUPPLIER_MARKERS

    kept = c.imports.source(supplier)
    if kept is not None and kept.exists():
        return sorted(kept.rglob("*.xlsx"))
    data_dir = c.settings.data_dir
    if data_dir is None or not data_dir.exists():
        return []
    marker = SUPPLIER_MARKERS[supplier]
    return [path for path in sorted(data_dir.rglob("*.xlsx")) if marker in str(path).casefold()]


def _classify(supplier: str, names: list[str]) -> dict[str, str]:
    """Имя файла → тип; неизвестный тип и два файла одного типа отклоняются сразу."""
    from app.infrastructure.storage.excel_normalizer import file_markers

    markers = file_markers(supplier)
    by_kind: dict[str, str] = {}
    for name in names:
        kind = next((k for k, marker in markers.items() if marker in name.casefold()), None)
        if kind is None:
            raise DomainValidationError(
                f"Не удалось понять назначение файла {name!r}: в имени нет ни одного "
                f"из ожидаемых слов ({', '.join(markers.values())})",
                code="UNKNOWN_FILE_KIND", field="files", details={"file": name},
            )
        if kind in by_kind:
            raise DomainValidationError(
                f"Файлы {by_kind[kind]!r} и {name!r} одного типа — оставьте один",
                code="DUPLICATE_FILE_KIND", field="files",
                details={"files": [by_kind[kind], name]},
            )
        by_kind[kind] = name
    return by_kind


def _fill_missing(
    c: Container, supplier: str, directory: Path, uploaded: dict[str, str]
) -> list[str]:
    """Докопировать в каталог импорта недостающие типы из текущего набора."""
    from app.infrastructure.storage.excel_normalizer import file_markers

    markers = file_markers(supplier)
    current = _current_files(c, supplier)
    reused: list[str] = []
    missing: list[str] = []
    for kind, marker in markers.items():
        if kind in uploaded:
            continue
        matches = [path for path in current if marker in path.name.casefold()]
        if len(matches) != 1:
            missing.append(marker)
            continue
        shutil.copyfile(matches[0], directory / matches[0].name)
        reused.append(matches[0].name)
    if missing:
        raise DomainValidationError(
            f"Для {supplier} нет текущих данных, из которых можно взять недостающие файлы: "
            f"{', '.join(missing)}. Загрузите их вместе с остальными",
            code="MISSING_FILES", field="files", details={"missing": missing},
        )
    return reused


def start_import(
    c: Container, supplier: str, uploads: list[tuple[str, bytes]], *, loader: Loader | None = None
) -> dict[str, Any]:
    """Сохранить файлы во временный каталог и запустить разбор в фоне.

    Каталог создаётся вне `settings.data_dir`: иначе `rglob` при следующем
    старте найдёт дубли файлов и загрузчик упадёт.
    """
    names = [_safe_name(name) for name, _ in uploads]
    validate_upload(supplier, names, sum(len(content) for _, content in uploads))
    if len(set(name.casefold() for name in names)) != len(names):
        raise DomainValidationError(
            "Имена файлов повторяются", code="DUPLICATE_FILE", field="files",
        )
    uploaded_kinds = _classify(supplier, names)

    directory = Path(tempfile.mkdtemp(prefix="ekt-import-")) / supplier
    directory.mkdir()
    try:
        for name, (_, content) in zip(names, uploads, strict=True):
            (directory / name).write_bytes(content)
        reused = _fill_missing(c, supplier, directory, uploaded_kinds)
    except Exception:
        shutil.rmtree(directory.parent, ignore_errors=True)
        raise

    job = c.imports.create(supplier, names, directory)
    job.reused_files = reused
    threading.Thread(
        target=_run, args=(c, job, loader or _default_loader),
        name=f"import-{job.import_id}", daemon=True,
    ).start()
    return {
        "import_id": job.import_id, "status": job.status,
        "supplier": job.supplier, "files": job.files, "reused_files": reused,
    }


def _run(c: Container, job: ImportJob, loader: Loader) -> None:
    """Тело фонового потока: любая ошибка превращается в статус failed, не в падение сервиса."""
    applied = False
    try:
        loaded = loader(job.supplier, job.directory)
        _apply(c, job.supplier, loaded.repository.list_skus())
        report = loaded.report.to_dict()
        report.setdefault("metrics", {})["reused_from_previous"] = list(job.reused_files)
        c.imports.finish(job, report=report, error=None)
        applied = True
        logger.info("Импорт %s применён: %s", job.import_id, job.supplier)
    except DomainError as exc:
        c.imports.finish(job, report=None, error=exc.message)
        logger.warning("Импорт %s отклонён: %s", job.import_id, exc.message)
    except Exception as exc:  # поток не должен умирать молча: любая ошибка → failed
        c.imports.finish(job, report=None, error=f"Не удалось разобрать файлы: {exc}")
        logger.exception("Импорт %s упал", job.import_id)
    finally:
        if applied:
            # Каталог остаётся источником недостающих файлов для следующего импорта;
            # предыдущий такой каталог больше не нужен
            previous = c.imports.keep_source(job.supplier, job.directory)
            if previous is not None and previous != job.directory:
                shutil.rmtree(previous.parent, ignore_errors=True)
        else:
            shutil.rmtree(job.directory.parent, ignore_errors=True)


def _apply(c: Container, supplier: str, new_skus: list) -> None:
    """Слить по поставщику и подменить репозиторий одним присваиванием.

    Замок рабочего места — тот же, под которым расчёт фиксирует версию:
    подмена данных и сброс версий не должны вклиниться между расчётом и
    записью его номера. Сам `workspace.reset()` берёт этот замок сам,
    поэтому вызывается после.
    """
    from app.infrastructure.storage.memory_repo import MemorySkuRepository

    with c.workspace.lock:
        kept = [sku for sku in c.repo.list_skus() if sku.supplier != supplier]
        c.repo = MemorySkuRepository(kept + list(new_skus))
        c.drafts.clear()
        c.data_mode = "uploaded"
    c.workspace.reset()


# ---------- чтение ----------

def get_import(c: Container, import_id: str) -> dict[str, Any]:
    return c.imports.get(import_id).to_dict()


def list_imports(c: Container) -> list[dict[str, Any]]:
    return [job.to_dict(with_report=False) for job in c.imports.list()]
