export type ISODate = string;
export type DateTime = string;
export type Month = string;
export type SkuId = string;
export type SupplierId = 'SE' | 'IEK';

export type SkuStatus = 'order' | 'enough' | 'needs_data' | 'insufficient_history';
export type Urgency = 'urgent' | 'this_cycle' | 'none' | 'unknown';
export type OrderStatus = 'draft' | 'submitted' | 'approved';
export type Role = 'manager' | 'head';
export type Origin = 'real' | 'synthetic' | 'assumption' | 'manual' | 'imported' | 'none';
export type SourceUsageStatus = 'used' | 'partial' | 'not_used';

export interface Qty { value: number | null; unit: string; }
export interface Supplier { id: SupplierId; name: string; }
export interface Warehouse { id: string; name: string; }

export interface AppHeader {
  warehouse: Warehouse;
  category_filter: string | null;
  calc_date: string;
  data_cut_date: string;
  calc_at: DateTime | null;
  calc_stale: boolean;
  snapshot_age_days: number | null;
  snapshot_stale: boolean;
  what_if_active: boolean;
  data_mode: 'demo' | 'mixed' | 'imported';
  data_mode_text: string;
  order: { version: number; revision: number; status: OrderStatus; approved_at: DateTime | null } | null;
  role: Role;
  user: { id: string; name: string };
}

export interface DataOverview {
  header: AppHeader;
  sources: Array<{ key: string; supplier: Supplier; type_text: string; usage_text: string; freshness_text: string | null; volume_text: string | null; file: { name: string; status_text: string } | null }>;
  matching: Array<{ label?: string; value_text?: string }>;
  readiness: Array<{ supplier: Supplier; calculated: number; needs_data: number; insufficient_history: number }>;
  assumptions: Array<{ label: string; value_text: string; origin: Origin }>;
  issues: Array<{ text?: string; label?: string }>;
  document_rules: Array<{ doc_type: string; rule_text: string; editable: boolean }>;
  settings: {
    warehouse_options: Warehouse[];
    category_filter: string | null;
    category_options: Array<{ value: string | null; label: string }>;
    calc_date: string; calc_date_min: string; calc_date_max: string;
    suppliers: Array<{ id: SupplierId; name: string; lead_time_days: number; review_days: number; horizon_days: number }>;
    excess_months: number;
  };
}

export interface RecommendationRow {
  sku_id: SkuId;
  supplier: Supplier;
  code_1c: string;
  supplier_article: string;
  name: string;
  category: string | null;
  unit: string;
  purchase_unit: string;
  unit_text: string;
  free_stock: number | null;
  inbound: Array<{ qty: number; eta: string | null }>;
  recommended_qty: number | null;
  final_qty: number | null;
  manual: boolean;
  reason_short: string;
  urgency: Urgency;
  cover_days: number | null;
  status: SkuStatus;
  excess: boolean;
}

export interface RecommendationsPage {
  header: AppHeader;
  summary: { order: number; enough: number; needs_data: number; insufficient_history: number; excess: number };
  groups: Array<{
    supplier: Supplier;
    total: number; page: number; pages: number;
    count_text: string;
    rows: RecommendationRow[];
  }>;
  what_if: { delay_days: number; demand_pct: number } | null;
  category_trends: null;
}

export interface CalcStep {
  key: string;
  label: string;
  value_text: string;
  note_text: string;
  emphasis: boolean;
  large?: boolean;
}

export interface AgentTraceEvent {
  seq: number;
  type: string;
  status: 'ok' | 'warning' | 'blocked' | 'waiting';
  title: string;
  tool: string;
  sku: string;
  facts: Record<string, unknown>;
}

export interface SkuExplanation {
  header: AppHeader;
  nav: { prev_sku_id: SkuId | null; next_sku_id: SkuId | null };
  sku: {
    sku_id: SkuId;
    supplier: Supplier;
    code_1c: string;
    supplier_article: string;
    category: string | null;
    name: string;
    unit: string;
    purchase_unit: string;
  };
  status: SkuStatus;
  urgency: Urgency;
  excess: boolean;
  issues: Array<{ key: string; text: string }>;
  events?: Array<{ id: string; title_text: string; note_text: string }>;
  stockouts?: Array<{ id: string; title_text: string; note_text: string }>;
  chart: {
    base_from: Month; base_to: Month;
    months: Array<{ month: Month; label: string; sales: number; restored: number; one_off_excluded: number; one_off_included: number; in_base: boolean; partial: boolean; missing: boolean }>;
    forecast: Array<{ month: Month; label: string; qty: number }>;
  };
  demand: {
    raw_avg: number; regular_avg: number; daily: number;
    season: number; season_source_text: string;
    trend: number; trend_source_text: string; trend_manual: boolean;
    trend_estimate: number; trend_estimate_text: string;
  };
  steps: CalcStep[];
  agent_trace?: AgentTraceEvent[];
  explanation_text: string;
  params: { lead_time_days: number; review_days: number; season: number | null; overridden: boolean };
  stock: { free: number | null; free_manual: boolean; reserve: number | null; cover_days: number | null; cover_text: string; early_risk: boolean };
  inbound: Array<{ id: string; qty: number; eta: string | null; days: number | null; doc_text: string; counted: boolean; in_horizon: boolean; where_text: string }>;
  manual: { active: boolean; qty: number | null; reason: string | null; note_text: string | null };
  price: { value: number | null; manual: boolean; text: string };
  cost: { value: number | null; text: string };
  provenance: Array<{ input: string; source_text: string; origin: Origin }>;
}

export interface OrderCurrent {
  header: AppHeader;
  version: number;
  revision: number;
  status: OrderStatus;
  status_text: string;
  approved_at: DateTime | null;
  approved_by: string | null;
  hint_text: string;
  permissions: { can_edit: boolean; can_submit: boolean; can_approve: boolean; can_reject: boolean; can_export: boolean };
  blocked_reason_text: string | null;
  groups: Array<{
    supplier: Supplier;
    summary_text: string;
    cost_text: string;
    pending_text: string | null;
    lines: Array<{
      sku_id: SkuId; code_1c: string; name: string;
      purchase_unit: string; recommended_qty: number | null;
      final_qty: number | null; manual: boolean;
      reason: string | null; price: number | null; cost: number | null;
    }>;
  }>;
  export_settings: {
    format: 'csv' | 'xlsx'; separator: string; encoding: string;
    columns: Array<{ key: string; label: string; enabled: boolean }>;
    format_options: string[]; separator_options: string[]; encoding_options: string[];
    note_text: string;
  };
}

export interface ValidationScenarios {
  passed: number; total: number; summary_text: string;
  items: Array<{ n: number; name: string; expected_text: string | null; actual_text: string; passed: boolean }>;
}
