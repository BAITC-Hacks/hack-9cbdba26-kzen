import type { AppHeader, RecommendationsPage, SkuExplanation, OrderCurrent, ValidationScenarios } from '../types';

export const mockHeader: AppHeader = {
  warehouse: { id: 'ALM', name: 'Алматы' },
  category_filter: null,
  calc_date: '2026-09-23',
  data_cut_date: '2026-09-22',
  calc_at: '2026-09-23T14:05:00+05:00',
  calc_stale: false,
  snapshot_age_days: 1,
  snapshot_stale: false,
  what_if_active: false,
  data_mode: 'demo',
  data_mode_text: 'Позиции и числа по SKU — синтетика; объёмы выгрузок — реальные',
  order: { version: 3, status: 'draft', approved_at: null },
  role: 'manager',
  user: { id: 'u1', name: 'Айгерим С.' },
};

export const mockRecommendations: RecommendationsPage = {
  header: mockHeader,
  summary: { order: 8, enough: 3, needs_data: 2, insufficient_history: 1, excess: 1 },
  groups: [
    { supplier: { id: 'SE', name: 'Systeme Electric' }, total: 9, page: 1, pages: 1, count_text: '9 поз.',
      rows: [
        { sku_id: 'SE:ЦБ-004121', supplier: { id: 'SE', name: 'Systeme Electric' }, code_1c: 'ЦБ-004121', supplier_article: 'C9F34116', name: 'Выключатель автоматический City9 Set 1P 16А C 4,5кА', category: '1', unit: 'шт', purchase_unit: 'шт', unit_text: 'шт', free_stock: 35, inbound: [{ qty: 25, eta: '2026-10-05' }, { qty: 40, eta: '2026-11-20' }], recommended_qty: 84, final_qty: 84, manual: false, reason_short: '112 + стр. 21 − 35 − путь 25 = 73 → 84 (мин. 12, крат. 12)', urgency: 'urgent', cover_days: 17, status: 'order', excess: false },
        { sku_id: 'SE:ЦБ-004125', supplier: { id: 'SE', name: 'Systeme Electric' }, code_1c: 'ЦБ-004125', supplier_article: 'C9F34125', name: 'Выключатель автоматический City9 Set 1P 25А C 4,5кА', category: '1', unit: 'шт', purchase_unit: 'шт', unit_text: 'шт', free_stock: 12, inbound: [], recommended_qty: 60, final_qty: 60, manual: false, reason_short: '78 − 12 = 66 → 72 (крат. 12)', urgency: 'urgent', cover_days: 8, status: 'order', excess: false },
        { sku_id: 'SE:ЦБ-004132', supplier: { id: 'SE', name: 'Systeme Electric' }, code_1c: 'ЦБ-004132', supplier_article: 'C9F34132', name: 'Выключатель автоматический City9 Set 1P 32А C 4,5кА', category: '1', unit: 'шт', purchase_unit: 'шт', unit_text: 'шт', free_stock: 150, inbound: [{ qty: 120, eta: '2026-10-15' }], recommended_qty: 0, final_qty: 0, manual: false, reason_short: 'запас 150 + 120 в пути покрывает горизонт', urgency: 'none', cover_days: 95, status: 'enough', excess: true },
        { sku_id: 'SE:ЦБ-009041', supplier: { id: 'SE', name: 'Systeme Electric' }, code_1c: 'ЦБ-009041', supplier_article: 'A9F74216', name: 'Автоматический выключатель iC60N 2P 16А', category: '2', unit: 'шт', purchase_unit: 'шт', unit_text: 'шт', free_stock: null, inbound: [], recommended_qty: null, final_qty: null, manual: false, reason_short: 'нет снимка остатка', urgency: 'unknown', cover_days: null, status: 'needs_data', excess: false },
        { sku_id: 'SE:ЦБ-009025', supplier: { id: 'SE', name: 'Systeme Electric' }, code_1c: 'ЦБ-009025', supplier_article: 'A9F74225', name: 'Автоматический выключатель iC60N 2P 25А', category: '2', unit: 'шт', purchase_unit: 'шт', unit_text: 'шт', free_stock: 20, inbound: [], recommended_qty: 48, final_qty: 48, manual: false, reason_short: '65 − 20 = 45 → 48 (крат. 12)', urgency: 'this_cycle', cover_days: 32, status: 'order', excess: false },
      ] },
    { supplier: { id: 'IEK', name: 'ИЭК' }, total: 6, page: 1, pages: 1, count_text: '6 поз.',
      rows: [
        { sku_id: 'IEK:КМ47-29', supplier: { id: 'IEK', name: 'ИЭК' }, code_1c: '300200428_', supplier_article: 'MVA20-1-016-C', name: 'Автоматический выключатель КМ47-29 1Р 16А 4,5кА C', category: 'Автоматы', unit: 'шт', purchase_unit: 'шт', unit_text: 'шт', free_stock: 88, inbound: [], recommended_qty: 50, final_qty: 50, manual: false, reason_short: '135 − 88 = 47 → 50 (мин. 10)', urgency: 'this_cycle', cover_days: 45, status: 'order', excess: false },
        { sku_id: 'IEK:КМ47-63', supplier: { id: 'IEK', name: 'ИЭК' }, code_1c: '300200430_', supplier_article: 'MVA50-1-016-C', name: 'Автоматический выключатель КМ47-63 1Р 16А 6кА C', category: 'Автоматы', unit: 'шт', purchase_unit: 'шт', unit_text: 'шт', free_stock: 200, inbound: [{ qty: 100, eta: '2026-10-20' }], recommended_qty: 0, final_qty: 96, manual: true, reason_short: 'ручная корректировка: проектный заказ', urgency: 'none', cover_days: 120, status: 'order', excess: true },
        { sku_id: 'IEK:КМ-1260', supplier: { id: 'IEK', name: 'ИЭК' }, code_1c: '300205001_', supplier_article: 'KMU10010', name: 'Контактор КМ 1260 1NO+1NC 220В', category: 'Контакторы', unit: 'шт', purchase_unit: 'шт', unit_text: 'шт', free_stock: 5, inbound: [], recommended_qty: 20, final_qty: 20, manual: false, reason_short: '24 − 5 = 19 → 20 (мин. 5)', urgency: 'urgent', cover_days: 12, status: 'order', excess: false },
      ] },
  ],
  what_if: null, category_trends: null,
};
export const mockSkuExplanation: SkuExplanation = {
  header: mockHeader,
  nav: { prev_sku_id: null, next_sku_id: 'SE:ЦБ-004125' },
  sku: { sku_id: 'SE:ЦБ-004121', supplier: { id: 'SE', name: 'Systeme Electric' }, code_1c: 'ЦБ-004121', supplier_article: 'C9F34116', category: '1', name: 'Выключатель автоматический City9 Set 1P 16А C 4,5кА', unit: 'шт', purchase_unit: 'шт' },
  status: 'order', urgency: 'urgent', excess: false, issues: [],
  chart: {
    base_from: '2026-03', base_to: '2026-08',
    months: [
      { month: '2025-10', label: 'Окт', sales: 52, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: false, partial: false, missing: false },
      { month: '2025-11', label: 'Ноя', sales: 58, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: false, partial: false, missing: false },
      { month: '2025-12', label: 'Дек', sales: 71, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: false, partial: false, missing: false },
      { month: '2026-01', label: 'Янв', sales: 40, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: false, partial: false, missing: false },
      { month: '2026-02', label: 'Фев', sales: 35, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: false, partial: false, missing: false },
      { month: '2026-03', label: 'Мар', sales: 55, restored: 0, one_off_excluded: 480, one_off_included: 0, in_base: true, partial: false, missing: false },
      { month: '2026-04', label: 'Апр', sales: 62, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: true, partial: false, missing: false },
      { month: '2026-05', label: 'Май', sales: 0, restored: 63, one_off_excluded: 0, one_off_included: 0, in_base: true, partial: false, missing: false },
      { month: '2026-06', label: 'Июн', sales: 68, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: true, partial: false, missing: false },
      { month: '2026-07', label: 'Июл', sales: 72, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: true, partial: false, missing: false },
      { month: '2026-08', label: 'Авг', sales: 65, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: true, partial: false, missing: false },
      { month: '2026-09', label: 'Сен', sales: 41, restored: 0, one_off_excluded: 0, one_off_included: 0, in_base: false, partial: true, missing: false },
    ],
    forecast: [{ month: '2026-10', label: 'П·окт', qty: 72 }, { month: '2026-11', label: 'П·ноя', qty: 76 }],
  },
  demand: { raw_avg: 138, regular_avg: 64, daily: 2.1, season: 1.15, season_source_text: 'агрегат бренда', trend: 0.06, trend_source_text: 'оценка аналитика', trend_manual: false, trend_estimate: 0.04, trend_estimate_text: '+4%' },
  steps: [
    { key: 'regular_demand', label: 'Регулярный спрос', value_text: '64 шт/мес', note_text: 'мар–авг 2026 после исключения разовых сделок и поправки на stockout; 2,10 шт/дн', emphasis: false },
    { key: 'forecast', label: 'Прогноз на H = L 30 + R 14 = 44 дн.', value_text: '112', note_text: '2,10 × 44 × сезон 1,15 × прирост 1,06', emphasis: false },
    { key: 'safety', label: '+ Страховой запас', value_text: '+21', note_text: '10 дн (правило категории 1) × 2,10', emphasis: false },
    { key: 'free', label: '− Свободный остаток', value_text: '−35', note_text: 'снимок 22.09.2026; резерв 8 уже вычтен', emphasis: false },
    { key: 'inbound', label: '− Поступления в пределах H', value_text: '−25', note_text: '25 через 12 дн.; 40 через 58 дн. (за горизонтом)', emphasis: false },
    { key: 'need', label: '= Потребность', value_text: '73 шт', note_text: 'max(0, прогноз + страховой − свободно − путь)', emphasis: true },
    { key: 'order', label: 'Рекомендуемый заказ', value_text: '84 шт', note_text: 'минимум 12, кратность 12: 12 × ceil(max(потребность, 12) / 12)', emphasis: true, large: true },
  ],
  explanation_text: 'На период защиты 44 дн. прогноз 112 шт., страховой запас 21, свободно 35, вовремя ожидается 25. Потребность 73 шт. С учётом минимума 12 и кратности 12 рекомендуем 84 шт.',
  params: { lead_time_days: 30, review_days: 14, season: 1.15, overridden: false },
  stock: { free: 35, free_manual: false, reserve: 8, cover_days: 17, cover_text: '17 дн.', early_risk: false },
  inbound: [
    { id: 'i1', qty: 25, eta: '2026-10-05', days: 12, doc_text: 'Путь П-2291', counted: true, in_horizon: true, where_text: 'внутри H (через 12 дн.)' },
    { id: 'i2', qty: 40, eta: '2026-11-20', days: 58, doc_text: 'Путь П-2301', counted: false, in_horizon: false, where_text: 'за горизонтом (через 58 дн.)' },
  ],
  manual: { active: false, qty: null, reason: null, note_text: null },
  price: { value: null, manual: false, text: 'не подтверждена' },
  cost: { value: null, text: '—' },
  provenance: [
    { input: 'Свободный остаток', source_text: 'Товар в пути_SystemElectric на 22.09.2026 · TDSheet', origin: 'synthetic' },
    { input: 'Товар в пути', source_text: 'Товар в пути_SystemElectric на 22.09.2026 · TDSheet', origin: 'synthetic' },
    { input: 'Продажи', source_text: 'Ежемесячные продажи SE янв.2024–сент.2026', origin: 'synthetic' },
  ],
};
export const mockOrder: OrderCurrent = {
  header: mockHeader,
  version: 3, revision: 0, status: 'draft', status_text: 'v3 Черновик',
  approved_at: null, approved_by: null,
  hint_text: 'Проверьте список позиций и отправьте на согласование руководителю.',
  permissions: { can_edit: true, can_submit: true, can_approve: false, can_reject: false, can_export: false },
  blocked_reason_text: null,
  groups: [
    {
      supplier: { id: 'SE', name: 'Systeme Electric' },
      summary_text: '3 строки к заказу', cost_text: 'Сумма: цены не подтверждены',
      pending_text: '1 поз. без количества — не попадут в экспорт',
      lines: [
        { sku_id: 'SE:ЦБ-004121', code_1c: 'ЦБ-004121', name: 'Выключатель автоматический City9 Set 1P 16А C 4,5кА', purchase_unit: 'шт', recommended_qty: 84, final_qty: 84, manual: false, reason: null, price: null, cost: null },
        { sku_id: 'SE:ЦБ-004125', code_1c: 'ЦБ-004125', name: 'Выключатель автоматический City9 Set 1P 25А C 4,5кА', purchase_unit: 'шт', recommended_qty: 60, final_qty: 60, manual: false, reason: null, price: null, cost: null },
        { sku_id: 'SE:ЦБ-009025', code_1c: 'ЦБ-009025', name: 'Автоматический выключатель iC60N 2P 25А', purchase_unit: 'шт', recommended_qty: 48, final_qty: 48, manual: false, reason: null, price: null, cost: null },
      ],
    },
    {
      supplier: { id: 'IEK', name: 'ИЭК' },
      summary_text: '3 строки к заказу · изменено вручную: 1', cost_text: 'Сумма: цены не подтверждены',
      pending_text: null,
      lines: [
        { sku_id: 'IEK:КМ47-29', code_1c: '300200428_', name: 'Автоматический выключатель КМ47-29 1Р 16А 4,5кА C', purchase_unit: 'шт', recommended_qty: 50, final_qty: 50, manual: false, reason: null, price: null, cost: null },
        { sku_id: 'IEK:КМ47-63', code_1c: '300200430_', name: 'Автоматический выключатель КМ47-63 1Р 16А 6кА C', purchase_unit: 'шт', recommended_qty: 0, final_qty: 96, manual: true, reason: 'подтверждён проектный заказ', price: null, cost: null },
        { sku_id: 'IEK:КМ-1260', code_1c: '300205001_', name: 'Контактор КМ 1260 1NO+1NC 220В', purchase_unit: 'шт', recommended_qty: 20, final_qty: 20, manual: false, reason: null, price: null, cost: null },
      ],
    },
  ],
  export_settings: {
    format: 'csv', separator: ';', encoding: 'utf-8-bom',
    columns: [
      { key: 'supplier', label: 'Поставщик', enabled: true },
      { key: 'code_1c', label: 'Код 1С', enabled: true },
      { key: 'supplier_article', label: 'Артикул поставщика', enabled: true },
      { key: 'name', label: 'Наименование', enabled: true },
      { key: 'purchase_unit', label: 'Ед. закупки', enabled: true },
      { key: 'recommended_qty', label: 'Рекомендация', enabled: true },
      { key: 'final_qty', label: 'Итог', enabled: true },
      { key: 'manual', label: 'Ручная корректировка', enabled: false },
      { key: 'reason', label: 'Причина', enabled: true },
    ],
    format_options: ['csv', 'xlsx'],
    separator_options: [';', ',', 'tab'],
    encoding_options: ['utf-8-bom', 'cp1251'],
    note_text: 'Точный состав полей нужно сверить с образцом файла импорта 1С.',
  },
};

export const mockValidation: ValidationScenarios = {
  passed: 5, total: 5, summary_text: 'Пройдено 5 из 5',
  items: [
    { n: 1, name: 'Товар в пути уменьшает заказ', expected_text: 'с 300 шт в пути заказ меньше', actual_text: 'без пути 147 шт, с 300 шт в пути — 0 шт', passed: true },
    { n: 2, name: 'Учитывается сезонность', expected_text: 'прогноз на ноябрь > прогноза на май в 1,5 раза', actual_text: 'ноябрь 84 шт/мес, май 18 шт/мес', passed: true },
    { n: 3, name: 'Компенсируется упущенный спрос', expected_text: 'с учётом 2 мес. отсутствия заказ выше', actual_text: 'по сырым 147 шт, с stockout — 183 шт', passed: true },
    { n: 4, name: 'Разовые крупные заказы исключаются', expected_text: 'выброс 1500 шт не даёт роста >25%', actual_text: 'без выброса 147 шт, с выбросом 1500 шт — 156 шт (рост 6%)', passed: true },
    { n: 5, name: 'Каждая позиция имеет обоснование', expected_text: 'объяснение непустое, ≥3 компонентов', actual_text: '7 компонентов: Средние продажи: 64,0 шт/мес; Сезонность: +15%; Тренд: +6%', passed: true },
  ],
};
