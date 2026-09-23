# Формат данных для фронтенда

Документ описывает, какие данные фронт получает и отправляет на каждом экране прототипа `prototype_source.dc.html`. Хранение и внутренний расчёт определяет бэкенд: здесь зафиксированы форма данных и список запросов. Имена типов (`RecommendationRow`, `SkuExplanation` и т. д.) нужны, чтобы на них ссылаться. Сводная таблица всех запросов — в разделе 8.

## 0. Принципы

1. **Фронт не считает.** Все количества, статусы, срочность, тексты объяснений и права на действия приходят с бэка. Фронт только форматирует и отображает.
2. **Числа сырые, тексты готовые.** Числовые поля — `number` без форматирования; фронт выводит их в формате `ru-RU` (`1 234`, `2,10`). Поля `*_text`, `formula`, `reason_short` и `hint` — готовые строки для вывода как есть.
3. **`null` ≠ `0`.** `null` — данных нет (показывается «н/д» или «—»), `0` — настоящий ноль. Заказ, который не удалось рассчитать, — это `null`, а не `0`.
4. **Любое действие возвращает обновлённое состояние.** После каждой операции записи приходит `ActionResult` (раздел 1.9), и фронт обновляет шапку и изменённые объекты без повторной загрузки экрана.
5. **Права приходят с бэка.** Доступность кнопок определяется объектом `permissions`, фронт не вычисляет её сам.

---

## 1. Общие типы

### 1.1 Скаляры

| Тип | Формат | Пример |
|---|---|---|
| `Date` | `YYYY-MM-DD` | `"2026-10-05"` |
| `DateTime` | ISO 8601 с поясом | `"2026-09-23T14:05:00+05:00"` |
| `Month` | `YYYY-MM` | `"2026-06"` |
| `SkuId` | строка, стабильная | `"SE:ЦБ-004121"` |
| `SupplierId` | `"SE"` \| `"IEK"` | `"SE"` |

### 1.2 Количество

```json
{ "value": 84, "unit": "шт" }
```
`value: number | null`. Единица всегда передаётся вместе с числом. Для товара приходят две единицы: `unit` (продажи и учёта) и `purchase_unit` (закупки). Заказ всегда выражен в `purchase_unit`.

### 1.3 Перечисления

| Тип | Значения | Подпись в интерфейсе |
|---|---|---|
| `SkuStatus` | `order`, `enough`, `needs_data`, `insufficient_history` | Заказать · Запаса достаточно · Нужны данные · Недостаточно истории |
| `Urgency` | `urgent`, `this_cycle`, `none`, `unknown` | Срочно · В этом цикле · Нет · н/д |
| `OrderStatus` | `draft`, `submitted`, `approved` | Черновик · На согласовании · Утверждена |
| `Role` | `manager`, `head` | Менеджер закупа · Руководитель закупок |
| `Origin` | `real`, `synthetic`, `assumption`, `manual`, `imported`, `none` | реальные · синтетика · предположение · ручной ввод · импорт · нет данных |
| `SourceUsage` | `used`, `partial`, `not_used` | используется · частично · не используется |

Подписи можно держать на фронте или получать с бэка полем `*_label` — достаточно согласовать один вариант.

### 1.4 Страница списка

```json
{ "items": [], "page": 1, "page_size": 100, "total": 2463, "pages": 25 }
```

### 1.5 Шапка (`AppHeader`)

Приходит на каждом экране и в каждом `ActionResult`. Из неё строятся верхняя строка и плашки.

```json
{
  "warehouse": { "id": "ALM", "name": "Алматы" },
  "category_filter": null,
  "calc_date": "2026-09-23",
  "data_cut_date": "2026-09-22",
  "calc_at": "2026-09-23T14:05:00+05:00",
  "calc_stale": false,
  "snapshot_age_days": 1,
  "snapshot_stale": false,
  "what_if_active": false,
  "data_mode": "demo",
  "data_mode_text": "Позиции и числа по SKU — синтетика; объёмы выгрузок — реальные",
  "order": { "version": 3, "status": "draft", "approved_at": null },
  "role": "manager",
  "user": { "id": "u1", "name": "Айгерим С." }
}
```

| Поле | Как показывать |
|---|---|
| `calc_at` | «Расчёт: …»; `null` — «не запускался» |
| `calc_stale` | `true` — баннер «Данные или параметры изменились — пересчитать» |
| `snapshot_stale` | `true` — плашка «Снимок остатка старше 7 дней» |
| `what_if_active` | `true` — плашка «Сценарий „что если“ активен» |
| `data_mode` | `demo`, `mixed` или `imported`; текст плашки — `data_mode_text` |

### 1.6 Проблема данных по позиции (`SkuIssue`)

```json
{ "key": "no_free_stock", "text": "нет снимка свободного остатка на 22.09.2026", "resolve": { "field": "free_stock", "input": "number", "unit": "шт" } }
```

Варианты `key` и того, что фронт показывает для исправления:

| `key` | Поле `resolve.field` | Элемент |
|---|---|---|
| `no_free_stock` | `free_stock` | числовой ввод |
| `unit_factor_unconfirmed` | `unit_factor` | числовой ввод, `resolve.candidate` — подсказка |
| `moq_missing` | `multiple` | числовой ввод |
| `moq_semantics_unconfirmed` | `moq_semantics` | две кнопки: `min` / `multiple`, `resolve.value_hint` — число из справочника |

### 1.7 Предположение (`Assumption`)

```json
{ "label": "Срок поставки L / период пересмотра R", "value_text": "Systeme 30/14 дн., ИЭК 35/14 дн.", "origin": "assumption" }
```

### 1.8 Ошибка

```json
{ "error": { "code": "ORDER_NOT_SUBMITTED", "message": "Утвердить можно только версию на согласовании", "field": null } }
```
Фронт показывает `message`. Если указано `field`, сообщение выводится рядом с этим полем.

Коды, по которым фронт ведёт себя по-особому:

| `code` | Поведение |
|---|---|
| `VERSION_CONFLICT` | «Список изменён другим пользователем» и перезагрузка данных |
| `WHAT_IF_ACTIVE` | Подсказка сбросить сценарий |
| `REASON_REQUIRED` | Подсветить поле «Причина» |
| `FORBIDDEN_ROLE` | Скрыть или заблокировать действие |

### 1.9 Результат действия (`ActionResult`)

```json
{
  "header": { "…": "AppHeader" },
  "sku": { "…": "SkuExplanation — если действие по позиции" },
  "row": { "…": "RecommendationRow — та же позиция для таблицы" },
  "order": { "…": "OrderCurrent — если изменился заказ" },
  "settings": { "…": "Settings — если изменились настройки" },
  "import_report": { "…": "ImportReport — после применения импорта" },
  "log_entry": { "…": "AuditEntry — запись в журнале об этом действии" },
  "toast": "Остаток введён вручную: 40 шт"
}
```
Все поля, кроме `header`, необязательные: приходит то, что изменилось.

---

## 2. Экран 01 — Данные и параметры

### 2.1 Получает: `DataOverview`
Предлагаемый адрес: `GET /data/overview`

```json
{
  "header": { "…": "AppHeader" },
  "sources": [
    {
      "key": "se-path",
      "supplier": { "id": "SE", "name": "Systeme Electric" },
      "type_text": "Товар в пути + рабочий расчёт (TDSheet)",
      "usage_text": "Свободный остаток, резерв, путь, категории",
      "freshness_text": "22.09.2026",
      "volume_text": "497 кодов",
      "volume_origin": "real",
      "file": { "name": "Товар в пути_SystemElectric на 22.09.2026.xlsx", "sheets": 2, "rows": 512, "status": "applied", "status_text": "применён" },
      "import_id": "imp_7f2"
    }
  ],
  "matching": [
    { "label": "Systeme: коды продаж ↔ снимок остатка (TDSheet)", "value_text": "469 / 554", "origin": "real" }
  ],
  "readiness": [
    { "supplier": { "id": "SE", "name": "Systeme Electric" }, "calculated": 7, "needs_data": 1, "insufficient_history": 1 }
  ],
  "assumptions": [ { "…": "Assumption" } ],
  "issues": [
    { "supplier_text": "ИЭК", "check_text": "Полнота", "problem_text": "Нет свободного остатка на 22.09.2026.", "handling_text": "«Нужны данные»; остаток можно ввести вручную." }
  ],
  "document_rules": [
    { "doc_type": "Реализация", "rule_text": "Продажа, входит в спрос", "editable": false },
    { "doc_type": "Возврат", "rule_text": null, "editable": true, "setting": "returns_rule" }
  ],
  "settings": { "…": "Settings" }
}
```

| Поле | Примечание |
|---|---|
| `sources[].file` | `null` — файл не загружен, кнопка «Загрузить .xlsx» |
| `sources[].import_id` | Нужен, чтобы открыть панель сопоставления колонок |
| `document_rules` | Если `editable: true`, строка управляется настройкой `setting` |

### 2.2 Получает и отправляет: `Settings`

```json
{
  "warehouse_id": "ALM",
  "warehouse_options": [{ "id": "ALM", "name": "Алматы" }],
  "category_filter": null,
  "category_options": [{ "value": null, "label": "Все" }, { "value": "SE|1", "label": "Категория 1" }, { "value": "IEK|—", "label": "Без категории (ИЭК)" }],
  "calc_date": "2026-09-23",
  "calc_date_min": "2026-09-23",
  "calc_date_max": "2026-12-31",
  "suppliers": [
    { "id": "SE", "name": "Systeme Electric", "lead_time_days": 30, "review_days": 14, "horizon_days": 44 }
  ],
  "categories": [
    { "key": "SE|1", "label": "Категория 1", "safety_days": 10, "season_coef": null }
  ],
  "one_off_threshold_x_median": 3,
  "returns_rule": "net",
  "excess_months": 2
}
```

Изменение настроек — частичный объект, в котором только изменённые поля:

```json
{ "suppliers": [{ "id": "SE", "lead_time_days": 35 }] }
```
В ответ приходит `ActionResult` с полным `settings` и `header` (`calc_stale: true`).

| Поле | Элемент | Ограничения |
|---|---|---|
| `calc_date` | выбор даты | `calc_date_min` … `calc_date_max` |
| `lead_time_days`, `review_days` | число | ≥ 1 |
| `safety_days` | число | ≥ 0 |
| `season_coef` | число или пусто | `null` — как у бренда или SKU |
| `one_off_threshold_x_median` | число, шаг 0,5 | ≥ 1,5 |
| `returns_rule` | переключатель | `net` — вычитать в месяце, `ignore` — не учитывать |
| `excess_months` | число, шаг 0,5 | ≥ 0,5 |

### 2.3 Импорт файла

**Отправляет:** multipart `file`, `source_key` (например, `se-path`).

**Получает: `ImportFile`**

```json
{
  "import_id": "imp_7f2",
  "source_key": "se-path",
  "title_text": "Systeme Electric · Товар в пути + рабочий расчёт (TDSheet)",
  "file_name": "Товар в пути_SystemElectric на 22.09.2026.xlsx",
  "status": "parsed",
  "status_text": "прочитан, проверьте колонки",
  "progress": null,
  "error_text": null,
  "sheets": [{ "index": 0, "name": "TDSheet", "rows": 512 }],
  "sheet_index": 0,
  "header_row": 2,
  "columns": [{ "index": 0, "letter": "A", "header": "Код" }, { "index": 1, "letter": "B", "header": "Номенклатура" }],
  "fields": [
    { "key": "code", "label": "Код 1С", "kind": "column", "required": true, "value": 0 },
    { "key": "qty", "label": "Количество в пути", "kind": "column", "required": false, "value": 6 },
    { "key": "row", "label": "Строка с коэффициентами (№ строки)", "kind": "row_number", "required": true, "value": 3 }
  ],
  "options": [{ "key": "returns_in_monthly", "label": "Месячные продажи уже за вычетом возвратов", "value": true }]
}
```

| `status` | Что показывает фронт |
|---|---|
| `uploading`, `parsing` | индикатор; `progress` — число от 0 до 1 или `null` |
| `parsed` | панель сопоставления колонок |
| `applied` | «применён», отчёт о сопоставлении |
| `failed` | `error_text` |

`fields[].value`: номер колонки (`kind: column`), номер строки (`kind: row_number`) или `null` («— нет —»). Вариантов у поля `kind` всего два.

**Отправляет (изменение сопоставления):**
```json
{ "sheet_index": 0, "header_row": 2, "fields": { "code": 0, "qty": 6 }, "options": { "returns_in_monthly": true } }
```
При смене `sheet_index` или `header_row` в ответ приходит новый `ImportFile` с пересчитанными `columns` и автосопоставлением.

**Отправляет (применить импорт поставщика):** `{ "supplier_id": "SE" }` для всех загруженных файлов поставщика или `{ "import_id": "…" }` для одного файла.
**Получает:** `ActionResult` плюс `import_report`:
```json
{ "supplier_id": "SE", "ok": true, "message_text": "Импортировано 554 позиции",
  "counters": [{ "label": "коды продаж ↔ свободный остаток", "value_text": "469 / 554" }, { "label": "дубликаты кодов, нечисловые MOQ", "value_text": "0, 26" }] }
```
При ошибке: `ok: false`, в `message_text` — причина (например, «Файл продаж: нужны колонки „Код 1С“, „Первый месяц“, „Последний месяц“»).

**Вернуть демо-набор:** `{ "supplier_id": "SE", "reset": true }` → `ActionResult`.

### 2.4 Запуск расчёта
**Отправляет:** `{}`
**Получает:** `ActionResult`, где `header.calc_at` обновлён, а `toast` содержит, например, «Расчёт выполнен: 13 позиций». После этого фронт переходит на экран 02.

### 2.5 Сброс сессии
**Отправляет:** `{ "confirm": true }` → `ActionResult`. Сбрасываются только ручные правки, журнал и версии этого расчёта.

---

## 3. Экран 02 — Рекомендации

### 3.1 Отправляет: `RecommendationsQuery`

```json
{ "q": "City9", "supplier_id": null, "category": null, "status": null, "sort": "deficit", "page": { "SE": 1, "IEK": 1 }, "page_size": 100, "what_if": null }
```
`sort`: `deficit` (по сроку дефицита) или `code`. Если `what_if` не `null`, это `{ "delay_days": 7, "demand_pct": 10 }`.

### 3.2 Получает: `RecommendationsPage`

```json
{
  "header": { "…": "AppHeader" },
  "summary": { "order": 5, "enough": 2, "needs_data": 5, "insufficient_history": 1, "excess": 1 },
  "groups": [
    {
      "supplier": { "id": "SE", "name": "Systeme Electric" },
      "total": 9, "page": 1, "pages": 1,
      "count_text": "9 поз.",
      "rows": [ { "…": "RecommendationRow" } ]
    }
  ],
  "what_if": null,
  "category_trends": null
}
```
Группы без строк не приходят. `what_if` повторяет применённый сценарий или равен `null`.

### 3.3 `RecommendationRow`

```json
{
  "sku_id": "SE:ЦБ-004121",
  "supplier": { "id": "SE", "name": "Systeme Electric" },
  "code_1c": "ЦБ-004121",
  "supplier_article": "C9F34116",
  "name": "Выключатель автоматический City9 Set 1P 16А C 4,5кА",
  "category": "1",
  "unit": "шт",
  "purchase_unit": "шт",
  "unit_text": "шт",
  "free_stock": 35,
  "inbound": [{ "qty": 25, "eta": "2026-10-05" }, { "qty": 40, "eta": "2026-11-20" }],
  "recommended_qty": 84,
  "final_qty": 84,
  "manual": false,
  "reason_short": "112 + стр. 21 − 35 − путь 25 = 73 → 84 (мин. 12, крат. 12)",
  "urgency": "urgent",
  "cover_days": 17,
  "status": "order",
  "excess": false
}
```

| Колонка | Поле | Отображение |
|---|---|---|
| Поставщик | `supplier.name` | |
| Код 1С / Артикул / Наименование | `code_1c`, `supplier_article`, `name` | |
| Ед. | `unit_text` | `"м / бухта"`, если единицы продажи и закупки разные |
| Свободно | `free_stock` | `null` → «н/д» |
| Путь · ETA | `inbound[]` | `25 · 05.10, 40 · 20.11`; пусто → «—» |
| Заказ | `final_qty` + `purchase_unit` | `null` → «—»; `manual: true` → значок ✎ |
| Обоснование | `reason_short` | как есть |
| Срочность | `urgency` | подпись из 1.3 |
| Статус | `status`, `excess` | тег статуса; при `excess: true` — второй тег «Избыточный запас» |

Клик по строке открывает экран 03 с `sku_id`.

### 3.4 Тренды по категориям: `CategoryTrend[]`
Загружаются по раскрытию блока (`include=category_trends` или отдельный запрос).

```json
[
  { "label": "Systeme Electric · кат. 1", "unit": "шт", "sku_count": 5,
    "months": [{ "month": "2025-10", "qty": 470, "partial": false }],
    "slope_pct_per_month": 2.4, "slope_text": "+2,4% / мес" }
]
```
`slope_pct_per_month: null` → «н/д». Столбик месяца с `partial: true` рисуется бледным.

### 3.5 Сценарий «что если»
Фронт отправляет `RecommendationsQuery` с заполненным `what_if` и получает `RecommendationsPage` с `header.what_if_active: true`. В версию заказа сценарий не сохраняется. Сброс — тот же запрос с `what_if: null`.

---

## 4. Экран 03 — Объяснение SKU

### 4.1 Получает: `SkuExplanation`
Предлагаемый адрес: `GET /skus/{sku_id}/explanation`

```json
{
  "header": { "…": "AppHeader" },
  "nav": { "prev_sku_id": "IEK:ЦБ-109041", "next_sku_id": "SE:ЦБ-004125" },

  "sku": {
    "sku_id": "SE:ЦБ-004121", "supplier": { "id": "SE", "name": "Systeme Electric" },
    "code_1c": "ЦБ-004121", "supplier_article": "C9F34116", "category": "1",
    "name": "Выключатель автоматический City9 Set 1P 16А C 4,5кА",
    "unit": "шт", "purchase_unit": "шт"
  },
  "status": "order",
  "urgency": "urgent",
  "excess": false,
  "issues": [],

  "chart": {
    "base_from": "2026-03", "base_to": "2026-08",
    "months": [
      { "month": "2026-03", "label": "Мар", "sales": 55, "restored": 0, "one_off_excluded": 480, "one_off_included": 0, "in_base": true, "partial": false, "missing": false }
    ],
    "forecast": [{ "month": "2026-10", "label": "П·окт", "qty": 72 }, { "month": "2026-11", "label": "П·ноя", "qty": 76 }]
  },

  "events": [
    { "id": "d1", "kind": "document", "qty": 480, "included": false,
      "title_text": "Разовая сделка: 480 шт — исключена",
      "note_text": "Реализация ЭК-0412 от 14.03.2026, клиент K-203. Порог 171 шт = 3 × медиана 57. Исходные строки сохранены." }
  ],
  "regular_clients": [
    { "client_id": "K-044", "title_text": "Клиент K-044: 12 документов — регулярный, учтён в спросе", "note_text": "25–25 шт на документ, ниже порога 105 шт" }
  ],
  "stockouts": [
    { "id": "s1", "month": "2026-06", "availability": 0.35, "origin": "synthetic", "removable": false,
      "title_text": "июн 2026, доступен ~35% месяца", "note_text": "Продано 22, восстановлено +41. Источник: синтетика" }
  ],
  "stockout_candidates": [ { "month": "2026-05", "title_text": "май 2026 — остаток на начало месяца 0" } ],
  "stockout_month_options": [ { "month": "2026-03", "label": "мар 2026" } ],

  "demand": {
    "raw_avg": 138, "regular_avg": 64, "daily": 2.1,
    "season": 1.15, "season_source_text": "агрегат бренда",
    "trend": 0.06, "trend_source_text": "оценка аналитика", "trend_manual": false,
    "trend_estimate": 0.04, "trend_estimate_text": "+4%"
  },

  "steps": [
    { "key": "regular_demand", "label": "Регулярный спрос", "value_text": "64 /мес", "note_text": "мар–авг 2026 после исключения разовых сделок и поправки на stockout; 2,10 шт/дн", "emphasis": false },
    { "key": "forecast", "label": "Прогноз на H = L 30 + R 14 = 44 дн.", "value_text": "112", "note_text": "2,10 × 44 × сезон 1,15 × прирост 1,06", "emphasis": false },
    { "key": "safety", "label": "+ Страховой запас", "value_text": "+21", "note_text": "10 дн (правило категории 1) × 2,10", "emphasis": false },
    { "key": "free", "label": "− Свободный остаток", "value_text": "−35", "note_text": "снимок 22.09.2026; резерв 8 уже вычтен", "emphasis": false },
    { "key": "inbound", "label": "− Поступления в пределах H", "value_text": "−25", "note_text": "25 через 12 дн.; 40 через 58 дн. (за горизонтом)", "emphasis": false },
    { "key": "need", "label": "= Потребность", "value_text": "73 шт", "note_text": "max(0, прогноз + страховой − свободно − путь)", "emphasis": true },
    { "key": "order", "label": "Рекомендуемый заказ", "value_text": "84 шт", "note_text": "минимум 12, кратность 12: 12 × ceil(max(потребность, 12) / 12)", "emphasis": true, "large": true }
  ],
  "explanation_text": "На период защиты 44 дн. прогноз 112 шт., страховой запас 21, свободно 35, вовремя ожидается 25. Потребность 73 шт. С учётом минимума 12 и кратности 12 рекомендуем 84 шт. …",

  "params": { "lead_time_days": 30, "review_days": 14, "season": 1.15, "overridden": false },

  "stock": { "free": 35, "free_manual": false, "reserve": 8, "cover_days": 17, "cover_text": "17 дн.", "early_risk": false },
  "inbound": [
    { "id": "i1", "qty": 25, "eta": "2026-10-05", "days": 12, "doc_text": "Путь П-2291", "counted": true, "in_horizon": true,
      "where_text": "внутри H (через 12 дн.)" }
  ],

  "manual": { "active": false, "qty": null, "reason": null, "note_text": null },
  "price": { "value": null, "manual": false, "text": "не подтверждена" },
  "cost": { "value": null, "text": "—" },

  "provenance": [
    { "input": "Свободный остаток", "source_text": "Товар в пути_SystemElectric на 22.09.2026 · TDSheet", "origin": "synthetic" }
  ]
}
```

Как отображаются блоки:

| Блок | Поля | Правило |
|---|---|---|
| Заголовок | `sku`, `status`, `excess`, `urgency` | |
| «Нужны данные» | `issues[]` | Блок виден, если `issues` не пуст; элементы ввода — по `issues[].resolve` (1.6) |
| График | `chart.months`, `chart.forecast` | Слои столбика снизу вверх: `sales`, `one_off_included`, `restored` (штриховка), прогноз (пунктир), `one_off_excluded` — маркер с подписью «+480». `missing: true` → «н/д». `in_base` — подсветка фона. `partial` — бледный цвет |
| Поправки | `events`, `regular_clients`, `stockouts`, `stockout_candidates` | Кнопки: вернуть или исключить сделку, удалить период (`removable`), подтвердить кандидата |
| Добавить период | `stockout_month_options` | Выбор месяца и поле «доступен, % месяца» (5–95) |
| Спрос | `demand` | Кнопка «Использовать» ставит `trend_estimate`; «Вернуть исходный» — при `trend_manual: true` |
| Расчёт | `steps`, `explanation_text` | `emphasis` — жирный с разделителем; `large` — крупная цифра |
| Параметры позиции | `params` | Плейсхолдеры полей L/R/сезонность; «Как у поставщика» — при `overridden: true` |
| Остаток и поступления | `stock`, `inbound` | `counted: false` — строка бледная, кнопка «Учитывать»; `early_risk: true` — предупреждение |
| Корректировка | `manual`, `price`, `cost` | |
| Источники входов | `provenance` | Тег по `origin` |

### 4.2 Действия по позиции

Каждое действие возвращает `ActionResult` с обновлёнными `sku` и `row`, а также `order`, если изменился заказ. Поле `reason` обязательно там, где указано.

| Действие | Отправляет | `reason` |
|---|---|---|
| Ручное количество | `{ "action": "set_manual_qty", "qty": 96, "reason": "подтверждён проектный заказ" }` | да |
| Вернуть рекомендацию | `{ "action": "clear_manual_qty" }` | — |
| Ввести свободный остаток | `{ "action": "set_override", "field": "free_stock", "value": 40 }` | нет (можно передать) |
| Подтвердить коэффициент единиц | `{ "action": "set_override", "field": "unit_factor", "value": 100 }` | нет |
| Задать кратность | `{ "action": "set_override", "field": "multiple", "value": 10 }` | нет |
| Смысл «Мин. разр. к отгр.» | `{ "action": "set_override", "field": "moq_semantics", "value": "min" }` | нет |
| Прирост вручную | `{ "action": "set_override", "field": "trend", "value": 0.08, "source": "manager" }` | нет |
| Использовать оценку по истории | `{ "action": "set_override", "field": "trend", "value": 0.04, "source": "history_estimate" }` | нет |
| Параметры позиции | `{ "action": "set_override", "field": "sku_params", "value": { "lead_time_days": 40, "review_days": null, "season": 1.2 } }` | нет |
| Цена закупки | `{ "action": "set_override", "field": "price", "value": 1250.5 }` | нет |
| Сбросить переопределение | `{ "action": "clear_override", "field": "trend" }` | — |
| Разовая сделка в спрос / из спроса | `{ "action": "set_event_included", "event_id": "d1", "included": true }` | нет |
| Учитывать поставку | `{ "action": "set_inbound_counted", "inbound_id": "i2", "counted": false }` | нет |
| Добавить период отсутствия | `{ "action": "add_stockout", "month": "2026-07", "availability": 0.5 }` | нет |
| Подтвердить кандидата | `{ "action": "confirm_stockout_candidate", "month": "2026-05" }` | нет |
| Удалить период | `{ "action": "remove_stockout", "stockout_id": "s3" }` | — |

В действиях, которые меняют заказ, фронт передаёт номер версии, которую видит (`order_version`). Если версия устарела, приходит ошибка `VERSION_CONFLICT`.

---

## 5. Экран 04 — Проверка и экспорт

### 5.1 Получает: `OrderCurrent`

```json
{
  "header": { "…": "AppHeader" },
  "version": 3,
  "status": "submitted",
  "status_text": "v3 на согласовании",
  "approved_at": null,
  "approved_by": null,
  "hint_text": "Проверьте список и утвердите или верните на доработку.",
  "permissions": { "can_edit": true, "can_submit": false, "can_approve": true, "can_reject": true, "can_export": false },
  "blocked_reason_text": null,
  "groups": [
    {
      "supplier": { "id": "SE", "name": "Systeme Electric" },
      "summary_text": "5 строк к заказу · изменено вручную: 1",
      "cost_text": "Сумма: цены не подтверждены",
      "pending_text": "1 поз. без количества (нужны данные) — не попадут в экспорт",
      "lines": [
        { "sku_id": "SE:ЦБ-004121", "code_1c": "ЦБ-004121", "name": "Выключатель автоматический City9 Set 1P 16А C 4,5кА",
          "purchase_unit": "шт", "recommended_qty": 84, "final_qty": 96, "manual": true,
          "reason": "подтверждён проектный заказ", "price": null, "cost": null }
      ]
    }
  ],
  "export_settings": {
    "format": "csv", "separator": ";", "encoding": "utf-8-bom",
    "columns": [ { "key": "version", "label": "Версия", "enabled": true } ],
    "format_options": ["csv", "xlsx"], "separator_options": [";", ",", "tab"], "encoding_options": ["utf-8-bom", "cp1251"],
    "note_text": "Точный состав полей нужно сверить с образцом файла импорта 1С."
  }
}
```

| Элемент | Правило |
|---|---|
| Кнопка «Отправить на согласование» | Видна при `header.role = manager`, доступна при `permissions.can_submit` |
| «Утвердить» и «Вернуть на доработку» | Видны при `role = head`, доступны при `can_approve` и `can_reject` |
| Экспорт (общий и по поставщику) | Доступен при `can_export` |
| `blocked_reason_text` | Причина, по которой действие недоступно (например, активен сценарий «что если») |
| Строка заказа | «Рекомендация» — `recommended_qty` (`null` → «—»); «Итог» — `final_qty` и ✎ при `manual`; под названием — `reason`; «Сумма» — `cost` (`null` → «—») |

### 5.2 Действия со статусом

| Действие | Отправляет | Получает |
|---|---|---|
| Отправить на согласование | `{ "action": "submit", "order_version": 3 }` | `ActionResult` с `order` |
| Утвердить | `{ "action": "approve", "order_version": 3 }` | `ActionResult` с `order` (`status: approved`) и новой записью в `versions` |
| Вернуть на доработку | `{ "action": "reject", "order_version": 3, "comment": "проверить кабель" }` | `ActionResult` |
| Сменить роль (демо) | `{ "role": "head" }` | `ActionResult` с новыми `header` и `permissions` |

### 5.3 Экспорт
**Отправляет:**
```json
{ "version": 3, "supplier_id": "SE", "format": "xlsx", "separator": ";", "encoding": "utf-8-bom", "columns": ["version", "approved_at", "supplier", "code_1c", "supplier_article", "name", "purchase_unit", "recommended_qty", "final_qty", "manual", "reason", "price", "cost"] }
```
`supplier_id: null` — экспорт всех поставщиков.

**Получает:** файл. Имя берётся из `Content-Disposition` (например, `zakaz_almaty_se_v3.xlsx`), фронт отдаёт его на скачивание.

Колонки экспорта:

| key | Подпись |
|---|---|
| `version` | Версия |
| `approved_at` | Утверждено |
| `supplier` | Поставщик |
| `code_1c` | Код 1С |
| `supplier_article` | Артикул поставщика |
| `name` | Наименование |
| `purchase_unit` | Ед. закупки |
| `recommended_qty` | Рекомендация |
| `final_qty` | Итог |
| `manual` | Ручная корректировка |
| `reason` | Причина |
| `price` | Цена |
| `cost` | Сумма |

### 5.4 Утверждённые версии: `OrderVersionSummary[]`

```json
[ { "version": 2, "approved_at": "2026-09-23T15:10:00+05:00", "approved_by_text": "Руководитель закупок", "lines": 6 } ]
```

### 5.5 Сравнение: `VersionDiff`
**Отправляет:** `{ "version": 2, "against": "current" }`

```json
{
  "title_text": "Отличия v2 от текущего списка",
  "rows": [ { "code_1c": "ЦБ-004121", "name": "…", "in_version_text": "84 шт", "current_text": "96 шт" } ]
}
```
Пустой `rows` → «Отличий нет».

### 5.6 Журнал: `AuditEntry[]` (постранично)

```json
[ { "version": 3, "text": "ЦБ-004121: заказ 84 → 96 шт. Причина: подтверждён проектный заказ", "role": "manager", "user_text": "Айгерим С.", "at": "2026-09-23T14:20:00+05:00" } ]
```

---

## 6. Экран 05 — Проверки ТЗ

### 6.1 `ValidationScenarios`

```json
{
  "passed": 25, "total": 25, "summary_text": "Пройдено 25 из 25",
  "items": [
    { "n": 1, "name": "Достаточно свободного запаса", "expected_text": "Заказ 0, статус «запаса достаточно»", "actual_text": "заказ 0, «Запаса достаточно»", "passed": true }
  ]
}
```

### 6.2 `Backtest`

```json
{
  "note_text": "Сейчас — на демо-наборе; после импорта считается по реальным рядам.",
  "rows": [
    { "unit": "шт", "model": "raw_avg6", "model_text": "Сырые продажи, среднее 6 мес.", "sku_count": 11, "points": 52, "wape": 0.183, "mae": 12.4, "bias": 0.061, "best": false }
  ]
}
```
`wape` и `bias` — доли (0,183 → «18,3%»). `wape: null` → «не определён». Модели: `raw_avg6`, `regular_avg6`, `regular_trend`.

### 6.3 `SourceUsage[]`

```json
[ { "source_text": "Остатки по месяцам", "usage_text": "Нулевой начальный остаток → кандидат в stockout; применяется после подтверждения", "status": "used" } ]
```

---

## 7. Что фронт делает сам

- Форматирует числа, даты и проценты (`ru-RU`), выводит подписи перечислений.
- Хранит состояние фильтров, поиска, номера страницы, раскрытых блоков и черновиков полей ввода до отправки.
- Рисует график по числам из `chart`: масштаб — по максимуму столбиков без исключённых сделок.
- Показывает `toast` из `ActionResult`, баннеры по флагам `header`, обрабатывает ошибки по `error.code`.

Чего фронт не делает: не считает количества, статусы, срочность, суммы и права; не решает, какие позиции попадут в экспорт; не отправляет заказ поставщику.

---

## 8. Сводная таблица запросов

Базовый путь — `/api/v1`. Тело запросов и ответов — JSON, если не указано иное.

### 8.1 Общие правила транспорта

| Тема | Правило |
|---|---|
| Авторизация | `Authorization: Bearer <token>`; роль берётся из токена. Для демонстрации допускается заголовок `X-Role: manager \| head` |
| Действия | Одна точка на объект: `POST …/actions` с полем `action`. Список `action` — в разделах 4.2 и 5.2 |
| Версия заказа | Все действия, которые меняют заказ, передают `order_version`. Если версия устарела — `409` с кодом `VERSION_CONFLICT` |
| Загрузка файла | `multipart/form-data`, ответ `202` с `ImportFile`. Фронт опрашивает `GET /imports/{id}` раз в 1 с, пока статус не станет `parsed`, `applied` или `failed` |
| Скачивание | Ответ — файл (`text/csv` или `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) с заголовком `Content-Disposition`. При ошибке — JSON `Error` |
| Коды ответов | `200` — успех; `202` — принято в обработку; `400` — неверный запрос; `401` — нет авторизации; `403` — `FORBIDDEN_ROLE`; `404` — не найдено; `409` — конфликт состояния или версии; `422` — ошибка поля (`error.field`) |

### 8.2 Сессия и шапка

| Метод | Путь | Отправляет | Получает | Экран |
|---|---|---|---|---|
| GET | `/session` | — | `AppHeader` | все, при старте |
| PUT | `/session/role` | `{ "role": "head" }` | `ActionResult` | 04 (демо-переключатель) |
| POST | `/session/reset` | `{ "confirm": true }` | `ActionResult` | 01 |

### 8.3 Экран 01 — Данные и параметры

| Метод | Путь | Отправляет | Получает |
|---|---|---|---|
| GET | `/data/overview` | — | `DataOverview` (2.1) |
| PATCH | `/settings` | частичный `Settings` (2.2) | `ActionResult` с `settings` |
| POST | `/imports` | multipart: `file`, `source_key` | `202` + `ImportFile` (2.3) |
| GET | `/imports/{import_id}` | — | `ImportFile` |
| PATCH | `/imports/{import_id}` | `{ sheet_index, header_row, fields, options }` | `ImportFile` |
| POST | `/imports/apply` | `{ "supplier_id": "SE" }` или `{ "import_id": "…" }` | `ActionResult` с `import_report` |
| POST | `/imports/reset` | `{ "supplier_id": "SE" }` | `ActionResult` |
| POST | `/calculations` | `{}` | `ActionResult` (новый `header.calc_at`) |

### 8.4 Экран 02 — Рекомендации

| Метод | Путь | Отправляет | Получает |
|---|---|---|---|
| POST | `/recommendations/search` | `RecommendationsQuery` (3.1) | `RecommendationsPage` (3.2) |
| GET | `/analytics/category-trends` | query: `supplier_id`, `category`, `q` | `CategoryTrend[]` (3.4) |

`POST` для поиска выбран потому, что в запросе есть вложенные `page` и `what_if`. Запрос не меняет данные.

### 8.5 Экран 03 — Объяснение SKU

| Метод | Путь | Отправляет | Получает |
|---|---|---|---|
| GET | `/skus/{sku_id}/explanation` | — | `SkuExplanation` (4.1) |
| POST | `/skus/{sku_id}/actions` | `{ "action": "…", …, "order_version": 3 }` (4.2) | `ActionResult` с `sku`, `row`, `order` |

`sku_id` передаётся в URL-кодировке (`SE%3A%D0%A6%D0%91-004121`).

### 8.6 Экран 04 — Проверка и экспорт

| Метод | Путь | Отправляет | Получает |
|---|---|---|---|
| GET | `/orders/current` | — | `OrderCurrent` (5.1) |
| POST | `/orders/current/actions` | `{ "action": "submit" \| "approve" \| "reject", "order_version": 3, "comment": "…" }` (5.2) | `ActionResult` с `order` |
| PATCH | `/orders/current/export-settings` | `{ format, separator, encoding, columns: [{ key, enabled }] }` | `ActionResult` с `order` |
| POST | `/orders/export` | `ExportRequest` (5.3) | файл |
| GET | `/orders/versions` | — | `OrderVersionSummary[]` (5.4) |
| GET | `/orders/versions/{version}/diff` | query: `against=current` | `VersionDiff` (5.5) |
| GET | `/audit-log` | query: `page`, `page_size` | `Page<AuditEntry>` (5.6) |

### 8.7 Экран 05 — Проверки ТЗ

| Метод | Путь | Отправляет | Получает |
|---|---|---|---|
| GET | `/validation/scenarios` | — | `ValidationScenarios` (6.1) |
| GET | `/validation/backtest` | — | `Backtest` (6.2) |
| GET | `/validation/source-usage` | — | `SourceUsage[]` (6.3) |

### 8.8 Какие запросы вызывает каждый экран

| Экран | При открытии | При действиях |
|---|---|---|
| Любой | `GET /session` (один раз при старте) | — |
| 01 Данные | `GET /data/overview` | `PATCH /settings`, `POST /imports`, `GET/PATCH /imports/{id}`, `POST /imports/apply`, `POST /imports/reset`, `POST /calculations`, `POST /session/reset` |
| 02 Рекомендации | `POST /recommendations/search` | тот же запрос при смене фильтра, страницы или «что если»; `GET /analytics/category-trends` при раскрытии блока |
| 03 SKU | `GET /skus/{id}/explanation` | `POST /skus/{id}/actions`; «Пред. / След.» — `GET` по `nav.prev_sku_id` / `nav.next_sku_id` |
| 04 Экспорт | `GET /orders/current`, `GET /orders/versions`, `GET /audit-log` | `POST /orders/current/actions`, `PATCH /orders/current/export-settings`, `POST /orders/export`, `GET /orders/versions/{v}/diff`, `PUT /session/role` |
| 05 Проверки | `GET /validation/scenarios`, `GET /validation/backtest`, `GET /validation/source-usage` | — |

### 8.9 Порядок реализации

1. `GET /session`, `POST /recommendations/search`, `GET /skus/{id}/explanation`, `GET /orders/current` — на демо-наборе как фикстурах. После этого фронт уже показывает все основные экраны.
2. `POST /skus/{id}/actions` и `POST /orders/current/actions` — ручные правки, согласование, версии, журнал.
3. `POST /orders/export`, `GET /orders/versions*`.
4. Импорт: `/imports*`, `GET /data/overview`, `PATCH /settings`, `POST /calculations`.
5. `/analytics/category-trends`, `/validation/*`.
