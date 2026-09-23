"""Объяснение без внешних сервисов.

Вторая реализация порта, и она не «запасная на всякий случай», а рабочая:
на демо без интернета, в тестах и когда LLM не нужен. Текст суховат,
зато все числа гарантированно из расчёта.
"""

from __future__ import annotations

from typing import Any

URGENCY_WORDS = {
    "critical": "закупить срочно",
    "high": "закупить в ближайшее время",
    "normal": "плановое пополнение",
    "none": "заказ не требуется",
}


class TemplateNarrator:
    @property
    def backend(self) -> str:
        return "template"

    def narrate(self, context: dict[str, Any]) -> str:
        action = URGENCY_WORDS.get(str(context.get("urgency")), "пополнение")
        head = (
            f"{context.get('name', 'Позиция')}: {action}, "
            f"{context.get('quantity', 0)} шт."
        )
        demand = context.get("monthly_demand")
        coverage = context.get("coverage_months")
        if demand:
            head += f" Спрос {demand} шт/мес, текущего запаса хватит на {coverage} мес."

        reasons = context.get("reasons") or []
        if reasons:
            head += " Учтено: " + "; ".join(
                f"{r.get('label')} — {r.get('value')}" for r in reasons[:4]
            ) + "."
        return head
