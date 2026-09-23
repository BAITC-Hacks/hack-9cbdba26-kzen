def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["components"]["skus"] == "2"
    assert "smoothed" in body["components"]["forecasters"]


def test_process_time_header(client):
    response = client.get("/health")
    assert "X-Process-Time" in response.headers
    assert float(response.headers["X-Process-Time"]) >= 0


def test_metrics_counts_requests(client):
    client.get("/health")
    body = client.get("/metrics").json()
    assert body["requests_total"] >= 1
    assert "p95" in body["latency_ms"]
