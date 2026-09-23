"""Сценарии экранов закупщика в форме, которую ждёт фронт (FRONTEND_DATA.md).

Слой-переводчик: домен и расчёт не меняются под интерфейс. Здесь правила
отображения, которые фронт по контракту считать не должен: статус позиции,
срочность, избыточный запас, права на кнопки, что попадёт в экспорт.

Числа не выдумываются: всё берётся из версии расчёта (снимка) и данных.
Чего в данных нет — даты поступления, цены, резерва — отдаётся как null.
"""

from __future__ import annotations

import statistics
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from app.application.use_cases.agent import RunProcurementAgent
from app.application.use_cases.replenishment import CalcParams, CalculateOrders
from app.application.use_cases.selfcheck import RunSelfChecks
from app.application.use_cases.workspace import EXPORT_COLUMNS, supplier_id
from app.domain.assessment import assess
from app.domain.demand import prepare
from app.domain.entities import MonthPoint, Sku
from app.domain.exceptions import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
)
from app.domain.workflow import (
    DraftEvent,
    DraftLine,
    DraftStatus,
    LineStatus,
    OrderDraft,
    draft_line,
)

if TYPE_CHECKING:
    from app.core.container import Container

ALMATY = timezone(timedelta(hours=5))
METHOD = "smoothed"
ROLE_NAMES = {"manager": "Менеджер закупа", "head": "Руководитель закупок"}
MONTH_LABELS = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
STATUS_TEXT = {"draft": "черновик", "submitted": "на согласовании", "approved": "утверждена"}
# Значение из контракта фронта → то, что реально пишется в файл
SEPARATORS = {";": ";", ",": ",", "tab": "\t"}
# utf-8-bom — чтобы Excel сам узнал кодировку; cp1251 — для старых загрузок в 1С
ENCODINGS = {"utf-8-bom": "utf-8-sig", "cp1251": "cp1251"}


# ---------- общие помощники ----------

def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(ALMATY).isoformat(timespec="seconds") if dt else None


def _sku_id(supplier: str, code: str) -> str:
    return f"{supplier_id(supplier)}:{code}"


def _parse_sku_id(sku_id: str) -> str:
    """Возвращает код 1С. Префикс поставщика нужен фронту для стабильного ключа."""
    return sku_id.split(":", 1)[1] if ":" in sku_id else sku_id


def _calculator(c: Container) -> CalculateOrders:
    return CalculateOrders(c.repo, c.forecasters[METHOD])


def _params(c: Container, supplier: str, *, delay_days: int = 0) -> CalcParams:
    s = c.workspace.supplier(supplier)
    return CalcParams(
        lead_time_days=s.lead_time_days + delay_days,
        coverage_months=s.review_days / 30,
        safety_factor=c.workspace.safety_factor,
        today=c.workspace.calc_date,
    )


def current_draft(c: Container) -> OrderDraft | None:
    v = c.workspace.current_version
    return c.drafts.get(v) if v is not None else None


def _require_draft(c: Container) -> OrderDraft:
    draft = current_draft(c)
    if draft is None:
        raise ConflictError("Расчёт ещё не запускался", code="NO_CALCULATION")
    return draft


def _check_version(draft: OrderDraft, payload: dict[str, Any]) -> int:
    """Фронт присылает версию, которую видит; ревизия уточняет правки внутри версии."""
    version = payload.get("order_version")
    if version is not None and version != draft.version:
        raise ConflictError(
            "Список изменён другим пользователем", code="VERSION_CONFLICT",
            details={"expected": version, "current": draft.version},
        )
    return payload.get("order_revision") or draft.revision


# ---------- шапка и сессия ----------

def header(c: Container) -> dict[str, Any]:
    ws, draft = c.workspace, current_draft(c)
    demo = c.data_mode == "demo"
    return {
        "warehouse": {"id": ws.warehouse_id, "name": "Алматы"},
        "category_filter": ws.category_filter,
        "calc_date": (ws.calc_date or date.today()).isoformat(),
        "data_cut_date": "2026-09-22",
        "calc_at": _iso(ws.calc_at),
        "calc_stale": ws.calc_stale,
        "snapshot_age_days": None,
        "snapshot_stale": False,
        "what_if_active": False,
        "data_mode": c.data_mode,
        "data_mode_text": (
            "Коды и названия — из выгрузок партнёра, числа по позициям — синтетика"
            if demo else "Данные из выгрузок партнёра"
        ),
        "order": None if draft is None else {
            "version": draft.version, "revision": draft.revision,
            "status": draft.status.value, "approved_at": _iso(draft.approved_at),
        },
        "role": ws.role,
        "user": {"id": ws.role, "name": ROLE_NAMES.get(ws.role, ws.role)},
    }


def set_role(c: Container, role: str) -> dict[str, Any]:
    if role not in ROLE_NAMES:
        raise DomainValidationError("Неизвестная роль", field="role", details={"role": role})
    with c.workspace.lock:
        c.workspace.role = role
    result = {"header": header(c), "toast": f"Роль: {ROLE_NAMES[role]}"}
    if current_draft(c):
        result["order"] = order_current(c)
    return result


def reset_session(c: Container) -> dict[str, Any]:
    """Сбрасываются версии, ручные правки и журнал: журнал живёт в версиях."""
    c.drafts.clear()
    c.workspace.reset()
    return {"header": header(c), "toast": "Сессия сброшена: версии, правки и журнал удалены"}


# ---------- расчёт ----------

def calculate(c: Container) -> dict[str, Any]:
    """Запуск расчёта = запуск агента: проверка данных, расчёт, доп. проверки, версия."""
    ws = c.workspace
    suppliers = c.repo.suppliers()
    category = _category_value(ws.category_filter)
    draft = RunProcurementAgent(_calculator(c), c.repo, c.drafts).execute(
        goal="Подготовить закупку на следующий период",
        supplier=None, category=category,
        params=CalcParams(safety_factor=ws.safety_factor, today=ws.calc_date),
        params_by_supplier={s: _params(c, s) for s in suppliers},
        method=METHOD, author=ROLE_NAMES.get(ws.role, ws.role), include_all=True,
    )
    with ws.lock:
        ws.current_version = draft.version
        ws.calc_at = datetime.now(UTC)
        ws.calc_stale = False
    # Та же классификация, что в сводке таблицы: иначе тост и счётчик «к заказу» расходятся
    to_order = sum(1 for x in draft.lines.values() if row_status(x) == "order")
    return {
        "header": header(c),
        "order": order_current(c),
        "agent": {"version": draft.version, "trace": [_trace(e) for e in draft.trace]},
        "toast": f"Расчёт выполнен: {to_order} поз. к заказу из {len(draft.lines)}",
    }


def _category_value(value: str | None) -> str | None:
    """Фронт передаёт категорию как «SE|1»; расчёту нужна сама категория."""
    if not value:
        return None
    cat = value.split("|", 1)[-1]
    return None if cat == "—" else cat


def _trace(e) -> dict[str, Any]:
    return {"seq": e.seq, "type": e.type, "status": e.status, "title": e.title,
            "tool": e.tool, "sku": e.sku, "facts": e.facts}


# ---------- строка рекомендаций ----------

def row_status(line: DraftLine) -> str:
    codes = set(line.issue_codes)
    if codes & {"no_history", "short_history"}:
        return "insufficient_history"
    if line.status is LineStatus.INSUFFICIENT_DATA:
        return "needs_data"
    return "order" if line.quantity > 0 else "enough"


def _computed(line: DraftLine) -> bool:
    """Количество известно: расчёт на полных данных или менеджер поставил сам."""
    return line.status is not LineStatus.INSUFFICIENT_DATA or line.adjusted


def _urgency(line: DraftLine) -> str:
    if not _computed(line):
        return "unknown"
    if line.quantity <= 0:
        return "none"
    return "urgent" if line.urgency == "critical" else "this_cycle"


def _cover_days(line: DraftLine) -> int | None:
    if line.monthly_demand <= 0 or line.coverage_months >= 999:
        return None
    return round(line.coverage_months * 30)


def _excess(c: Container, line: DraftLine) -> bool:
    s = c.workspace.supplier(line.supplier)
    horizon = (s.lead_time_days + s.review_days) / 30
    return (line.quantity == 0 and line.monthly_demand > 0
            and line.coverage_months > horizon + c.workspace.excess_months)


def _reason_short(line: DraftLine) -> str:
    if not _computed(line):
        return line.issues[0] if line.issues else "Недостаточно данных для расчёта"
    parts = dict(line.reasons)
    # Подписи — контракт с _build_reasons в replenishment.py: переименуют там —
    # формула тихо откатится на полное обоснование, поэтому её держит тест
    labels = ("Потребность на период", "Свободный остаток", "Учтено в пути")
    if any(label not in parts for label in labels):
        return line.explanation
    # Значения приходят как «120 шт»; единица есть в соседней колонке, в формуле она шум
    need, free, transit = (parts[label].split()[0] for label in labels)
    text = f"потребность {need} − свободно {free} − путь {transit} → {line.recommended}"
    if line.moq > 1 and line.recommended:
        text += f" (крат. {line.moq})"
    return text


def _inbound(
    sku: Sku | None,
    *,
    today: date | None = None,
    arrival: date | None = None,
) -> list[dict[str, Any]]:
    if sku is None or sku.in_transit <= 0:
        return []
    if not sku.inbound:
        return [{
            "id": "legacy", "qty": sku.in_transit, "eta": None, "days": None,
            "doc_text": "Товар в пути", "counted": True, "in_horizon": True,
            "where_text": "учтён целиком: дата поступления неизвестна",
        }]

    result = []
    for index, item in enumerate(sku.inbound, start=1):
        counted = item.eta is None or arrival is None or item.eta <= arrival
        result.append({
            "id": item.document or f"inbound-{index}",
            "qty": item.quantity,
            "eta": item.eta.isoformat() if item.eta else None,
            "days": (item.eta - today).days if item.eta and today else None,
            "doc_text": item.document or "Товар в пути",
            "counted": counted,
            "in_horizon": counted,
            "where_text": "успевает к горизонту" if counted else "не успевает к горизонту",
        })
    return result


def recommendation_row(c: Container, line: DraftLine) -> dict[str, Any]:
    sku = c.repo.get(line.code)
    sid = supplier_id(line.supplier)
    computed = _computed(line)
    return {
        "sku_id": _sku_id(line.supplier, line.code),
        "supplier": {"id": sid, "name": c.workspace.supplier(line.supplier).name},
        "code_1c": line.code,
        "supplier_article": line.article,
        "name": line.name,
        "category": (sku.category or None) if sku else None,
        "unit": line.unit, "purchase_unit": line.unit, "unit_text": line.unit,
        "free_stock": sku.free_stock if sku else None,
        "inbound": _inbound(
            sku,
            today=c.workspace.calc_date or date.today(),
            arrival=(c.workspace.calc_date or date.today())
            + timedelta(days=c.workspace.supplier(line.supplier).lead_time_days),
        ),
        "recommended_qty": line.recommended if line.status is not LineStatus.INSUFFICIENT_DATA
        else None,
        "final_qty": line.quantity if computed else None,
        "manual": line.adjusted,
        "reason_short": _reason_short(line),
        "urgency": _urgency(line),
        "cover_days": _cover_days(line),
        "status": row_status(line),
        "excess": _excess(c, line),
        # Расширение контракта: позиция требует проверки человеком (флаг агента)
        "needs_review": line.status is LineStatus.NEEDS_REVIEW,
        "review_text": "; ".join(line.issues) or None,
    }


# ---------- экран 02: рекомендации ----------

def search(c: Container, query: dict[str, Any]) -> dict[str, Any]:
    draft = current_draft(c)
    if draft is None:
        calculate(c)  # первый заход на экран: считаем, чтобы таблица не была пустой
        draft = _require_draft(c)

    what_if = query.get("what_if")
    lines = _what_if_lines(c, draft, what_if) if what_if else list(draft.lines.values())
    rows = [recommendation_row(c, x) for x in lines]

    summary = {"order": 0, "enough": 0, "needs_data": 0, "insufficient_history": 0, "excess": 0}
    for r in rows:
        summary[r["status"]] += 1
        summary["excess"] += r["excess"]

    q = (query.get("q") or "").casefold().strip()
    if q:
        rows = [r for r in rows if q in f"{r['code_1c']} {r['supplier_article']} {r['name']}"
                .casefold()]
    if query.get("supplier_id"):
        rows = [r for r in rows if r["supplier"]["id"] == query["supplier_id"]]
    if query.get("category"):
        sid, _, cat = query["category"].partition("|")
        rows = [r for r in rows if r["supplier"]["id"] == sid
                and (r["category"] or "—") == cat]
    if query.get("status"):
        rows = [r for r in rows if r["status"] == query["status"]]

    if query.get("sort") == "code":
        rows.sort(key=lambda r: r["code_1c"])
    else:  # deficit: сначала то, что кончится раньше; без спроса — в конец
        rows.sort(key=lambda r: (r["cover_days"] is None, r["cover_days"] or 0))

    page_size = max(1, min(int(query.get("page_size") or 100), 500))
    pages_req = query.get("page") or {}
    groups: dict[str, dict[str, Any]] = {}
    for r in rows:
        g = groups.setdefault(r["supplier"]["id"], {"supplier": r["supplier"], "all": []})
        g["all"].append(r)
    out = []
    for sid, g in groups.items():
        total = len(g["all"])
        pages = max(1, -(-total // page_size))
        page = min(max(1, int(pages_req.get(sid, 1))), pages)
        out.append({
            "supplier": g["supplier"], "total": total, "page": page, "pages": pages,
            "count_text": f"{total} поз.",
            "rows": g["all"][(page - 1) * page_size: page * page_size],
        })

    head = header(c)
    head["what_if_active"] = bool(what_if)
    return {"header": head, "summary": summary, "groups": out,
            "what_if": what_if or None, "category_trends": None}


def _what_if_lines(c: Container, draft: OrderDraft, what_if: dict[str, Any]) -> list[DraftLine]:
    """«Что если» не сохраняется в версию: пересчёт на лету тем же расчётом.

    delay_days — поставки придут позже (срок поставки длиннее);
    demand_pct — спрос выше: история масштабируется, прогноз строится по ней.
    """
    delay = int(what_if.get("delay_days") or 0)
    factor = 1 + float(what_if.get("demand_pct") or 0) / 100
    calc = _calculator(c)
    result = []
    for old in draft.lines.values():
        sku = c.repo.get(old.code)
        if sku is None:
            continue
        if factor != 1:
            sku = replace(sku, history=tuple(
                MonthPoint(p.month, p.sold * factor, p.stock_start) for p in sku.history
            ))
        line = calc.calculate_line(sku, _params(c, sku.supplier, delay_days=delay))
        a = assess(sku, line, prepare(sku.history, sku.bulk_orders))
        result.append(draft_line(line, a.status, a.messages, a.codes))
    return result


# ---------- экран 03: объяснение SKU ----------

def line_for(c: Container, sku_id: str) -> DraftLine:
    """Строка текущей версии по идентификатору фронта: нужна ручке обоснования словами."""
    return _require_draft(c).line(_parse_sku_id(sku_id))


def explanation(c: Container, sku_id: str) -> dict[str, Any]:
    draft = _require_draft(c)
    code = _parse_sku_id(sku_id)
    line = draft.line(code)
    sku = c.repo.get(code)
    if sku is None:
        raise NotFoundError(f"Артикул {code!r} не найден", details={"sku_id": sku_id})

    s = c.workspace.supplier(sku.supplier)
    cleaned = prepare(sku.history, sku.bulk_orders)
    forecaster = c.forecasters[METHOD]
    cleaned_sku = replace(sku, history=cleaned.points)
    arrival = (c.workspace.calc_date or date.today()) + timedelta(days=s.lead_time_days)
    fc = forecaster.forecast(cleaned_sku, arrival.month)

    raw = {p.month: p for p in sku.history}
    last = sku.history[-12:]
    bulk = set(cleaned.bulk_months)
    months = []
    for p, cp in zip(sku.history[-12:], cleaned.points[-12:], strict=True):
        months.append({
            "month": p.month.strftime("%Y-%m"), "label": MONTH_LABELS[p.month.month - 1],
            "sales": p.sold,
            "restored": round(max(0.0, cp.sold - p.sold), 1) if p.stockout else 0,
            "one_off_excluded": round(max(0.0, p.sold - cp.sold), 1) if p.month in bulk else 0,
            "one_off_included": 0, "in_base": True, "partial": False, "missing": False,
        })
    forecast = []
    if sku.history:
        for i in range(1, 4):
            m = _add_months(sku.history[-1].month, i)
            forecast.append({"month": m.strftime("%Y-%m"),
                             "label": f"П·{MONTH_LABELS[m.month - 1].lower()}",
                             "qty": round(
                                 forecaster.forecast(cleaned_sku, m.month).monthly_demand, 2
                             )})

    origin = "synthetic" if c.data_mode == "demo" else "real"
    iek_monthly_stock = c.data_mode != "demo" and supplier_id(sku.supplier) == "IEK"
    events = [{
        "id": f"m{m.strftime('%Y-%m')}", "kind": "month",
        "qty": round(raw[m].sold - next(cp.sold for cp in cleaned.points if cp.month == m)),
        "included": False,
        "title_text": f"Разовые продажи в {m.strftime('%m.%Y')} — исключены из регулярного спроса",
        "note_text": _one_off_note(sku, m),
    } for m in cleaned.bulk_months]
    stockouts = [{
        "id": f"s{p.month.strftime('%Y-%m')}", "month": p.month.strftime("%Y-%m"),
        "availability": 0.0, "origin": origin, "removable": False,
        "title_text": f"{MONTH_LABELS[p.month.month - 1].lower()} {p.month.year} — "
                      "начальный остаток нулевой или не указан",
        "note_text": (
            f"Продано {p.sold:g}, спрос восстановлен оценкой до {cp.sold:.1f}"
            if cp.sold > p.sold else
            f"Продано {p.sold:g}, корректировка спроса не потребовалась"
        ),
    } for p, cp in zip(sku.history, cleaned.points, strict=True) if p.stockout]

    computed = _computed(line)
    steps = [{"key": f"r{i}", "label": label, "value_text": value, "note_text": "",
              "emphasis": label.startswith("Потребность"), "large": False}
             for i, (label, value) in enumerate(line.reasons)]
    steps.append({"key": "order", "label": "Рекомендуемый заказ",
                  "value_text": f"{line.recommended} {line.unit}" if computed else "—",
                  "note_text": f"кратность {line.moq}" if line.moq > 1 else "",
                  "emphasis": True, "large": True})

    ids = sorted(draft.lines.values(), key=lambda x: (supplier_id(x.supplier), x.code))
    pos = next(i for i, x in enumerate(ids) if x.code == code)
    cover = _cover_days(line)
    return {
        "header": header(c),
        "nav": {
            "prev_sku_id": _sku_id(ids[pos - 1].supplier, ids[pos - 1].code) if pos else None,
            "next_sku_id": _sku_id(ids[pos + 1].supplier, ids[pos + 1].code)
            if pos + 1 < len(ids) else None,
        },
        "sku": {
            "sku_id": _sku_id(sku.supplier, code),
            "supplier": {"id": supplier_id(sku.supplier), "name": s.name},
            "code_1c": code, "supplier_article": sku.article, "category": sku.category or None,
            "name": sku.name, "unit": line.unit, "purchase_unit": line.unit,
        },
        "status": row_status(line), "urgency": _urgency(line), "excess": _excess(c, line),
        "issues": [{"key": k, "text": t, "resolve": None}
                   for k, t in zip(line.issue_codes, line.issues, strict=False)],
        "chart": {"base_from": last[0].month.strftime("%Y-%m") if last else None,
                  "base_to": last[-1].month.strftime("%Y-%m") if last else None,
                  "months": months, "forecast": forecast},
        "events": events,
        "regular_clients": [],  # ID клиентов в данных партнёра нет
        "stockouts": stockouts,
        "stockout_candidates": [],
        "stockout_month_options": [],
        "demand": {
            "raw_avg": round(statistics.fmean(p.sold for p in last), 2) if last else None,
            "regular_avg": round(fc.base_demand, 2),
            "daily": round(line.monthly_demand / 30, 2),
            "season": round(fc.seasonality_factor, 2), "season_source_text": "по истории артикула",
            "trend": round(fc.growth_factor - 1, 3), "trend_source_text": "по истории артикула",
            "trend_manual": False,
            "trend_estimate": round(fc.growth_factor - 1, 3),
            "trend_estimate_text": f"{(fc.growth_factor - 1) * 100:+.0f}%",
        },
        "steps": steps,
        "explanation_text": line.explanation,
        "params": {"lead_time_days": s.lead_time_days, "review_days": s.review_days,
                   "season": round(fc.seasonality_factor, 2), "overridden": False},
        "stock": {"free": sku.free_stock, "free_manual": False, "reserve": None,
                  "cover_days": cover,
                  "cover_text": f"{cover} дн." if cover is not None else "—",
                  "early_risk": line.urgency == "critical"},
        "inbound": _inbound(
            sku,
            today=c.workspace.calc_date or date.today(),
            arrival=(c.workspace.calc_date or date.today()) + timedelta(days=s.lead_time_days),
        ),
        "manual": {"active": line.adjusted, "qty": line.quantity if line.adjusted else None,
                   "reason": line.adjustment_reason or None,
                   "note_text": f"изменил: {line.adjusted_by}" if line.adjusted else None},
        "price": {"value": None, "manual": False, "text": "не подтверждена"},
        "cost": {"value": None, "text": "—"},
        "provenance": [
            {"input": "История продаж", "source_text": "Ежемесячные продажи", "origin": origin},
            {"input": "Свободный остаток",
             "source_text": ("Начальный остаток последнего месяца, не текущий снимок"
                             if iek_monthly_stock else "Остатки / TDSheet"),
             "origin": "assumption" if iek_monthly_stock else origin},
            {"input": "Товар в пути", "source_text": "Путь / TDSheet", "origin": origin},
            {"input": "Срок поставки", "source_text": "Настройки поставщика",
             "origin": "assumption"},
        ],
        # Расширение контракта: что агент делал по этой позиции
        "agent_trace": [_trace(e) for e in draft.trace if e.sku == code],
    }


def _one_off_note(sku: Sku, month: date) -> str:
    # Накладная — проверяемое доказательство: менеджер найдёт её в 1С по номеру
    invoices = [b for b in sku.bulk_orders if b.month == month]
    if not invoices:
        return ("Продажи месяца выше ожидаемого уровня в 3 раза и более; "
                "ожидаемый уровень — медиана того же месяца других лет.")
    return "; ".join(
        f"Накладная {b.invoice}: {b.quantity:g} {sku.unit} при обычной {b.regular_quantity:g}"
        for b in invoices
    ) + " — разовая отгрузка, излишек исключён."


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def sku_action(c: Container, sku_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    draft = _require_draft(c)
    code = _parse_sku_id(sku_id)
    revision = _check_version(draft, payload)
    author = ROLE_NAMES.get(c.workspace.role, c.workspace.role)
    action = payload.get("action")

    if action == "set_manual_qty":
        qty = payload.get("qty")
        if not isinstance(qty, int | float) or qty < 0:
            raise DomainValidationError("Укажите количество не меньше нуля", field="qty")
        at = datetime.now(UTC)
        reason = payload.get("reason") or ""

        def change(d: OrderDraft) -> OrderDraft:
            # Проверка ревизии внутри замка хранилища: иначе между проверкой
            # и записью чужая правка успеет проскочить
            d.check_revision(revision)
            return d.adjust(code, int(qty), reason=reason, author=author, at=at)

        updated = c.drafts.update(draft.version, change)
        toast = f"Количество изменено: {int(qty)}"
    elif action == "clear_manual_qty":
        at = datetime.now(UTC)
        def change(d: OrderDraft) -> OrderDraft:
            d.check_revision(revision)
            return d.clear_adjustment(code, author=author, at=at)

        updated = c.drafts.update(draft.version, change)
        toast = "Возвращена рекомендация расчёта"
    else:
        raise DomainValidationError(
            f"Действие {action!r} пока не поддерживается",
            code="ACTION_NOT_SUPPORTED", field="action",
            details={"supported": ["set_manual_qty", "clear_manual_qty"]},
        )

    line = updated.line(code)
    return {
        "header": header(c),
        "sku": explanation(c, sku_id),
        "row": recommendation_row(c, line),
        "order": order_current(c),
        "log_entry": _audit(updated, updated.events[-1]),
        "toast": toast,
    }


# ---------- экран 04: проверка и экспорт ----------

def _permissions(role: str, draft: OrderDraft) -> dict[str, bool]:
    has_lines = any(x.exportable for x in draft.lines.values())
    return {
        "can_edit": True,  # правка утверждённого заказа разрешена, но снимает утверждение
        "can_submit": role == "manager" and draft.status is DraftStatus.DRAFT and has_lines,
        "can_approve": role == "head" and draft.status is DraftStatus.SUBMITTED,
        "can_reject": role == "head" and draft.status is DraftStatus.SUBMITTED,
        "can_export": draft.status is DraftStatus.APPROVED,
    }


def order_current(c: Container) -> dict[str, Any]:
    draft = _require_draft(c)
    role = c.workspace.role
    groups = []
    for name, lines in sorted(draft.by_supplier().items()):
        shown = [x for x in lines if x.quantity > 0 or x.adjusted or not _computed(x)]
        if not shown:
            continue
        pending = [x for x in shown if not x.exportable and not _computed(x)]
        to_order = [x for x in shown if x.exportable]
        groups.append({
            "supplier": {"id": supplier_id(name), "name": c.workspace.supplier(name).name},
            "summary_text": f"{len(to_order)} строк к заказу · изменено вручную: "
                            f"{sum(1 for x in shown if x.adjusted)}",
            "cost_text": "Сумма: цены не подтверждены",
            "pending_text": f"{len(pending)} поз. без количества (нужны данные) — "
                            "не попадут в экспорт" if pending else None,
            "lines": [{
                "sku_id": _sku_id(x.supplier, x.code), "code_1c": x.code, "name": x.name,
                "purchase_unit": x.unit,
                "recommended_qty": x.recommended
                if x.status is not LineStatus.INSUFFICIENT_DATA else None,
                "final_qty": x.quantity if _computed(x) else None,
                "manual": x.adjusted, "reason": x.adjustment_reason or None,
                "price": None, "cost": None,
            } for x in shown],
        })

    hints = {
        ("draft", "manager"): "Проверьте список и отправьте на согласование.",
        ("draft", "head"): "Менеджер ещё не отправил список на согласование.",
        ("submitted", "manager"): "Список на согласовании у руководителя.",
        ("submitted", "head"): "Проверьте список и утвердите или верните на доработку.",
    }
    status = draft.status.value
    ws = c.workspace
    return {
        "header": header(c),
        "version": draft.version,
        "revision": draft.revision,
        "status": status,
        "status_text": f"v{draft.version} {STATUS_TEXT[status]}",
        "approved_at": _iso(draft.approved_at),
        "approved_by": draft.approved_by or None,
        "hint_text": hints.get((status, role), "Заказ утверждён — можно выгружать для 1С."),
        "permissions": _permissions(role, draft),
        "blocked_reason_text": None,
        "groups": groups,
        "sent_to_supplier": False,
        "export_settings": {
            "format": ws.export_format, "separator": ws.export_separator,
            "encoding": ws.export_encoding,
            "columns": [{"key": k, "label": label, "enabled": ws.export_columns.get(k, True)}
                        for k, label in EXPORT_COLUMNS],
            "format_options": ["xlsx", "csv"], "separator_options": list(SEPARATORS),
            "encoding_options": list(ENCODINGS),
            "note_text": "Точный состав полей нужно сверить с образцом файла импорта 1С.",
        },
    }


def order_action(c: Container, payload: dict[str, Any]) -> dict[str, Any]:
    draft = _require_draft(c)
    revision = _check_version(draft, payload)
    role = c.workspace.role
    author = ROLE_NAMES.get(role, role)
    action = payload.get("action")
    at = datetime.now(UTC)

    allowed = {"submit": "manager", "approve": "head", "reject": "head"}
    if action not in allowed:
        raise DomainValidationError(f"Неизвестное действие {action!r}", field="action")
    if role != allowed[action]:
        raise ForbiddenError(
            "Отправляет на согласование менеджер закупа" if action == "submit"
            else "Утверждает и возвращает руководитель закупок"
        )

    def change(d: OrderDraft) -> OrderDraft:
        # Все проверки состояния — внутри замка хранилища, на свежей версии
        if action == "submit":
            return d.submit(author=author, revision=revision, at=at)
        if action == "reject":
            return d.reject(author=author, revision=revision,
                            comment=payload.get("comment") or "", at=at)
        if d.status is not DraftStatus.SUBMITTED:
            raise ConflictError("Утвердить можно только версию на согласовании",
                                code="ORDER_NOT_SUBMITTED")
        return d.approve(author=author, revision=revision, at=at)

    updated = c.drafts.update(draft.version, change)
    toast = {"submit": "Отправлено на согласование", "approve": "Заказ утверждён",
             "reject": "Возвращено на доработку"}[action]
    return {"header": header(c), "order": order_current(c),
            "log_entry": _audit(updated, updated.events[-1]), "toast": toast}


def update_export_settings(c: Container, payload: dict[str, Any]) -> dict[str, Any]:
    ws = c.workspace
    with ws.lock:
        if payload.get("format") in ("xlsx", "csv"):
            ws.export_format = payload["format"]
        if payload.get("separator") in SEPARATORS:
            ws.export_separator = payload["separator"]
        if payload.get("encoding") in ENCODINGS:
            ws.export_encoding = payload["encoding"]
        for col in payload.get("columns") or []:
            if col.get("key") in ws.export_columns:
                ws.export_columns[col["key"]] = bool(col.get("enabled"))
    return {"header": header(c), "order": order_current(c)}


def export(c: Container, payload: dict[str, Any]) -> tuple[str, bytes, str]:
    """Файл утверждённого заказа с колонками, которые выбрал менеджер.

    В файл идут только позиции, за которые кто-то отвечает (DraftLine.exportable):
    «нужны данные» без ручного количества не выгружаются.
    """
    ws = c.workspace
    version = payload.get("version") or ws.current_version
    if version is None:
        raise ConflictError("Расчёт ещё не запускался", code="NO_CALCULATION")
    draft = c.drafts.get(version)
    if not draft.approved:
        raise ConflictError("Выгрузить можно только утверждённый заказ",
                            code="ORDER_NOT_APPROVED", details={"version": version})

    fmt = payload.get("format") or ws.export_format
    separator = payload.get("separator") or ws.export_separator
    encoding = payload.get("encoding") or ws.export_encoding
    if fmt not in ("xlsx", "csv") or separator not in SEPARATORS or encoding not in ENCODINGS:
        raise DomainValidationError("Неподдерживаемый формат выгрузки", field="format")
    labels = dict(EXPORT_COLUMNS)
    keys = payload.get("columns") or [k for k, _ in EXPORT_COLUMNS if ws.export_columns.get(k)]
    unknown = [k for k in keys if k not in labels]
    if unknown:
        raise DomainValidationError(f"Неизвестные колонки: {unknown}", field="columns")

    sid = payload.get("supplier_id")
    sheets: dict[str, list[list[Any]]] = {}
    for name, lines in sorted(draft.by_supplier().items()):
        if sid and supplier_id(name) != sid:
            continue
        rows = [[_export_value(c, draft, x, k) for k in keys] for x in lines if x.exportable]
        if rows:
            sheets[c.workspace.supplier(name).name] = rows

    from app.infrastructure.export.table import render_csv, render_xlsx

    header_row = [labels[k] for k in keys]
    if fmt == "xlsx":
        content = render_xlsx(header_row, sheets)
    else:
        content = render_csv(header_row, [r for rows in sheets.values() for r in rows],
                             separator=SEPARATORS[separator], encoding=ENCODINGS[encoding])
    filename = f"zakaz_almaty_{(sid or 'all').lower()}_v{version}.{fmt}"
    return filename, content, fmt


EXPORT_URGENCY = {"critical": "срочно", "high": "в этом цикле", "normal": "плановая",
                  "none": "не требуется"}
EXPORT_STATUS = {"order": "к заказу", "enough": "хватает", "needs_data": "нужны данные",
                 "insufficient_history": "мало истории"}


def _export_value(c: Container, draft: OrderDraft, x: DraftLine, key: str) -> Any:
    return {
        "version": f"v{draft.version}.r{draft.revision}",
        "approved_at": draft.approved_at.astimezone(ALMATY).strftime("%d.%m.%Y %H:%M")
        if draft.approved_at else "",
        "supplier": c.workspace.supplier(x.supplier).name,
        "code_1c": x.code, "supplier_article": x.article, "name": x.name,
        "purchase_unit": x.unit, "recommended_qty": x.recommended, "final_qty": x.quantity,
        "urgency": EXPORT_URGENCY.get(x.urgency, x.urgency),
        "status": EXPORT_STATUS.get(row_status(x), row_status(x)),
        "manual": "да" if x.adjusted else "", "reason": x.adjustment_reason,
        # Обоснование строкой — то же, что менеджер видел в таблице и карточке
        "explanation": x.explanation,
        "price": "", "cost": "",  # цен в данных нет — пусто, а не ноль
        "approved_by": draft.approved_by or "",
    }[key]


def versions(c: Container) -> list[dict[str, Any]]:
    return [{"version": d.version, "approved_at": _iso(d.approved_at),
             "approved_by_text": d.approved_by,
             "lines": sum(1 for x in d.lines.values() if x.exportable)}
            for d in c.drafts.list() if d.approved]


def version_diff(c: Container, version: int) -> dict[str, Any]:
    old, cur = c.drafts.get(version), _require_draft(c)
    rows = []
    for code in sorted(set(old.lines) | set(cur.lines)):
        a, b = old.lines.get(code), cur.lines.get(code)
        qa, qb = (a.quantity if a else None), (b.quantity if b else None)
        if qa != qb:
            ref = b or a
            rows.append({"code_1c": code, "name": ref.name,
                         "in_version_text": f"{qa} {ref.unit}" if qa is not None else "—",
                         "current_text": f"{qb} {ref.unit}" if qb is not None else "—"})
    return {"title_text": f"Отличия v{version} от текущего списка", "rows": rows}


def _audit(draft: OrderDraft, e: DraftEvent) -> dict[str, Any]:
    return {"version": draft.version, "text": _event_text(e), "role": None,
            "user_text": e.author, "at": _iso(e.at)}


def _event_text(e: DraftEvent) -> str:
    titles = {"calculate": "Расчёт", "adjust": "Изменено количество",
              "clear_adjustment": "Возвращена рекомендация", "submit": "Отправлено на согласование",
              "approve": "Утверждено", "reject": "Возвращено на доработку",
              "approval_reset": "Согласование сброшено", "derive": "Новая версия"}
    return f"{titles.get(e.action, e.action)}: {e.detail}" if e.detail else titles.get(
        e.action, e.action)


def audit_log(c: Container, page: int, page_size: int) -> dict[str, Any]:
    entries = [(d, e) for d in c.drafts.list() for e in d.events]
    entries.sort(key=lambda x: x[1].at, reverse=True)
    total = len(entries)
    page_size = max(1, min(page_size, 200))
    pages = max(1, -(-total // page_size))
    page = min(max(1, page), pages)
    items = [_audit(d, e) for d, e in entries[(page - 1) * page_size: page * page_size]]
    return {"items": items, "page": page, "page_size": page_size, "total": total, "pages": pages}


# ---------- экран 01: данные и параметры ----------

def settings_view(c: Container) -> dict[str, Any]:
    ws = c.workspace
    skus = c.repo.list_skus()
    categories = sorted({(supplier_id(s.supplier), s.category or "—") for s in skus})
    for name in c.repo.suppliers():
        ws.supplier(name)
    today = date.today()
    return {
        "warehouse_id": ws.warehouse_id,
        "warehouse_options": [{"id": "ALM", "name": "Алматы"}],
        "category_filter": ws.category_filter,
        "category_options": [{"value": None, "label": "Все"}] + [
            {"value": f"{sid}|{cat}",
             "label": f"Категория {cat}" if cat != "—" else f"Без категории ({sid})"}
            for sid, cat in categories
        ],
        "calc_date": (ws.calc_date or today).isoformat(),
        "calc_date_min": today.isoformat(),
        "calc_date_max": date(today.year, 12, 31).isoformat(),
        "suppliers": [{"id": s.id, "name": s.name, "lead_time_days": s.lead_time_days,
                       "review_days": s.review_days,
                       "horizon_days": s.lead_time_days + s.review_days}
                      for s in ws.suppliers.values()],
        # Страховой запас по категориям, порог разовых сделок и правило возвратов
        # пока зашиты в расчётном модуле. Отдавать их как настройки нельзя:
        # менеджер поменяет значение, а заказ останется прежним.
        "categories": [],
        "excess_months": ws.excess_months,
    }


def patch_settings(c: Container, payload: dict[str, Any]) -> dict[str, Any]:
    ws = c.workspace
    with ws.lock:
        for item in payload.get("suppliers") or []:
            s = ws.suppliers.get(item.get("id"))
            if s is None:
                raise DomainValidationError("Неизвестный поставщик", field="suppliers")
            for key in ("lead_time_days", "review_days"):
                if key in item:
                    if int(item[key]) < 1:
                        raise DomainValidationError("Значение должно быть ≥ 1", field=key)
                    setattr(s, key, int(item[key]))
        if "excess_months" in payload:
            if float(payload["excess_months"]) < 0.5:
                raise DomainValidationError("Значение должно быть ≥ 0,5", field="excess_months")
            ws.excess_months = float(payload["excess_months"])
        if "category_filter" in payload:
            ws.category_filter = payload["category_filter"]
        if "calc_date" in payload:
            ws.calc_date = date.fromisoformat(payload["calc_date"]) if payload["calc_date"] \
                else None
        fixed = {"returns_rule", "one_off_threshold_x_median", "categories"} & payload.keys()
        if fixed:
            raise DomainValidationError(
                "Эта настройка пока не меняется: правило зашито в расчёте",
                code="SETTING_NOT_SUPPORTED", field=sorted(fixed)[0],
            )
        ws.calc_stale = ws.current_version is not None
    return {"header": header(c), "settings": settings_view(c),
            "toast": "Настройки сохранены — пересчитайте заказ"}


def data_overview(c: Container) -> dict[str, Any]:
    draft = current_draft(c)
    origin = "synthetic" if c.data_mode == "demo" else "real"
    readiness = []
    if draft:
        for name, lines in sorted(draft.by_supplier().items()):
            statuses = [row_status(x) for x in lines]
            readiness.append({
                "supplier": {"id": supplier_id(name), "name": c.workspace.supplier(name).name},
                "calculated": sum(s in ("order", "enough") for s in statuses),
                "needs_data": statuses.count("needs_data"),
                "insufficient_history": statuses.count("insufficient_history"),
            })
    files = sorted(c.settings.data_dir.rglob("*.xlsx")) if c.settings.data_dir and \
        c.settings.data_dir.exists() else []
    return {
        "header": header(c),
        "sources": [{
            "key": f.stem, "supplier": {"id": "SE" if "system" in f.as_posix().lower()
                                        else "IEK", "name": ""},
            "type_text": f.stem, "usage_text": "", "freshness_text": None,
            "volume_text": None, "volume_origin": "real",
            "file": {"name": f.name, "sheets": None, "rows": None, "status": "applied"
                     if c.data_mode == "imported" else "uploaded",
                     "status_text": "применён" if c.data_mode == "imported"
                     else "загружен, парсер в работе"},
            "import_id": None,
        } for f in files],
        "matching": [],
        "readiness": readiness,
        "assumptions": [
            {"label": "Срок поставки L / период пересмотра R", "origin": "assumption",
             "value_text": ", ".join(f"{s.name} {s.lead_time_days}/{s.review_days} дн."
                                     for s in c.workspace.suppliers.values())},
            {"label": "Страховой запас", "origin": "assumption",
             "value_text": f"{c.workspace.safety_factor:.0%} потребности на горизонт"},
            {"label": "Числа по позициям", "origin": origin,
             "value_text": "синтетика на реальных кодах" if origin == "synthetic"
             else "из выгрузок партнёра"},
        ],
        "issues": [],
        "document_rules": [
            {"doc_type": "Реализация", "rule_text": "Продажа, входит в спрос", "editable": False},
            {"doc_type": "Возврат",
             "rule_text": "Отрицательный месячный итог — возврат, в спрос не входит; "
                          "отрицательные транзакции не участвуют в поиске разовых сделок",
             "editable": False},
        ],
        "settings": settings_view(c),
    }


# ---------- экран 05: проверки ТЗ ----------

def validation_scenarios(c: Container) -> dict[str, Any]:
    results = RunSelfChecks(_calculator(c)).execute()
    passed = sum(1 for r in results if r.passed)
    return {
        "passed": passed, "total": len(results),
        "summary_text": f"Пройдено {passed} из {len(results)}",
        "items": [{"n": i, "name": r.name, "expected_text": None, "actual_text": r.detail,
                   "passed": r.passed} for i, r in enumerate(results, start=1)],
    }
