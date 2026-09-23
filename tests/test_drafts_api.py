"""Рабочий процесс закупщика: версия → правка → утверждение → выгрузка."""

from __future__ import annotations

import csv
import io
import threading
from dataclasses import replace
from datetime import UTC, datetime

from app.domain.workflow import OrderDraft
from app.infrastructure.storage.draft_store import MemoryDraftStore

BASE = "/api/v1/drafts"


def _create(client) -> dict:
    response = client.post(BASE, json={"lead_time_days": 45, "author": "Алдияр"})
    assert response.status_code == 201
    return response.json()


def _first_line(draft: dict) -> dict:
    return draft["suppliers"][0]["lines"][0]


def _approve(client, draft: dict):
    return client.post(
        f"{BASE}/{draft['version']}/approve",
        json={"author": "Алдияр", "revision": draft["revision"]},
    )


def test_each_calculation_is_new_version(client):
    first, second = _create(client), _create(client)
    assert second["version"] == first["version"] + 1

    listed = client.get(BASE).json()
    assert [d["version"] for d in listed] == [second["version"], first["version"]]
    assert all(d["sent_to_supplier"] is False for d in listed)


def test_draft_groups_by_supplier_and_keeps_explanation(client):
    draft = _create(client)
    assert {s["supplier"] for s in draft["suppliers"]} == {"Systeme Electric", "IEK"}
    line = _first_line(draft)
    assert line["quantity"] == line["recommended"]
    assert "заказать" in line["explanation"]


def test_adjust_requires_reason(client):
    draft = _create(client)
    line = _first_line(draft)
    response = client.patch(
        f"{BASE}/{draft['version']}/lines/{line['code']}",
        json={"quantity": 10, "reason": "   "},
    )
    assert response.status_code == 422


def test_adjust_keeps_recommendation_and_reason(client):
    draft = _create(client)
    line = _first_line(draft)
    body = client.patch(
        f"{BASE}/{draft['version']}/lines/{line['code']}",
        json={"quantity": line["recommended"] + 100, "reason": "акция у клиента", "author": "Миша"},
    ).json()

    changed = next(x for s in body["suppliers"] for x in s["lines"] if x["code"] == line["code"])
    assert changed["quantity"] == line["recommended"] + 100
    assert changed["recommended"] == line["recommended"]
    assert changed["adjustment_reason"] == "акция у клиента"
    assert body["revision"] == draft["revision"] + 1
    assert body["adjusted_positions"] == 1


def test_adjust_unknown_code_is_404(client):
    draft = _create(client)
    response = client.patch(
        f"{BASE}/{draft['version']}/lines/нет-такого", json={"quantity": 1, "reason": "x"}
    )
    assert response.status_code == 404


def test_change_after_approval_resets_it(client):
    """Главное правило процесса: утверждение относится к конкретному содержимому."""
    draft = _create(client)
    approved = _approve(client, draft).json()
    assert approved["status"] == "approved"

    line = _first_line(draft)
    changed = client.patch(
        f"{BASE}/{draft['version']}/lines/{line['code']}",
        json={"quantity": 0, "reason": "поставщик снял позицию"},
    ).json()

    assert changed["status"] == "draft"
    assert changed["approved_by"] == ""
    assert "approval_reset" in [e["action"] for e in changed["events"]]


def test_approve_stale_revision_is_conflict(client):
    """Менеджер утверждает то, что видел, а не то, что успели поменять после."""
    draft = _create(client)
    line = _first_line(draft)
    client.patch(
        f"{BASE}/{draft['version']}/lines/{line['code']}", json={"quantity": 1, "reason": "x"}
    )

    response = _approve(client, draft)  # ревизия из устаревшего экрана
    assert response.status_code == 409
    assert response.json()["error"]["details"]["current"] == draft["revision"] + 1


def test_export_only_after_approval(client):
    draft = _create(client)
    assert client.get(f"{BASE}/{draft['version']}/export").status_code == 409

    _approve(client, draft)
    response = client.get(f"{BASE}/{draft['version']}/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][:3] == ["Поставщик", "Код 1с", "Артикул"]
    assert len(rows) > 1


def test_export_uses_manager_quantity(client):
    draft = _create(client)
    line = _first_line(draft)
    updated = client.patch(
        f"{BASE}/{draft['version']}/lines/{line['code']}",
        json={"quantity": 777, "reason": "крупный объект"},
    ).json()
    _approve(client, updated)

    text = client.get(f"{BASE}/{draft['version']}/export?format=csv").content.decode("utf-8-sig")
    row = next(r for r in csv.reader(io.StringIO(text), delimiter=";") if r[1] == line["code"])
    assert row[6] == "777"
    assert row[7] == "крупный объект"


def test_no_route_sends_to_supplier(client):
    """ТЗ запрещает отправку без человека — в API нет ни одной такой ручки."""
    paths = list(client.get("/openapi.json").json()["paths"])
    assert not [p for p in paths if "send" in p or "submit" in p]


def test_parallel_adjustments_are_not_lost():
    """Под нагрузкой ни одна правка не теряется: ревизия = 1 + число правок."""
    store = MemoryDraftStore()
    at = datetime.now(UTC)
    store.create(lambda v: OrderDraft(version=v, created_at=at, params={}, lines={}))

    def bump(draft: OrderDraft) -> OrderDraft:
        return replace(draft, revision=draft.revision + 1)

    threads = [
        threading.Thread(target=lambda: [store.update(1, bump) for _ in range(200)])
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert store.get(1).revision == 1 + 8 * 200
