"""Агент закупщика: цель → инструменты → наблюдения → ветвления → версия на утверждение.

Устройство — классический цикл агента, а не «кнопка + красивый текст»:

    очередь действий → вызвать инструмент → записать наблюдение в trace
    → политика смотрит на наблюдение и решает, какие проверки добавить
    → повторять, пока очередь не пуста или не кончился бюджет шагов

Что решает политика, а что нет. Флаги (всплеск, пропуск данных, крупный заказ)
ставит код в domain/assessment.py — это факты. Политика решает, какую
дополнительную проверку запустить по флагу. Количество считает только
CalculateOrders, человек утверждает. Инструмента «отправить поставщику» нет.

Сейчас политика на правилах (RulesPolicy). LLM-политика встанет рядом с тем же
интерфейсом follow_ups и теми же инструментами; правила останутся запасным
вариантом, когда LLM недоступен. Демо не может упасть из-за внешнего API.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.application.use_cases.replenishment import CalcParams, CalculateOrders
from app.domain.assessment import (
    ONE_OFF_SHARE_LIMIT,
    Assessment,
    assess,
    data_issues,
    one_off_share,
)
from app.domain.demand import CleanedDemand, prepare
from app.domain.entities import OrderLine, Sku
from app.domain.exceptions import NotFoundError
from app.domain.workflow import (
    LineStatus,
    OrderDraft,
    TraceEvent,
    draft_from_lines,
    draft_line,
)

if TYPE_CHECKING:
    from app.infrastructure.storage.draft_store import MemoryDraftStore

# Бюджет — защита от зацикливания, особенно когда политикой станет LLM.
MAX_STEPS = 60
# Глубокий разбор показывается по самым крупным позициям: статус получают все,
# но лента из 500 одинаковых шагов бесполезна менеджеру.
MAX_DEEP_REVIEWS = 10


@dataclass(frozen=True, slots=True)
class Action:
    tool: str
    sku: str = ""


@dataclass(slots=True)
class AgentState:
    """Рабочая память одного запуска. Живёт только внутри execute."""

    skus: dict[str, Sku] = field(default_factory=dict)
    lines: dict[str, OrderLine] = field(default_factory=dict)
    cleaned: dict[str, CleanedDemand] = field(default_factory=dict)
    assessments: dict[str, Assessment] = field(default_factory=dict)
    trace: list[TraceEvent] = field(default_factory=list)

    def log(self, type_: str, status: str, title: str, *, tool: str = "", sku: str = "",
            facts: dict[str, Any] | None = None) -> None:
        self.trace.append(
            TraceEvent(len(self.trace) + 1, type_, status, title, tool, sku, facts or {})
        )


class ProcurementTools:
    """Инструменты агента — тонкие обёртки над расчётом и данными.

    Каждый возвращает наблюдение (dict с фактами). Ни один не выдумывает
    число: всё берётся из репозитория или из расчёта.
    """

    def __init__(self, calculator: CalculateOrders, params: CalcParams) -> None:
        self._calc = calculator
        self._params = params

    def inspect_data_quality(self, state: AgentState) -> dict[str, Any]:
        blocked: dict[str, list[str]] = {}
        for code, sku in state.skus.items():
            issues = [i for i in data_issues(sku) if i.blocking]
            if issues:
                blocked[code] = [i.message for i in issues]
        return {"skus": len(state.skus), "insufficient_data": len(blocked),
                "examples": dict(list(blocked.items())[:5])}

    def calculate_orders(self, state: AgentState) -> dict[str, Any]:
        for code, sku in state.skus.items():
            cleaned = prepare(sku.history)
            line = self._calc.calculate_line(sku, self._params)
            state.cleaned[code] = cleaned
            state.lines[code] = line
            state.assessments[code] = assess(sku, line, cleaned)
        needed = [x for x in state.lines.values() if x.needed]
        return {"positions": len(needed), "units": sum(x.quantity for x in needed)}

    def screen_recommendations(self, state: AgentState) -> dict[str, Any]:
        flagged: dict[str, list[str]] = {}
        for code, a in state.assessments.items():
            for issue in a.issues:
                if not issue.blocking:
                    flagged.setdefault(issue.code, []).append(code)
        return {kind: len(codes) for kind, codes in flagged.items()} | {"_flagged": flagged}

    def review_one_off(self, state: AgentState, code: str) -> dict[str, Any]:
        sku, cleaned = state.skus[code], state.cleaned[code]
        return {
            "removed_units": round(cleaned.removed_bulk),
            "share_of_history": round(one_off_share(sku, cleaned), 3),
            "months": [m.isoformat() for m in cleaned.bulk_months],
        }

    def check_supplier_constraints(self, state: AgentState, code: str) -> dict[str, Any]:
        sku, line = state.skus[code], state.lines[code]
        moq = max(1, sku.moq)
        return {
            "quantity": line.quantity,
            "moq": moq,
            "multiple_ok": line.quantity % moq == 0,
            "monthly_demand": line.monthly_demand,
            "months_of_demand": round(line.quantity / line.monthly_demand, 1)
            if line.monthly_demand else None,
        }


class RulesPolicy:
    """Какие проверки добавить после наблюдения. Детерминированно и объяснимо."""

    def follow_ups(self, action: Action, observation: dict[str, Any],
                   state: AgentState) -> list[Action]:
        if action.tool != "screen_recommendations":
            return []

        flagged: dict[str, list[str]] = observation.get("_flagged", {})
        # Сначала самые дорогие ошибки: крупные заказы и крупные выбросы
        suspicious = sorted(
            set(flagged.get("large_order", [])) | set(flagged.get("one_off_suspected", [])),
            key=lambda c: -state.lines[c].quantity,
        )[:MAX_DEEP_REVIEWS]

        actions: list[Action] = []
        for code in suspicious:
            actions.append(Action("review_one_off", code))
            if code in flagged.get("large_order", []):
                actions.append(Action("check_supplier_constraints", code))
        return actions


TITLES = {
    "inspect_data_quality": "Проверено качество данных",
    "calculate_orders": "Рассчитана потребность",
    "screen_recommendations": "Рекомендации проверены на аномалии",
    "review_one_off": "Разобрана история продаж",
    "check_supplier_constraints": "Проверены ограничения поставщика",
}


class RunProcurementAgent:
    def __init__(self, calculator: CalculateOrders, repo, store: MemoryDraftStore,
                 policy: RulesPolicy | None = None) -> None:
        self._calc = calculator
        self._repo = repo
        self._store = store
        self._policy = policy or RulesPolicy()

    def execute(self, *, goal: str, supplier: str | None, category: str | None,
                params: CalcParams, method: str, author: str) -> OrderDraft:
        state = AgentState(skus={s.code: s for s in self._repo.list_skus(supplier, category)})
        tools = ProcurementTools(self._calc, params)
        state.log("decision", "ok", f"Цель: {goal}",
                  facts={"supplier": supplier, "category": category, "skus": len(state.skus)})

        queue = deque([Action("inspect_data_quality"), Action("calculate_orders"),
                       Action("screen_recommendations")])
        steps = 0
        while queue and steps < MAX_STEPS:
            action = queue.popleft()
            steps += 1
            observation = self._run(tools, action, state)
            public = {k: v for k, v in observation.items() if not k.startswith("_")}
            state.log("tool_call", _status(action, observation),
                      TITLES.get(action.tool, action.tool),
                      tool=action.tool, sku=action.sku, facts=public)
            queue.extend(self._policy.follow_ups(action, observation, state))

        if queue:
            state.log("flag", "warning", "Бюджет шагов исчерпан, часть проверок не выполнена",
                      facts={"skipped": len(queue)})

        # В версию попадают позиции к заказу и позиции без решения:
        # «недостаточно данных» нельзя молча превращать в ноль и прятать.
        codes = [c for c, x in state.lines.items()
                 if x.needed or state.assessments[c].status is not LineStatus.READY]
        lines = [state.lines[c] for c in codes]
        counts = {s.value: 0 for s in LineStatus}
        for c in codes:
            counts[state.assessments[c].status.value] += 1
        state.log("decision", "ok", "Рекомендации сформированы", facts=counts)
        state.log("awaiting_approval", "waiting", "Ожидает утверждения менеджером")

        recorded = {k: v for k, v in asdict(params).items() if k != "today"}
        recorded |= {"supplier": supplier, "category": category, "method": method, "goal": goal}
        assessments = {c: (a.status, a.messages) for c, a in state.assessments.items()}
        at = datetime.now(UTC)
        return self._store.create(lambda v: draft_from_lines(
            v, lines, params=recorded, author=author, at=at,
            assessments=assessments, trace=tuple(state.trace),
        ))

    @staticmethod
    def _run(tools: ProcurementTools, action: Action, state: AgentState) -> dict[str, Any]:
        method = getattr(tools, action.tool)
        return method(state, action.sku) if action.sku else method(state)


class ReplanInboundDelay:
    """What-if: поставка задерживается и не успевает к нашей дате прихода.

    Агент не правит старую версию. Он получает новый факт, пересчитывает позицию
    тем же расчётом и, если количество изменилось, создаёт новую версию.
    Утверждение старой версии к новым фактам не относится — нужно новое.
    """

    def __init__(self, calculator_for: Callable[[str], CalculateOrders], repo,
                 store: MemoryDraftStore) -> None:
        self._calculator_for = calculator_for
        self._repo = repo
        self._store = store

    def execute(self, version: int, code: str, *, delayed_quantity: float,
                new_eta: str, author: str) -> tuple[OrderDraft, bool]:
        draft = self._store.get(version)
        sku = self._repo.get(code)
        if sku is None:
            raise NotFoundError(f"Артикул {code!r} не найден", details={"code": code})

        state = AgentState()
        old = draft.lines.get(code)
        old_qty = old.quantity if old else 0
        delayed = min(delayed_quantity, sku.in_transit)
        state.log("observation", "warning", "Поставка задерживается", sku=code,
                  facts={"in_transit": sku.in_transit, "delayed": delayed, "new_eta": new_eta})

        # Задержанная партия не придёт до нашей поставки — в расчёте её нет.
        # Когда у Sku появятся партии с ETA, здесь будет сдвиг даты, а не вычитание.
        shifted = replace(sku, in_transit=sku.in_transit - delayed)
        state.log("tool_call", "ok", "Проверен товар в пути", tool="get_inbound", sku=code,
                  facts={"counted_before": sku.in_transit, "counted_now": shifted.in_transit})

        params = _params_from(draft.params)
        calculator = self._calculator_for(draft.params.get("method", "smoothed"))
        line = calculator.calculate_line(shifted, params)
        cleaned = prepare(shifted.history)
        assessment = assess(shifted, line, cleaned)
        state.log("tool_call", "ok", "Заказ пересчитан", tool="calculate_reorder_quantity",
                  sku=code, facts={"before": old_qty, "after": line.quantity,
                                   "explanation": line.explain()})

        if line.quantity == old_qty:
            state.log("decision", "ok", "Задержка не меняет заказ: остатка хватает", sku=code,
                      facts={"quantity": line.quantity})
            return draft, False

        if draft.approved:
            state.log("flag", "warning", f"Утверждение версии {draft.version} больше не актуально",
                      facts={"approved_by": draft.approved_by})
        state.log("decision", "ok", f"Заказ изменён: {old_qty} → {line.quantity}", sku=code,
                  facts={"before": old_qty, "after": line.quantity})
        state.log("awaiting_approval", "waiting", "Новая версия ожидает утверждения")

        new_line = draft_line(line, assessment.status, assessment.messages)
        reason = f"поставка {delayed:.0f} шт по {code} задерживается до {new_eta}"
        at = datetime.now(UTC)
        derived = self._store.create(lambda v: draft.derive(
            v, new_line, reason=reason, author=author, at=at, trace=tuple(state.trace)
        ))
        return derived, True


def _params_from(recorded: dict[str, Any]) -> CalcParams:
    """Пересчёт идёт с теми же параметрами, что и исходная версия, иначе
    разница в заказе смешает эффект задержки с эффектом других настроек."""
    names = set(CalcParams.__slots__) - {"today"}
    return CalcParams(**{k: v for k, v in recorded.items() if k in names})


def _status(action: Action, observation: dict[str, Any]) -> str:
    if action.tool == "inspect_data_quality" and observation.get("insufficient_data"):
        return "warning"
    if action.tool == "screen_recommendations" and observation.get("_flagged"):
        return "warning"
    share = observation.get("share_of_history", 0)
    if action.tool == "review_one_off" and share > ONE_OFF_SHARE_LIMIT:
        return "warning"
    if action.tool == "check_supplier_constraints" and not observation.get("multiple_ok", True):
        return "blocked"
    return "ok"
