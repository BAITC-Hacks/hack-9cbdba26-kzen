"""Схемы API для заказов."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import OrderLine, SupplierOrder


class CalcRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"supplier": "Systeme Electric", "lead_time_days": 45}]}
    )

    supplier: str | None = Field(default=None, description="Поставщик; пусто — все")
    category: str | None = None
    lead_time_days: int = Field(default=45, ge=1, le=365, description="Срок поставки")
    coverage_months: float = Field(
        default=1.0, ge=0, le=12, description="Целевой запас сверх срока поставки"
    )
    safety_factor: float = Field(default=0.2, ge=0, le=1, description="Страховой запас, доля")
    method: str = Field(
        default="smoothed", description="baseline — формула партнёра, smoothed — сглаживание"
    )


class ReasonSchema(BaseModel):
    label: str
    value: str


class OrderLineSchema(BaseModel):
    code: str
    name: str
    article: str
    supplier: str
    quantity: int
    urgency: str
    monthly_demand: float
    coverage_months: float
    free_stock: float
    in_transit: float
    moq: int
    method: str
    reasons: list[ReasonSchema]
    explanation: str

    @classmethod
    def from_domain(cls, line: OrderLine) -> OrderLineSchema:
        return cls(
            code=line.sku.code,
            name=line.sku.name,
            article=line.sku.article,
            supplier=line.sku.supplier,
            quantity=line.quantity,
            urgency=line.urgency.value,
            monthly_demand=line.monthly_demand,
            coverage_months=line.coverage_months,
            free_stock=line.sku.free_stock,
            in_transit=line.sku.in_transit,
            moq=line.sku.moq,
            method=line.method,
            reasons=[ReasonSchema(label=r.label, value=r.value) for r in line.reasons],
            explanation=line.explain(),
        )


class SupplierOrderSchema(BaseModel):
    supplier: str
    positions: int
    total_units: int
    critical_positions: int
    lines: list[OrderLineSchema]

    @classmethod
    def from_domain(cls, order: SupplierOrder) -> SupplierOrderSchema:
        return cls(
            supplier=order.supplier,
            positions=order.positions,
            total_units=order.total_units,
            critical_positions=order.critical_positions,
            lines=[OrderLineSchema.from_domain(x) for x in order.lines],
        )


class CalcResponse(BaseModel):
    suppliers: list[SupplierOrderSchema]
    total_positions: int
    method: str


class StatsResponse(BaseModel):
    skus: int
    suppliers: list[str]
    months: int
    stockout_share: float = Field(description="Доля месяцев без товара по всей номенклатуре")
    zero_stock_now: int = 0


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str


class SelfCheckResponse(BaseModel):
    """Проверки из пункта 7 ТЗ, прогоняемые вживую."""

    passed: int
    total: int
    checks: list[CheckResult]
