"""API расчёта заказов."""


def test_health_reports_components(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "baseline" in body["components"]["forecasters"]


def test_calculate_groups_by_supplier(client):
    """Группировка по поставщикам — прямое требование ТЗ (Must have 5)."""
    response = client.post("/api/v1/orders/calculate", json={"lead_time_days": 45})
    assert response.status_code == 200

    body = response.json()
    suppliers = {s["supplier"] for s in body["suppliers"]}
    assert suppliers == {"Systeme Electric", "IEK"}
    assert body["total_positions"] > 0


def test_every_line_has_explanation(client):
    """Каждая позиция сопровождается обоснованием."""
    body = client.post("/api/v1/orders/calculate", json={}).json()
    lines = [line for s in body["suppliers"] for line in s["lines"]]

    assert lines
    for line in lines:
        assert line["reasons"]
        assert "заказать" in line["explanation"]


def test_quantity_respects_moq(client):
    """Количество кратно минимальной партии отгрузки."""
    body = client.post("/api/v1/orders/calculate", json={}).json()
    for s in body["suppliers"]:
        for line in s["lines"]:
            if line["moq"] > 1 and line["quantity"] > 0:
                assert line["quantity"] % line["moq"] == 0


def test_longer_lead_time_increases_order(client):
    """Дольше везут — больше нужно заказать."""
    short = client.post("/api/v1/orders/calculate", json={"lead_time_days": 30}).json()
    long = client.post("/api/v1/orders/calculate", json={"lead_time_days": 120}).json()

    def units(body):
        return sum(s["total_units"] for s in body["suppliers"])

    assert units(long) > units(short)


def test_filter_by_supplier(client):
    body = client.post("/api/v1/orders/calculate", json={"supplier": "IEK"}).json()
    assert [s["supplier"] for s in body["suppliers"]] == ["IEK"]


def test_methods_are_switchable(client):
    """Формула партнёра и наш прогноз переключаются в запросе."""
    for method in ("baseline", "smoothed"):
        body = client.post("/api/v1/orders/calculate", json={"method": method}).json()
        assert body["method"] == method


def test_unknown_method_is_rejected(client):
    response = client.post("/api/v1/orders/calculate", json={"method": "волшебство"})
    assert response.status_code == 422
    assert "available" in response.json()["error"]["details"]


def test_single_sku_card(client):
    body = client.get("/api/v1/orders/300200428_").json()
    assert body["code"] == "300200428_"
    assert body["supplier"] == "Systeme Electric"
    assert body["reasons"]


def test_unknown_sku_returns_404(client):
    response = client.get("/api/v1/orders/нет-такого")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_selfcheck_passes_all_requirements(client):
    """Пять проверок из пункта 7 ТЗ проходят вживую."""
    body = client.get("/api/v1/selfcheck").json()

    assert body["total"] == 5
    assert body["passed"] == 5, [c for c in body["checks"] if not c["passed"]]


def test_stats(client):
    body = client.get("/api/v1/stats").json()
    assert body["skus"] == 2
    assert set(body["suppliers"]) == {"IEK", "Systeme Electric"}
