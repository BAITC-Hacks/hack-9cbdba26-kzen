"""Загрузка выгрузок через API: слияние по поставщику, сброс версий, ошибки формы.

Файлы партнёра не нужны: миниатюрные xlsx собираются теми же помощниками,
что и в тестах загрузчика, — шапки повторяют реальные.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from tests.test_excel_loader import _build_iek

B = "/api/v1"


def _iek_uploads(tmp_path: Path, *, drop: str | None = None) -> list[tuple]:
    _build_iek(tmp_path)
    files = []
    for path in sorted((tmp_path / "IEK").glob("*.xlsx")):
        if drop and drop in path.name:
            continue
        files.append(("files", (path.name, path.read_bytes(),
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")))
    return files


def _start(client: TestClient, files: list[tuple], supplier: str = "IEK"):
    return client.post(f"{B}/imports", data={"supplier": supplier}, files=files)


def _finish(client: TestClient, import_id: str) -> dict:
    client.app.state.container.imports.wait(import_id, timeout=30)
    return client.get(f"{B}/imports/{import_id}").json()


def test_successful_import_replaces_only_that_supplier(client, tmp_path):
    container = client.app.state.container
    client.post(f"{B}/calculations", json={})
    assert client.get(f"{B}/session").json()["order"] is not None

    response = _start(client, _iek_uploads(tmp_path))
    assert response.status_code == 202, response.text
    started = response.json()
    assert started["status"] == "running"
    assert started["supplier"] == "IEK"
    assert "Ежемесячные продажи.xlsx" in started["files"]

    job = _finish(client, started["import_id"])
    assert job["status"] == "done", job
    assert job["applied"] is True
    assert job["error"] is None
    assert job["finished_at"] is not None
    assert job["report"]["metrics"]["normalized_skus"] == 1
    assert isinstance(job["report"]["issues"], list)

    codes = {sku.code: sku.supplier for sku in container.repo.list_skus()}
    assert codes == {"IEK-1": "IEK", "300200428_": "Systeme Electric"}
    assert container.data_mode == "uploaded"
    # Версии и текущий заказ считались по старым данным — их нет
    assert client.get(f"{B}/orders/versions").json() == []
    header = client.get(f"{B}/session").json()
    assert header["order"] is None
    assert header["data_mode"] == "uploaded"
    assert header["data_mode_text"].startswith("Данные загружены через интерфейс ")

    overview = client.get(f"{B}/data/overview").json()
    assert overview["imports"][0]["import_id"] == started["import_id"]
    assert "report" not in overview["imports"][0]
    assert any(s["import_id"] == started["import_id"] for s in overview["sources"])


def test_failed_import_keeps_repository(client, tmp_path):
    container = client.app.state.container
    before = {sku.code for sku in container.repo.list_skus()}

    started = _start(client, _iek_uploads(tmp_path, drop="Ежемесячные продажи")).json()
    job = _finish(client, started["import_id"])

    assert job["status"] == "failed"
    assert job["applied"] is False
    assert job["report"] is None
    assert "ежемесячные продажи" in job["error"]
    assert {sku.code for sku in container.repo.list_skus()} == before
    assert container.data_mode == "imported"


def test_non_xlsx_is_rejected(client):
    response = _start(client, [("files", ("продажи.csv", b"a;b", "text/csv"))])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BAD_FILE_TYPE"


def test_unknown_supplier_is_rejected(client):
    response = _start(client, [("files", ("a.xlsx", b"x", "application/octet-stream"))],
                      supplier="Legrand")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_SUPPLIER"


def test_missing_files_is_422(client):
    assert client.post(f"{B}/imports", data={"supplier": "IEK"}).status_code == 422


def test_unknown_import_is_404(client):
    assert client.get(f"{B}/imports/nope").status_code == 404


def test_list_returns_newest_first_without_report(client, tmp_path):
    first = _start(client, _iek_uploads(tmp_path, drop="MOQ")).json()["import_id"]
    _finish(client, first)
    second = _start(client, _iek_uploads(tmp_path)).json()["import_id"]
    _finish(client, second)

    listed = client.get(f"{B}/imports").json()
    assert [job["import_id"] for job in listed][:2] == [second, first]
    assert all("report" not in job for job in listed)
    assert listed[0]["status"] == "done" and listed[1]["status"] == "failed"
