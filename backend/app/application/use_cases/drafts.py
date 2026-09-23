"""Сценарии закупщика вокруг версии расчёта.

Расчёт → версия → корректировки с причиной → утверждение → выгрузка.
Шага «отправить поставщику» нет намеренно: ТЗ запрещает отправку без человека,
а выгрузку менеджер сам загружает в 1С. Нет кода — нет риска.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.application.use_cases.replenishment import CalcParams, CalculateOrders
from app.domain.exceptions import ConflictError
from app.domain.workflow import OrderDraft, draft_from_lines

if TYPE_CHECKING:
    # Второй реализации хранилища пока нет, поэтому и отдельного порта нет:
    # появится Postgres — тогда вынесем Protocol в domain/ports.py.
    from app.infrastructure.storage.draft_store import MemoryDraftStore

# Колонки повторяют Excel-модель менеджера: «Код 1с» — ключ для загрузки в 1С,
# «Заказ» — та самая пустая колонка, которую сейчас заполняют руками.
EXPORT_COLUMNS = [
    "Поставщик",
    "Код 1с",
    "Артикул",
    "Номенклатура",
    "Кратность",
    "Рекомендация",
    "Заказ",
    "Причина корректировки",
    "Обоснование",
]


def _now() -> datetime:
    return datetime.now(UTC)


class CreateDraft:
    """Запустить расчёт и заморозить его результат в новую версию."""

    def __init__(self, calculator: CalculateOrders, store: MemoryDraftStore) -> None:
        self._calculator = calculator
        self._store = store

    def execute(
        self,
        *,
        params: CalcParams,
        supplier: str | None,
        category: str | None,
        method: str,
        author: str,
    ) -> OrderDraft:
        orders = self._calculator.execute(supplier=supplier, category=category, params=params)
        lines = [line for order in orders for line in order.lines]
        # today выкидываем: date не сериализуется в JSON, а в журнале он не нужен
        recorded = {k: v for k, v in asdict(params).items() if k != "today"}
        recorded |= {"supplier": supplier, "category": category, "method": method}
        at = _now()
        return self._store.create(
            lambda version: draft_from_lines(
                version, lines, params=recorded, author=author, at=at
            )
        )


class AdjustLine:
    def __init__(self, store: MemoryDraftStore) -> None:
        self._store = store

    def execute(
        self, version: int, code: str, *, quantity: int, reason: str, author: str
    ) -> OrderDraft:
        at = _now()
        return self._store.update(
            version,
            lambda d: d.adjust(code, quantity, reason=reason, author=author, at=at),
        )


class ApproveDraft:
    def __init__(self, store: MemoryDraftStore) -> None:
        self._store = store

    def execute(self, version: int, *, author: str, revision: int) -> OrderDraft:
        at = _now()
        return self._store.update(
            version, lambda d: d.approve(author=author, revision=revision, at=at)
        )


class ExportDraft:
    """Выгрузка согласованного списка для 1С: xlsx по умолчанию, CSV — запасной.

    Только утверждённая версия: выгрузка черновика — это ровно тот сценарий
    «ушло не то», от которого защищает утверждение.
    """

    def __init__(self, store: MemoryDraftStore) -> None:
        self._store = store

    def execute(
        self,
        version: int,
        *,
        supplier: str | None = None,
        fmt: str = "xlsx",
        warehouse: str = "Алматы",
    ) -> tuple[str, bytes]:
        draft = self._store.get(version)
        if not draft.approved:
            raise ConflictError(
                "Выгрузить можно только утверждённый заказ",
                details={"version": version, "status": draft.status.value},
            )
        if fmt == "xlsx":
            from app.infrastructure.export.onec_xlsx import render_purchase_order

            content = render_purchase_order(draft, warehouse=warehouse, supplier=supplier)
            return f"purchase_order_1c_v{draft.version}.xlsx", content

        buffer = io.StringIO()
        # «;» и BOM — иначе русский Excel откроет файл одной колонкой кракозябр
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(EXPORT_COLUMNS)
        for name, lines in sorted(draft.by_supplier().items()):
            if supplier and name != supplier:
                continue
            for line in lines:
                if not line.exportable:
                    continue
                writer.writerow([
                    line.supplier, line.code, line.article, line.name, line.moq,
                    line.recommended, line.quantity, line.adjustment_reason, line.explanation,
                ])

        filename = f"order_v{draft.version}_r{draft.revision}.csv"
        return filename, buffer.getvalue().encode("utf-8-sig")
