"""Middleware: идентификатор запроса, замер времени, счётчики.

Заголовок X-Process-Time — не украшение: это ваша цифра латентности на защите
и источник данных для /metrics. Считаем перцентили по скользящему окну,
чтобы не тащить Prometheus ради одного слайда.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter, deque

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import request_id_ctx


class MetricsCollector:
    """Счётчики в памяти. Окно ограничено, поэтому память не растёт."""

    def __init__(self, window: int = 2000) -> None:
        self._latencies: deque[float] = deque(maxlen=window)
        self._by_endpoint: Counter[str] = Counter()
        self.requests_total = 0
        self.errors_total = 0

    def observe(self, endpoint: str, elapsed_ms: float, status: int) -> None:
        self.requests_total += 1
        self._by_endpoint[endpoint] += 1
        self._latencies.append(elapsed_ms)
        if status >= 500:
            self.errors_total += 1

    def snapshot(self) -> dict:
        values = sorted(self._latencies)
        return {
            "requests_total": self.requests_total,
            "errors_total": self.errors_total,
            "latency_ms": {
                "p50": _percentile(values, 0.50),
                "p95": _percentile(values, 0.95),
                "p99": _percentile(values, 0.99),
                "max": round(values[-1], 2) if values else 0.0,
            },
            "by_endpoint": dict(self._by_endpoint),
        }


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(int(q * len(sorted_values)), len(sorted_values) - 1)
    return round(sorted_values[idx], 2)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, collector: MetricsCollector) -> None:
        super().__init__(app)
        self._collector = collector

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:8])
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        elapsed_ms = (time.perf_counter() - started) * 1000

        route = request.scope.get("route")
        endpoint = route.path if route else request.url.path
        self._collector.observe(endpoint, elapsed_ms, response.status_code)

        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}"
        response.headers["X-Request-ID"] = request_id
        return response


def register_middleware(app: FastAPI, collector: MetricsCollector) -> None:
    app.add_middleware(ObservabilityMiddleware, collector=collector)
