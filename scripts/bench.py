"""Замер латентности. Запуск: python scripts/bench.py [--url ...] [--n 500]

Цифра из этого скрипта идёт прямо на слайд. Формулировка вида
«p50 8 мс, p95 17 мс, батч 0.1 мс на объект» убеждает жюри сильнее,
чем любые слова о производительности.

Важно: первые запросы отбрасываются как прогрев, иначе инициализация
библиотеки испортит медиану.
"""

from __future__ import annotations

import argparse
import statistics
import time

import httpx


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(int(q * len(ordered)), len(ordered) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--explain", action="store_true", help="считать факторы влияния")
    args = parser.parse_args()

    with httpx.Client(base_url=args.url, timeout=30) as client:
        health = client.get("/health").json()
        print(f"Сервис: {health['status']}, компоненты: {health['components']}")

        ids = client.get("/api/v1/analytics/samples", params={"limit": 20}).json()["ids"]
        if not ids:
            print("В датасете нет объектов — замеряем на произвольных признаках")

        # Каждый запрос с новым значением: иначе меряем скорость кэша, а не модели.
        def one(i: int) -> float:
            payload = {
                "subject_id": ids[i % len(ids)] if ids else None,
                "features": {"__bench": i},
                "explain": args.explain,
            }
            started = time.perf_counter()
            response = client.post("/api/v1/predict", json=payload)
            response.raise_for_status()
            return (time.perf_counter() - started) * 1000

        for i in range(args.warmup):
            one(i)

        timings = [one(i) for i in range(args.n)]

        print(f"\nОдиночные запросы (explain={args.explain}), всего {args.n}:")
        print(f"  p50  {percentile(timings, 0.50):.1f} мс")
        print(f"  p95  {percentile(timings, 0.95):.1f} мс")
        print(f"  p99  {percentile(timings, 0.99):.1f} мс")
        print(f"  сред {statistics.mean(timings):.1f} мс")

        if ids:
            items = [{"subject_id": i} for i in ids]
            started = time.perf_counter()
            client.post("/api/v1/predict/batch", json={"items": items}).raise_for_status()
            elapsed = (time.perf_counter() - started) * 1000
            per_item = elapsed / len(items)
            print(f"\nБатч {len(items)} объектов: {elapsed:.0f} мс ({per_item:.3f} мс на объект)")


if __name__ == "__main__":
    main()
