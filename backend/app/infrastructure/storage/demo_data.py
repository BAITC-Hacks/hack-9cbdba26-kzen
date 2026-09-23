"""Демо-набор: реальные коды и названия из выгрузок партнёра, синтетические числа.

Зачем. Пока парсер Excel не готов, фронту и демо нужны живые экраны. Каждый
артикул закладывает один сценарий из ТЗ, чтобы на защите было что показать:
сезонность, stockout, разовая сделка, товар в пути, нет кода 1С, короткая история.

Честность. В шапке интерфейса режим помечается как demo: числа по позициям
синтетические, и выдавать их за данные партнёра нельзя.
"""

from __future__ import annotations

from datetime import date

from app.domain.entities import MonthPoint, Sku
from app.infrastructure.storage.memory_repo import MemorySkuRepository

SE = "Systeme Electric"
IEK = "IEK"
# Январь 2024 — август 2026: полные месяцы до даты среза данных 22.09.2026
MONTHS = 32


def _history(sold: list[float], stock: list[float] | None = None) -> tuple[MonthPoint, ...]:
    stock = stock or [500.0] * len(sold)
    start = MONTHS - len(sold)
    return tuple(
        MonthPoint(month=date(2024 + (start + i) // 12, (start + i) % 12 + 1, 1),
                   sold=s, stock_start=st)
        for i, (s, st) in enumerate(zip(sold, stock, strict=True))
    )


def _flat(level: float, n: int = MONTHS) -> list[float]:
    # Небольшая детерминированная «пила», чтобы график не был линейкой
    return [level + (i % 3 - 1) * level * 0.08 for i in range(n)]


def _seasonal(level: float) -> list[float]:
    # Летний пик (электромонтаж сезонный): май–август ×1.6
    return [level * (1.6 if (i % 12) in (4, 5, 6, 7) else 0.8) for i in range(MONTHS)]


def _growing(start: float, monthly: float) -> list[float]:
    return [start * (1 + monthly) ** i for i in range(MONTHS)]


def build_demo_repository() -> MemorySkuRepository:
    one_off = _flat(55)
    one_off[26] = 535.0  # разовая сделка на 480 шт сверх обычных 55 — март 2026

    stockout_stock = [300.0] * MONTHS
    stockout_sales = _flat(70)
    for m in (20, 21, 22, 23):  # сентябрь–декабрь 2025 товара не было
        stockout_stock[m] = 0.0
        stockout_sales[m] = 6.0

    skus = [
        Sku(code="300200428_", name="A398 Роз. с з/к 16А с/у б/шт AtlasDesign", supplier=SE,
            article="ATN000343", category="1", moq=12, free_stock=35.0, in_transit=25.0,
            history=_history(_flat(64))),
        Sku(code="300200430_", name="А384 Выкл 1 кл 10А с/у AtlasDesign", supplier=SE,
            article="ATN000312", category="2", moq=1, free_stock=40.0, in_transit=200.0,
            history=_history(_flat(45))),
        Sku(code="300200588_", name="А3844 Выкл 1 кл 10А механизм AtlasDesign", supplier=SE,
            article="ATN000311", category="1", moq=10, free_stock=60.0,
            history=_history(_seasonal(90))),
        Sku(code="300200442_", name="A404 USB розетка 2 порта AtlasDesign", supplier=SE,
            article="ATN000333", category="3", moq=1, free_stock=20.0,
            history=_history(one_off)),
        Sku(code="300200635_", name="AtlasDesign Розетка 1-я алюминий", supplier=SE,
            article="ATN000356", category="1", moq=6, free_stock=0.0,
            history=_history(stockout_sales, stockout_stock)),
        Sku(code="ATN000330", name="SO + USB розетка A+A, 5В/2,4А", supplier=SE,
            article="ATN000330", category="7", free_stock=12.0,
            history=_history(_flat(18))),
        Sku(code="300200701_", name="AtlasDesign Рамка 3-постовая", supplier=SE,
            article="ATN000503", category="3", moq=1, free_stock=5.0,
            history=_history([4.0, 9.0, 7.0, 12.0])),
        Sku(code="300200445_", name="А409 Рамка 5-постовая AtlasDesign", supplier=SE,
            article="ATN000509", category="3", moq=1, free_stock=900.0,
            history=_history(_flat(30))),
        Sku(code="200400085_", name="F/UTP (24 AWG), кат.5Е экр., 4х2х0,51, PVC", supplier=IEK,
            article="LC1-C5E04-311", category="", moq=305, free_stock=4200.0,
            in_transit=6100.0, history=_history(_flat(6200))),
        Sku(code="200400050_", name="Миниконтактор МКИ-10610 6А 230В/АС3 1НО", supplier=IEK,
            article="MKK10-06-10", category="", moq=10, free_stock=8.0,
            history=_history(_flat(22))),
        Sku(code="120100031_", name="Механизм блокировки для ВА88-35/37", supplier=IEK,
            article="SVA40D-MB", category="", moq=4, free_stock=10.0,
            history=_history(_growing(10, 0.04))),
        Sku(code="200400104_", name="U/UTP кат.6 4х2х23AWG solid LSZH", supplier=IEK,
            article="LC1-C604-111", category="", moq=305, free_stock=0.0, in_transit=0.0,
            history=_history(_flat(1500))),
    ]
    return MemorySkuRepository(skus)
