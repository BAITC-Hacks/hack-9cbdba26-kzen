"""Схемы API версий расчёта и утверждения заказа."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.orders import CalcRequest
from app.domain.workflow import DraftEvent, DraftLine, OrderDraft


class CreateDraftRequest(CalcRequest):
    author: str = Field(default="менеджер", max_length=100, description="Кто запустил расчёт")


class AdjustRequest(BaseModel):
    quantity: int = Field(ge=0, description="Новое количество к заказу")
    reason: str = Field(min_length=1, max_length=500, description="Почему отличается от расчёта")
    author: str = Field(default="менеджер", max_length=100)


class ApproveRequest(BaseModel):
    author: str = Field(min_length=1, max_length=100)
    revision: int = Field(ge=1, description="Ревизия, которую менеджер видел на экране")


class DraftLineSchema(BaseModel):
    code: str
    name: str
    article: str
    supplier: str
    moq: int
    urgency: str
    recommended: int
    quantity: int
    adjusted: bool
    adjustment_reason: str
    adjusted_by: str
    explanation: str

    @classmethod
    def from_domain(cls, line: DraftLine) -> DraftLineSchema:
        return cls(
            code=line.code, name=line.name, article=line.article, supplier=line.supplier,
            moq=line.moq, urgency=line.urgency, recommended=line.recommended,
            quantity=line.quantity, adjusted=line.adjusted,
            adjustment_reason=line.adjustment_reason, adjusted_by=line.adjusted_by,
            explanation=line.explanation,
        )


class DraftSupplierSchema(BaseModel):
    supplier: str
    positions: int
    total_units: int
    lines: list[DraftLineSchema]


class DraftEventSchema(BaseModel):
    at: datetime
    author: str
    action: str
    detail: str

    @classmethod
    def from_domain(cls, event: DraftEvent) -> DraftEventSchema:
        return cls(at=event.at, author=event.author, action=event.action, detail=event.detail)


class DraftSummarySchema(BaseModel):
    version: int
    created_at: datetime
    status: str
    revision: int
    approved_by: str
    approved_at: datetime | None
    positions: int
    adjusted_positions: int
    total_units: int
    params: dict[str, Any]
    # Явно в ответе, чтобы интерфейс и жюри видели: сервис ничего не отправляет сам
    sent_to_supplier: bool = False

    @classmethod
    def from_domain(cls, draft: OrderDraft) -> DraftSummarySchema:
        lines = draft.lines.values()
        return cls(
            version=draft.version,
            created_at=draft.created_at,
            status=draft.status.value,
            revision=draft.revision,
            approved_by=draft.approved_by,
            approved_at=draft.approved_at,
            positions=len(draft.lines),
            adjusted_positions=sum(1 for x in lines if x.adjusted),
            total_units=sum(x.quantity for x in lines),
            params=draft.params,
        )


class DraftSchema(DraftSummarySchema):
    suppliers: list[DraftSupplierSchema]
    events: list[DraftEventSchema]

    @classmethod
    def from_domain(cls, draft: OrderDraft) -> DraftSchema:
        summary = DraftSummarySchema.from_domain(draft)
        suppliers = [
            DraftSupplierSchema(
                supplier=name,
                positions=len(lines),
                total_units=sum(x.quantity for x in lines),
                lines=[DraftLineSchema.from_domain(x) for x in lines],
            )
            for name, lines in draft.by_supplier().items()
        ]
        return cls(
            **summary.model_dump(),
            suppliers=suppliers,
            events=[DraftEventSchema.from_domain(e) for e in draft.events],
        )
