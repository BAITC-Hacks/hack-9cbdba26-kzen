"""Ручки под контракт фронта: сценарий закупщика целиком и три исправленных дыры."""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.core.container import Container
from app.infrastructure.cache.memory import MemoryCache
from app.infrastructure.forecasting.baseline import BaselineForecaster
from app.infrastructure.forecasting.smoothed import SmoothedForecaster
from app.infrastructure.storage.demo_data import build_demo_repository
from app.main import create_app

B = "/api/v1"


@pytest.fixture
def ui(settings):
    container = Container(
        settings=settings, repo=build_demo_repository(), cache=MemoryCache(),
        forecasters={"baseline": BaselineForecaster(), "smoothed": SmoothedForecaster()},
    )
    with TestClient(create_app(settings, container=container)) as client:
        yield client


def _approved(ui) -> int:
    first = ui.post(f"{B}/recommendations/search", json={}).json()
    sku_id = first["groups"][0]["rows"][0]["sku_id"]
    v = ui.get(f"{B}/orders/current").json()["version"]
    ui.post(f"{B}/skus/{sku_id}/actions",
            json={"action": "set_manual_qty", "qty": 96, "reason": "проект", "order_version": v})
    ui.post(f"{B}/orders/current/actions", json={"action": "submit", "order_version": v})
    ui.put(f"{B}/session/role", json={"role": "head"})
    assert ui.post(f"{B}/orders/current/actions",
                   json={"action": "approve", "order_version": v}).status_code == 200
    return v


def test_full_purchasing_flow(ui):
    v = _approved(ui)
    order = ui.get(f"{B}/orders/current").json()
    assert order["status"] == "approved"
    assert order["permissions"]["can_export"] is True
    assert order["sent_to_supplier"] is False
    assert len(ui.get(f"{B}/orders/versions").json()) == 1
    assert ui.post(f"{B}/orders/export", json={"version": v}).status_code == 200


def test_roles_and_reason_are_enforced(ui):
    ui.post(f"{B}/recommendations/search", json={})
    v = ui.get(f"{B}/orders/current").json()["version"]
    sku_id = ui.post(f"{B}/recommendations/search", json={}).json()["groups"][0]["rows"][0][
        "sku_id"]

    no_reason = ui.post(f"{B}/skus/{sku_id}/actions",
                        json={"action": "set_manual_qty", "qty": 1, "reason": ""})
    assert no_reason.json()["error"]["code"] == "REASON_REQUIRED"
    assert no_reason.json()["error"]["field"] == "reason"

    ui.post(f"{B}/orders/current/actions", json={"action": "submit", "order_version": v})
    forbidden = ui.post(f"{B}/orders/current/actions",
                        json={"action": "approve", "order_version": v})
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN_ROLE"


def test_needs_data_is_null_not_zero(ui):
    rows = [r for g in ui.post(f"{B}/recommendations/search", json={}).json()["groups"]
            for r in g["rows"]]
    no_code = next(r for r in rows if r["code_1c"] == "ATN000330")
    assert no_code["status"] == "needs_data"
    assert no_code["final_qty"] is None
    assert no_code["urgency"] == "unknown"


def test_dead_settings_are_not_offered(ui):
    """Настройка, которая не меняет расчёт, вводит менеджера в заблуждение."""
    settings = ui.get(f"{B}/data/overview").json()["settings"]
    assert "one_off_threshold_x_median" not in settings
    assert "returns_rule" not in settings

    response = ui.patch(f"{B}/settings", json={"returns_rule": "ignore"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SETTING_NOT_SUPPORTED"


def test_lead_time_setting_changes_order(ui):
    def total():
        ui.post(f"{B}/calculations", json={})
        return sum(r["final_qty"] or 0 for g in ui.post(f"{B}/recommendations/search",
                                                         json={}).json()["groups"]
                   for r in g["rows"])

    before = total()
    ui.patch(f"{B}/settings", json={"suppliers": [{"id": "SE", "lead_time_days": 90}]})
    assert total() > before


def test_export_respects_columns_separator_encoding(ui):
    v = _approved(ui)
    response = ui.post(f"{B}/orders/export", json={
        "version": v, "format": "csv", "separator": "tab", "encoding": "cp1251",
        "columns": ["code_1c", "final_qty", "reason"],
    })
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("cp1251")), delimiter="\t"))
    assert rows[0] == ["Код 1С", "Итог", "Причина"]
    assert any(r[1] == "96" and r[2] == "проект" for r in rows[1:])


def test_export_before_approval_is_conflict(ui):
    ui.post(f"{B}/recommendations/search", json={})
    v = ui.get(f"{B}/orders/current").json()["version"]
    response = ui.post(f"{B}/orders/export", json={"version": v})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOT_APPROVED"


def test_reset_clears_versions_and_journal(ui):
    _approved(ui)
    assert ui.get(f"{B}/audit-log").json()["total"] > 0

    ui.post(f"{B}/session/reset", json={"confirm": True})

    assert ui.get(f"{B}/audit-log").json()["total"] == 0
    assert ui.get(f"{B}/orders/versions").json() == []
    assert ui.get(f"{B}/session").json()["order"] is None


def test_current_route_is_not_taken_by_sku_card(ui):
    """/orders/{code} зарегистрирован раньше в каркасе — не должен перехватывать current."""
    ui.post(f"{B}/recommendations/search", json={})
    assert "version" in ui.get(f"{B}/orders/current").json()


def test_reason_short_is_formula_not_full_text(ui):
    rows = [r for g in ui.post(f"{B}/recommendations/search", json={}).json()["groups"]
            for r in g["rows"] if r["status"] == "order"]
    assert rows
    # Подписи обоснования должны совпадать с _build_reasons, иначе тут будет полный текст
    assert all("потребность" in r["reason_short"] for r in rows)
    assert "свободно" in rows[0]["reason_short"] and "путь" in rows[0]["reason_short"]


def test_card_uses_invoice_bulk_like_calculation(settings):
    """Карточка и расчёт чистят историю одинаково: разовая накладная видна с номером."""
    from dataclasses import replace

    from app.domain.entities import BulkOrderEvent

    repo = build_demo_repository()
    sku = repo.get("300200430_")
    month = sku.history[-2].month
    repo.add(replace(sku, bulk_orders=(
        BulkOrderEvent(month=month, invoice="TEST-1", quantity=40.0, regular_quantity=5.0),)))
    container = Container(
        settings=settings, repo=repo, cache=MemoryCache(),
        forecasters={"baseline": BaselineForecaster(), "smoothed": SmoothedForecaster()},
    )
    with TestClient(create_app(settings, container=container)) as client:
        client.post(f"{B}/calculations", json={})
        card = client.get(f"{B}/skus/SE:300200430_/explanation").json()
    notes = " ".join(e["note_text"] for e in card["events"])
    assert "TEST-1" in notes


def test_card_forecast_requires_sales_history(settings):
    from dataclasses import replace

    repo = build_demo_repository()
    sku = repo.get("200400050_")
    repo.add(replace(sku, history=()))
    container = Container(
        settings=settings, repo=repo, cache=MemoryCache(),
        forecasters={"baseline": BaselineForecaster(), "smoothed": SmoothedForecaster()},
    )
    with TestClient(create_app(settings, container=container)) as client:
        assert client.post(f"{B}/calculations", json={}).status_code == 200
        no_history = client.get(f"{B}/skus/IEK:200400050_/explanation")
        with_history = client.get(f"{B}/skus/SE:300200430_/explanation")

    assert no_history.status_code == 200
    assert no_history.json()["chart"]["months"] == []
    # Без продаж нулевые столбцы выглядели бы как подтверждённый прогноз.
    assert no_history.json()["chart"]["forecast"] == []
    assert with_history.status_code == 200
    assert [point["month"] for point in with_history.json()["chart"]["forecast"]] == [
        "2026-09", "2026-10", "2026-11",
    ]


def test_card_shows_small_nonzero_demand_without_changing_order(settings):
    from dataclasses import replace

    repo = build_demo_repository()
    sku = repo.get("200400050_")
    repo.add(replace(
        sku, free_stock=0,
        history=tuple(replace(point, sold=0.25) for point in sku.history),
    ))
    container = Container(
        settings=settings, repo=repo, cache=MemoryCache(),
        forecasters={"baseline": BaselineForecaster(), "smoothed": SmoothedForecaster()},
    )
    with TestClient(create_app(settings, container=container)) as client:
        assert client.post(f"{B}/calculations", json={}).status_code == 200
        card = client.get(f"{B}/skus/IEK:200400050_/explanation").json()

    assert card["demand"]["raw_avg"] == 0.25
    assert card["demand"]["regular_avg"] == 0.25
    assert [point["qty"] for point in card["chart"]["forecast"]] == [0.25] * 3
    assert any("(0.25 шт/мес)" in issue["text"] for issue in card["issues"])
    steps = {step["label"]: step["value_text"] for step in card["steps"]}
    assert steps["Средние продажи"] == "0.25 шт/мес"
    assert steps["Потребность на период"] != "0 шт"
    assert steps["Рекомендуемый заказ"] == "10 шт"


def test_calculation_toast_matches_table_summary(ui):
    toast = ui.post(f"{B}/calculations", json={}).json()["toast"]
    summary = ui.post(f"{B}/recommendations/search", json={}).json()["summary"]
    assert f"{summary['order']} поз. к заказу" in toast
