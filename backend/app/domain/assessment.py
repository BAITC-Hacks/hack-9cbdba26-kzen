"""Проверка готовности рекомендации: можно ли ей доверять без человека.

Правила, а не «confidence 0.73»: жюри и менеджер спросят, откуда 0.73,
а про правило «нет кода 1С» вопросов не бывает. Статус строки — самое
строгое из сработавших правил.

Флаги ставит код, а не LLM: наличие всплеска или пропуска — это факт
о данных, его нельзя «решать» языковой моделью.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.demand import CleanedDemand
from app.domain.entities import OrderLine, Sku
from app.domain.workflow import LineStatus

# Коды 1С у партнёра имеют вид 300200428_. Всё остальное (артикул поставщика
# на месте кода, «щт23054819») в 1С не загрузится — заказывать по нему нельзя.
ONEC_CODE = re.compile(r"\d{9}_")

MIN_HISTORY_MONTHS = 6
STOCKOUT_SHARE_LIMIT = 1 / 3     # треть истории без товара — компенсация уже догадка
LARGE_ORDER_MONTHS = 6.0         # заказ больше полугодового спроса — проверить руками
ONE_OFF_SHARE_LIMIT = 0.3        # выброс больше 30% истории — решение за человеком


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    message: str
    blocking: bool  # True → INSUFFICIENT_DATA, False → NEEDS_REVIEW


@dataclass(frozen=True, slots=True)
class Assessment:
    status: LineStatus
    issues: tuple[Issue, ...]

    @property
    def messages(self) -> tuple[str, ...]:
        return tuple(i.message for i in self.issues)

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.issues)


def data_issues(sku: Sku) -> list[Issue]:
    """Пробелы в данных, при которых считать количество нельзя или рискованно."""
    issues: list[Issue] = []
    if not ONEC_CODE.fullmatch(sku.code):
        issues.append(Issue(
            "no_1c_code",
            f"Код {sku.code!r} не похож на код 1С — позицию не сопоставить при загрузке",
            blocking=True,
        ))
    if not sku.history:
        issues.append(Issue("no_history", "Нет истории продаж", blocking=True))
    elif sku.months_of_history < MIN_HISTORY_MONTHS:
        issues.append(Issue(
            "short_history",
            f"История {sku.months_of_history} мес — меньше {MIN_HISTORY_MONTHS}, "
            "прогноз неустойчив",
            blocking=False,
        ))
    return issues


def one_off_share(sku: Sku, cleaned: CleanedDemand) -> float:
    total = sum(p.sold for p in sku.history if p.sold > 0)
    return cleaned.removed_bulk / total if total else 0.0


def assess(sku: Sku, line: OrderLine, cleaned: CleanedDemand) -> Assessment:
    issues = data_issues(sku)

    if sku.history and cleaned.stockout_months / len(sku.history) > STOCKOUT_SHARE_LIMIT:
        zero_stock_months = sum(point.stockout for point in sku.history)
        issues.append(Issue(
            "frequent_stockout",
            f"В {zero_stock_months} из {len(sku.history)} мес начальный остаток "
            "нулевой или не указан; "
            f"спрос восстановлен оценкой в {cleaned.stockout_months} мес",
            blocking=False,
        ))

    share = one_off_share(sku, cleaned)
    if share > ONE_OFF_SHARE_LIMIT:
        issues.append(Issue(
            "one_off_suspected",
            f"Исключено как разовые продажи {cleaned.removed_bulk:.0f} шт "
            f"({share:.0%} истории) — подтвердите, что это не новый регулярный клиент",
            blocking=False,
        ))

    if line.monthly_demand > 0 and line.quantity > line.monthly_demand * LARGE_ORDER_MONTHS:
        demand_text = f"{line.monthly_demand:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        issues.append(Issue(
            "large_order",
            f"Заказ {line.quantity} шт — больше {LARGE_ORDER_MONTHS:.0f} мес спроса "
            f"({demand_text} шт/мес)",
            blocking=False,
        ))

    if any(i.blocking for i in issues):
        status = LineStatus.INSUFFICIENT_DATA
    elif issues:
        status = LineStatus.NEEDS_REVIEW
    else:
        status = LineStatus.READY
    return Assessment(status, tuple(issues))
