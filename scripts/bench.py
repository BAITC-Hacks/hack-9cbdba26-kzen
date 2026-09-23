"""Замер латентности ключевых ручек закупщика. Запуск: python scripts/bench.py [--url ...]

Сервис должен быть запущен (`make api`). Цифры идут на слайд, поэтому:
- первые запросы отбрасываются как прогрев;
- тяжёлые ручки (расчёт, «что если») меряются меньшим числом повторов —
  они пересчитывают весь ассортимент, и 500 повторов заняли бы минуты.
В конце печатается сводка по статусам позиций — вторая половина цифр для защиты.
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections import Counter

import httpx

B = "/api/v1"


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(int(q * len(ordered)), len(ordered) - 1)]


def measure(client: httpx.Client, name: str, method: str, url: str, n: int, warmup: int,
            **kwargs) -> None:
    def one() -> float:
        started = time.perf_counter()
        client.request(method, url, **kwargs).raise_for_status()
        return (time.perf_counter() - started) * 1000

    for _ in range(warmup):
        one()
    timings = [one() for _ in range(n)]
    print(f"{name:<34} n={n:<4} p50 {percentile(timings, 0.5):7.1f} мс   "
          f"p95 {percentile(timings, 0.95):7.1f} мс   сред {statistics.mean(timings):7.1f} мс")


def all_rows(client: httpx.Client) -> list[dict]:
    """Все строки текущей версии: поиск отдаёт страницы по поставщикам, до 500 строк."""
    rows: list[dict] = []
    first = client.post(f"{B}/recommendations/search", json={"page_size": 500}).json()
    for group in first["groups"]:
        sid = group["supplier"]["id"]
        for page in range(1, group["pages"] + 1):
            body = {"page_size": 500, "supplier_id": sid, "page": {sid: page}}
            data = client.post(f"{B}/recommendations/search", json=body).json()
            rows += data["groups"][0]["rows"]
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--n", type=int, default=200, help="повторы для лёгких ручек")
    parser.add_argument("--heavy", type=int, default=10, help="повторы для пересчёта")
    args = parser.parse_args()

    with httpx.Client(base_url=args.url, timeout=120) as client:
        health = client.get("/health").json()
        session = client.get(f"{B}/session").json()
        print(f"Сервис: {health['status']}, SKU: {health['components'].get('skus')}, "
              f"данные: {session['data_mode']}, предупреждения: {health.get('warnings')}\n")

        client.post(f"{B}/session/reset")
        measure(client, "POST /calculations (агент)", "POST", f"{B}/calculations",
                args.heavy, 1, json={})
        rows = all_rows(client)
        sku_id = next(r["sku_id"] for r in rows if r["status"] == "order")

        measure(client, "GET /health", "GET", "/health", args.n, 20)
        measure(client, "POST /recommendations/search", "POST", f"{B}/recommendations/search",
                args.n, 20, json={"page_size": 100})
        measure(client, "  … с поиском по тексту", "POST", f"{B}/recommendations/search",
                args.n, 20, json={"q": "300", "page_size": 100})
        measure(client, "  … what-if задержка 14 дн", "POST", f"{B}/recommendations/search",
                args.heavy, 1, json={"what_if": {"delay_days": 14}})
        measure(client, "GET /skus/{id}/explanation", "GET",
                f"{B}/skus/{sku_id}/explanation", args.n, 20)
        measure(client, "GET /orders/current", "GET", f"{B}/orders/current", args.n, 20)

        # Экспорт доступен только после утверждения: проходим согласование один раз
        v = client.get(f"{B}/orders/current").json()["version"]
        client.post(f"{B}/orders/current/actions", json={"action": "submit", "order_version": v})
        client.put(f"{B}/session/role", json={"role": "head"})
        client.post(f"{B}/orders/current/actions", json={"action": "approve", "order_version": v})
        measure(client, "POST /orders/export (xlsx)", "POST", f"{B}/orders/export",
                args.heavy, 1, json={"version": v})
        client.post(f"{B}/session/reset")

        statuses = Counter(r["status"] for r in rows)
        review = sum(r["needs_review"] for r in rows)
        print(f"\nПозиций: {len(rows)}; статусы: {dict(statuses)}; "
              f"needs_review от агента: {review}")
        by_supplier = Counter(r["supplier"]["name"] for r in rows)
        print(f"По поставщикам: {dict(by_supplier)}")


if __name__ == "__main__":
    main()
