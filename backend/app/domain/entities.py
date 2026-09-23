"""Сущности предметной области: закуп и пополнение склада.

Чистый Python: ни FastAPI, ни pandas. Язык сущностей — язык менеджера отдела
закупа, а не разработчика: артикул, остаток, товар в пути, кратность, заказ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class Urgency(StrEnum):
    """Срочность позиции. Считается от запаса в месяцах до прихода товара."""

    CRITICAL = "critical"  # товара нет или не хватит до поставки
    HIGH = "high"          # хватит впритык
    NORMAL = "normal"      # обычное пополнение
    NONE = "none"          # заказывать не нужно


@dataclass(frozen=True, slots=True)
class MonthPoint:
    """Один месяц истории по артикулу.

    sold — фактические продажи в штуках, stock_start — остаток на начало месяца.
    Провал наличия выводится из остатка: отдельного файла со stockout партнёр не даёт.
    """

    month: date
    sold: float
    stock_start: float = 0.0
    stock_known: bool = True

    @property
    def stockout(self) -> bool:
        """Месяц без товара: продавать было нечего, спрос не виден в продажах."""
        return self.stock_known and self.stock_start <= 0


@dataclass(frozen=True, slots=True)
class BulkOrderEvent:
    """Разовая крупная отгрузка, подтверждённая транзакциями.

    ID клиента в выгрузках нет, поэтому номер накладной — проверяемый proxy
    клиентского заказа. regular_quantity — типичный размер накладной по позиции.
    """

    month: date
    invoice: str
    quantity: float
    regular_quantity: float

    @property
    def excess(self) -> float:
        return max(0.0, self.quantity - self.regular_quantity)


@dataclass(frozen=True, slots=True)
class Sku:
    """Артикул со всем, что нужно для расчёта заказа."""

    code: str                     # Номенклатура.Код / Код 1с — ключ связи между файлами
    name: str
    supplier: str
    article: str = ""             # артикул поставщика
    category: str = ""
    unit: str = "шт"
    moq: int = 1                  # кратность отгрузки; 0 в данных трактуем как 1
    on_hand_stock: float | None = None
    reserved_stock: float = 0.0
    free_stock: float = 0.0       # остаток минус зарезервировано
    in_transit: float = 0.0       # товар в пути по открытым заказам
    # Справочника сроков поставки партнёр не дал, поэтому по умолчанию None:
    # срок берётся из параметров расчёта. Если справочник появится,
    # значение на артикуле переопределит общий параметр.
    lead_time_days: int | None = None
    history: tuple[MonthPoint, ...] = ()
    bulk_orders: tuple[BulkOrderEvent, ...] = ()

    @property
    def months_of_history(self) -> int:
        return len(self.history)


@dataclass(frozen=True, slots=True)
class ReasonPart:
    """Компонент обоснования: что учли и как это повлияло на количество.

    Каждая часть приходит из расчёта. Текст собирается из этих частей,
    поэтому в обосновании не может появиться выдуманное число.
    """

    label: str
    value: str
    effect: float = 0.0  # вклад в итоговое количество, штук


@dataclass(frozen=True, slots=True)
class OrderLine:
    """Строка рекомендованного заказа."""

    sku: Sku
    quantity: int
    urgency: Urgency
    monthly_demand: float
    coverage_months: float          # на сколько месяцев хватит текущего запаса
    reasons: list[ReasonPart] = field(default_factory=list)
    method: str = "baseline"

    @property
    def needed(self) -> bool:
        return self.quantity > 0

    def explain(self) -> str:
        """Обоснование одной строкой — то, что видит менеджер в таблице."""
        parts = [f"{r.label}: {r.value}" for r in self.reasons]
        return "; ".join(parts) + f" → заказать {self.quantity} {self.sku.unit}"


@dataclass(frozen=True, slots=True)
class SupplierOrder:
    """Заказ по одному поставщику. Группировка — требование ТЗ."""

    supplier: str
    lines: list[OrderLine] = field(default_factory=list)

    @property
    def positions(self) -> int:
        return len(self.lines)

    @property
    def total_units(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def critical_positions(self) -> int:
        return sum(1 for line in self.lines if line.urgency is Urgency.CRITICAL)


@dataclass(frozen=True, slots=True)
class Forecast:
    """Прогноз спроса с разложением на компоненты — нужен для обоснования."""

    monthly_demand: float
    base_demand: float
    growth_factor: float = 1.0
    seasonality_factor: float = 1.0
    method: str = "baseline"


def urgency_for(coverage_months: float, lead_time_months: float) -> Urgency:
    """Срочность: хватит ли текущего запаса до прихода следующей поставки.

    Правило бизнеса, а не свойство прогноза, поэтому живёт в домене.
    """
    if coverage_months <= 0 or coverage_months < lead_time_months:
        return Urgency.CRITICAL
    if coverage_months < lead_time_months * 1.5:
        return Urgency.HIGH
    return Urgency.NORMAL
