"""Рабочий процесс закупщика: версия расчёта → правки → утверждение.

Расчёт только рекомендует. Решение принимает менеджер: он правит количество
с обязательной причиной и утверждает список. Отправки поставщику в сервисе
нет вообще — это прямой запрет ТЗ, а не недоделка.

Черновик неизменяемый: каждая правка возвращает новый объект. Хранилище
подменяет ссылку целиком, поэтому читающий поток всегда видит согласованный
снимок и никогда — черновик «наполовину исправленный».
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.domain.entities import OrderLine
from app.domain.exceptions import ConflictError, DomainValidationError, NotFoundError


class DraftStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class DraftLine:
    """Строка заказа: рекомендация расчёта и решение менеджера рядом.

    recommended не меняется никогда — по нему видно, насколько человек
    отошёл от расчёта. quantity — то, что уйдёт в выгрузку.
    """

    code: str
    name: str
    supplier: str
    article: str
    moq: int
    urgency: str
    recommended: int
    quantity: int
    explanation: str
    adjustment_reason: str = ""
    adjusted_by: str = ""

    @property
    def adjusted(self) -> bool:
        return bool(self.adjustment_reason)


@dataclass(frozen=True, slots=True)
class DraftEvent:
    """Запись журнала: кто, когда и что сделал. Нужна, чтобы спор
    «кто поставил 500 штук» решался за секунду, а не по памяти."""

    at: datetime
    author: str
    action: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class OrderDraft:
    """Одна версия расчёта со всеми правками менеджера.

    revision растёт на каждое изменение. Утверждение принимает номер ревизии,
    которую человек видел на экране: если между просмотром и нажатием
    кто-то поправил строку, утверждать «не то» нельзя.
    """

    version: int
    created_at: datetime
    params: dict[str, Any]
    lines: dict[str, DraftLine]
    status: DraftStatus = DraftStatus.DRAFT
    revision: int = 1
    approved_by: str = ""
    approved_at: datetime | None = None
    events: tuple[DraftEvent, ...] = field(default_factory=tuple)

    @property
    def approved(self) -> bool:
        return self.status is DraftStatus.APPROVED

    def line(self, code: str) -> DraftLine:
        found = self.lines.get(code)
        if found is None:
            raise NotFoundError(
                f"Артикула {code!r} нет в версии {self.version}",
                details={"version": self.version, "code": code},
            )
        return found

    def adjust(
        self, code: str, quantity: int, *, reason: str, author: str, at: datetime
    ) -> OrderDraft:
        """Ручная корректировка количества.

        Причина обязательна: без неё через месяц невозможно понять, почему
        заказ разошёлся с расчётом, и нельзя улучшать алгоритм по правкам.
        Любая правка утверждённого заказа снимает утверждение — иначе в 1С
        уйдёт список, который никто в таком виде не согласовывал.
        """
        reason = reason.strip()
        if not reason:
            raise DomainValidationError("Укажите причину корректировки", details={"code": code})
        if quantity < 0:
            raise DomainValidationError(
                "Количество не может быть отрицательным", details={"quantity": quantity}
            )

        old = self.line(code)
        new_line = replace(old, quantity=quantity, adjustment_reason=reason, adjusted_by=author)
        events = [
            DraftEvent(at, author, "adjust", f"{code}: {old.quantity} → {quantity} ({reason})")
        ]
        if self.approved:
            events.append(
                DraftEvent(at, author, "approval_reset", "заказ изменён после утверждения")
            )

        return replace(
            self,
            lines={**self.lines, code: new_line},
            status=DraftStatus.DRAFT,
            revision=self.revision + 1,
            approved_by="",
            approved_at=None,
            events=self.events + tuple(events),
        )

    def approve(self, *, author: str, revision: int, at: datetime) -> OrderDraft:
        if not author.strip():
            raise DomainValidationError("Укажите, кто утверждает заказ")
        if revision != self.revision:
            raise ConflictError(
                "Заказ изменился с момента просмотра, обновите список перед утверждением",
                details={"expected": revision, "current": self.revision},
            )
        if self.approved:
            raise ConflictError(
                "Версия уже утверждена",
                details={"approved_by": self.approved_by, "version": self.version},
            )

        return replace(
            self,
            status=DraftStatus.APPROVED,
            approved_by=author,
            approved_at=at,
            events=(*self.events, DraftEvent(at, author, "approve", f"ревизия {self.revision}")),
        )

    def by_supplier(self) -> dict[str, list[DraftLine]]:
        grouped: dict[str, list[DraftLine]] = {}
        for line in self.lines.values():
            grouped.setdefault(line.supplier, []).append(line)
        return grouped


def draft_from_lines(
    version: int,
    lines: list[OrderLine],
    *,
    params: dict[str, Any],
    author: str,
    at: datetime,
) -> OrderDraft:
    """Заморозить результат расчёта в версию.

    Снимок нужен, потому что данные и алгоритм меняются: утверждённый заказ
    должен остаться ровно таким, каким его видел менеджер, а не пересчитываться
    при каждом открытии.
    """
    draft_lines = {
        line.sku.code: DraftLine(
            code=line.sku.code,
            name=line.sku.name,
            supplier=line.sku.supplier,
            article=line.sku.article,
            moq=line.sku.moq,
            urgency=line.urgency.value,
            recommended=line.quantity,
            quantity=line.quantity,
            explanation=line.explain(),
        )
        for line in lines
    }
    return OrderDraft(
        version=version,
        created_at=at,
        params=dict(params),
        lines=draft_lines,
        events=(DraftEvent(at, author, "calculate", f"{len(draft_lines)} позиций"),),
    )
