"""Номенклатура в памяти.

Объёмы кейса маленькие (около 3000 артикулов × 36 месяцев), поэтому вся
номенклатура держится в словаре: расчёт по всему ассортименту укладывается
в доли секунды, и никакая база не нужна. Excel-парсер будет наполнять
этот же репозиторий — интерфейс не изменится.
"""

from __future__ import annotations

from typing import Any

from app.domain.entities import Sku


class MemorySkuRepository:
    def __init__(self, skus: list[Sku] | None = None) -> None:
        self._skus: dict[str, Sku] = {s.code: s for s in (skus or [])}

    @property
    def backend(self) -> str:
        return "memory"

    def add(self, sku: Sku) -> None:
        self._skus[sku.code] = sku

    def get(self, code: str) -> Sku | None:
        return self._skus.get(code)

    def list_skus(self, supplier: str | None = None, category: str | None = None) -> list[Sku]:
        items = list(self._skus.values())
        if supplier:
            items = [s for s in items if s.supplier == supplier]
        if category:
            items = [s for s in items if s.category == category]
        return items

    def suppliers(self) -> list[str]:
        return sorted({s.supplier for s in self._skus.values()})

    def stats(self) -> dict[str, Any]:
        items = list(self._skus.values())
        if not items:
            return {"skus": 0, "suppliers": [], "months": 0, "stockout_share": 0.0}

        total_months = sum(s.months_of_history for s in items)
        stockout_months = sum(1 for s in items for p in s.history if p.stockout)
        return {
            "skus": len(items),
            "suppliers": self.suppliers(),
            "months": max(s.months_of_history for s in items),
            "stockout_share": round(stockout_months / total_months, 4) if total_months else 0.0,
            "zero_stock_now": sum(1 for s in items if s.free_stock <= 0),
        }
