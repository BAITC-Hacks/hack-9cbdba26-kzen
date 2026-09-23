"""Состояние рабочего места закупщика: роль, текущий заказ, настройки расчёта.

Одно на процесс, как и хранилище версий: демо идёт на одном воркере, а
авторизации в прототипе нет — роль переключается кнопкой. При нескольких
пользователях это состояние переезжает в сессию пользователя.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(slots=True)
class SupplierSetting:
    id: str
    name: str
    lead_time_days: int      # L: срок поставки
    review_days: int         # R: как часто пересматриваем заказ


def supplier_id(name: str) -> str:
    """Короткий id поставщика для фронта. Имена приходят из данных, id стабилен."""
    low = name.casefold()
    if "systeme" in low:
        return "SE"
    if "iek" in low or "иэк" in low:
        return "IEK"
    return name.upper()


def default_suppliers() -> dict[str, SupplierSetting]:
    # Сроков поставки в данных нет — это предположение, в интерфейсе оно так и подписано
    return {
        "SE": SupplierSetting("SE", "Systeme Electric", 30, 14),
        "IEK": SupplierSetting("IEK", "ИЭК", 35, 14),
    }


EXPORT_COLUMNS = [
    ("version", "Версия"), ("approved_at", "Утверждено"), ("supplier", "Поставщик"),
    ("code_1c", "Код 1С"), ("supplier_article", "Артикул поставщика"), ("name", "Наименование"),
    ("purchase_unit", "Ед. закупки"), ("recommended_qty", "Рекомендация"), ("final_qty", "Итог"),
    ("manual", "Ручная корректировка"), ("reason", "Причина"), ("price", "Цена"),
    ("cost", "Сумма"),
]


@dataclass
class Workspace:
    role: str = "manager"
    current_version: int | None = None
    calc_at: datetime | None = None
    calc_stale: bool = False
    warehouse_id: str = "ALM"
    category_filter: str | None = None
    calc_date: date | None = None
    suppliers: dict[str, SupplierSetting] = field(default_factory=default_suppliers)
    safety_factor: float = 0.2
    excess_months: float = 2.0
    export_format: str = "xlsx"
    export_separator: str = ";"
    export_encoding: str = "utf-8-bom"
    export_columns: dict[str, bool] = field(
        default_factory=lambda: {key: True for key, _ in EXPORT_COLUMNS}
    )
    # Настройки меняются из пула потоков FastAPI: запись под замком
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def supplier(self, name: str) -> SupplierSetting:
        sid = supplier_id(name)
        if sid not in self.suppliers:
            self.suppliers[sid] = SupplierSetting(sid, name, 30, 14)
        return self.suppliers[sid]

    def reset(self) -> None:
        with self.lock:
            self.current_version = None
            self.calc_at = None
            self.calc_stale = False
