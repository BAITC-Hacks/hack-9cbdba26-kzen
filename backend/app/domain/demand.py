"""Подготовка спроса: очистка истории перед прогнозом.

Здесь живут три из четырёх требований Must have, и они намеренно вынесены
из прогнозиста: чистка одинаково нужна любому методу прогноза, а разница
между методами — только в способе экстраполяции.

Чистый Python без numpy: домен не зависит от библиотек, а объёмы тут
маленькие (36 месяцев на артикул).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from app.domain.entities import BulkOrderEvent, MonthPoint


@dataclass(frozen=True, slots=True)
class CleanedDemand:
    """История после очистки плюс то, что мы из неё узнали.

    removed_bulk и compensated нужны не только для расчёта: из них
    собирается обоснование, которое видит менеджер.
    """

    points: tuple[MonthPoint, ...]
    removed_bulk: float = 0.0           # сколько штук вычтено как разовые заказы
    bulk_months: tuple[date, ...] = ()  # в каких месяцах нашли аномалию
    bulk_invoices: tuple[str, ...] = () # накладные, подтвердившие клиентский сценарий
    compensated: float = 0.0            # сколько штук добавлено за месяцы без товара
    stockout_months: int = 0


def remove_bulk_orders(
    points: tuple[MonthPoint, ...], *, factor: float = 3.0
) -> tuple[tuple[MonthPoint, ...], float, list[date]]:
    """Убрать разовые крупные продажи (Must have 4).

    Месяц считается аномальным, если продажи превышают ожидаемый уровень
    в `factor` раз. Медиана, а не среднее — среднее само смещается выбросом,
    ради которого всё и затевалось.

    Ключевая тонкость: ожидаемый уровень берётся **по тому же календарному
    месяцу других лет**, если таких наблюдений хотя бы два. Иначе сезонный пик
    (декабрь у ёлочных гирлянд, ноябрь у обогревателей) выглядит как разовый
    заказ, срезается — и сезонность, которую требует Must have 2, исчезает.
    Два требования ТЗ здесь конфликтуют, и разрешается конфликт именно так.

    Почему по месяцам, а не по накладным: ID клиента в данных нет, а файл
    транзакций покрывает только часть истории. На уровне месяца сигнал
    сохраняется, а данные доступны по всему периоду.

    Аномальный месяц не выбрасывается целиком: он срезается до ожидаемого
    уровня, потому что регулярный спрос в этом месяце тоже был.
    """
    sold = [p.sold for p in points if p.sold > 0]
    if len(sold) < 4:
        return points, 0.0, []  # истории слишком мало, чтобы судить об аномалиях

    global_median = statistics.median(sold)
    cleaned: list[MonthPoint] = []
    removed = 0.0
    months: list[date] = []

    for p in points:
        expected = _expected_level(points, p, global_median)
        if p.sold > expected * factor:
            removed += p.sold - expected
            months.append(p.month)
            cleaned.append(
                MonthPoint(
                    month=p.month,
                    sold=expected,
                    stock_start=p.stock_start,
                    stock_known=p.stock_known,
                )
            )
        else:
            cleaned.append(p)

    return tuple(cleaned), removed, months


def remove_confirmed_bulk_orders(
    points: tuple[MonthPoint, ...], events: tuple[BulkOrderEvent, ...]
) -> tuple[tuple[MonthPoint, ...], float, list[date], list[str]]:
    """Вычесть избыток крупных накладных из соответствующего месяца.

    Транзакции покрывают не всю историю, поэтому они только подтверждают
    конкретные выбросы, но не заменяют помесячный источник спроса.
    """
    if not events:
        return points, 0.0, [], []

    excess_by_month: dict[date, float] = {}
    invoices_by_month: dict[date, list[str]] = {}
    for event in events:
        excess_by_month[event.month] = excess_by_month.get(event.month, 0.0) + event.excess
        invoices_by_month.setdefault(event.month, []).append(event.invoice)

    cleaned: list[MonthPoint] = []
    removed = 0.0
    months: list[date] = []
    invoices: list[str] = []
    for point in points:
        requested = excess_by_month.get(point.month, 0.0)
        deducted = min(max(0.0, point.sold), requested)
        if deducted > 0:
            removed += deducted
            months.append(point.month)
            invoices.extend(invoices_by_month[point.month])
        cleaned.append(
            MonthPoint(
                month=point.month,
                sold=max(0.0, point.sold - deducted),
                stock_start=point.stock_start,
                stock_known=point.stock_known,
            )
        )
    return tuple(cleaned), removed, months, invoices


def _expected_level(
    points: tuple[MonthPoint, ...], point: MonthPoint, fallback: float
) -> float:
    """Ожидаемый уровень продаж для месяца.

    Берём тот же календарный месяц других лет: если в прошлом ноябре продали
    столько же, это сезон, а не разовая сделка. Истории обычно два года,
    поэтому хватает одного наблюдения.

    Ограничение сверху нужно на случай, когда само это наблюдение было выбросом:
    тогда оно задрало бы порог и настоящий разовый заказ прошёл бы незамеченным.
    Потолок в три медианы оставляет место сезонности, но не бесконечное.
    """
    same_month = [
        p.sold
        for p in points
        if p.month.month == point.month.month and p.month != point.month and p.sold > 0
    ]
    if same_month:
        return min(statistics.median(same_month), fallback * 3)
    return fallback


def compensate_stockouts(
    points: tuple[MonthPoint, ...],
) -> tuple[tuple[MonthPoint, ...], float, int]:
    """Восстановить упущенный спрос в месяцы без товара (Must have 3).

    В месяцы, когда остатка не было, продажи занижены не из-за спроса,
    а из-за отсутствия товара. Если оставить их как есть, среднее падает,
    заказ выходит меньше, товара снова не хватает — цикл замыкается,
    и именно это приводит к «вечному дефициту» по части ассортимента.

    Замещаем такие месяцы средним по месяцам, когда товар был.
    """
    with_stock = [p.sold for p in points if not p.stockout]
    if not with_stock:
        return points, 0.0, len(points)

    normal = statistics.fmean(with_stock)
    cleaned: list[MonthPoint] = []
    added = 0.0
    count = 0

    for p in points:
        if p.stockout and p.sold < normal:
            added += normal - p.sold
            count += 1
            cleaned.append(
                MonthPoint(
                    month=p.month,
                    sold=normal,
                    stock_start=p.stock_start,
                    stock_known=p.stock_known,
                )
            )
        else:
            cleaned.append(p)

    return tuple(cleaned), added, count


def seasonality_factor(points: tuple[MonthPoint, ...], target_month: int) -> float:
    """Коэффициент сезонности для месяца поставки (Must have 2).

    Считается как отношение среднего по этому календарному месяцу за все годы
    к среднему по всей истории. Файл «Сезонность» от партнёра для этого не годится:
    там суммы в деньгах по всей компании, а не по артикулам.

    Нужно минимум два наблюдения по месяцу, иначе единичный всплеск
    превратится в «сезонность».
    """
    same_month = [p.sold for p in points if p.month.month == target_month]
    overall = [p.sold for p in points]
    if len(same_month) < 2 or not overall:
        return 1.0

    mean_all = statistics.fmean(overall)
    if mean_all <= 0:
        return 1.0

    factor = statistics.fmean(same_month) / mean_all
    return max(0.3, min(factor, 3.0))  # защита от диких значений на редких артикулах


def growth_factor(points: tuple[MonthPoint, ...], *, window: int = 6) -> float:
    """Коэффициент устойчивого роста (Must have 2).

    Сравниваем последние `window` месяцев с предыдущими `window`.
    Ограничение сверху и снизу — защита от артикулов, которые только появились
    или уходят из ассортимента: там отношение уходит в бесконечность.
    """
    if len(points) < window * 2:
        return 1.0

    recent = statistics.fmean([p.sold for p in points[-window:]])
    previous = statistics.fmean([p.sold for p in points[-window * 2 : -window]])
    if previous <= 0:
        return 1.0

    return max(0.5, min(recent / previous, 2.0))


def prepare(
    points: tuple[MonthPoint, ...], bulk_orders: tuple[BulkOrderEvent, ...] = ()
) -> CleanedDemand:
    """Полная подготовка истории: сначала выбросы, потом провалы наличия.

    Порядок важен: если сначала компенсировать stockout, разовый заказ
    завысит «нормальный» уровень, по которому считается компенсация.
    """
    stage0, confirmed_removed, confirmed_months, invoices = remove_confirmed_bulk_orders(
        points, bulk_orders
    )
    stage1, statistical_removed, statistical_months = remove_bulk_orders(stage0)
    stage2, added, stockouts = compensate_stockouts(stage1)
    return CleanedDemand(
        points=stage2,
        removed_bulk=confirmed_removed + statistical_removed,
        bulk_months=tuple(dict.fromkeys([*confirmed_months, *statistical_months])),
        bulk_invoices=tuple(dict.fromkeys(invoices)),
        compensated=added,
        stockout_months=stockouts,
    )
