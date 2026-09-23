import type { RecommendationsPage, SkuExplanation, OrderCurrent, AppHeader, ValidationScenarios, DataOverview } from '../types'

const BASE = '/api/v1'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

export async function getSession(): Promise<AppHeader> {
  return get('/session')
}

export async function getDataOverview(): Promise<DataOverview> {
  return get('/data/overview')
}

export async function saveSettings(payload: Record<string, unknown>): Promise<{ header: AppHeader; settings: DataOverview['settings'] }> {
  return patch('/settings', payload)
}

export async function resetSession(): Promise<{ header: AppHeader }> {
  return post('/session/reset')
}

export async function searchRecommendations(query: {
  q?: string; supplier_id?: string | null; category?: string | null;
  status?: string | null; sort?: string; what_if?: { delay_days: number; demand_pct: number };
}): Promise<RecommendationsPage> {
  return post('/recommendations/search', query)
}

export async function getSkuExplanation(skuId: string): Promise<SkuExplanation> {
  return get(`/skus/${encodeURIComponent(skuId)}/explanation`)
}

export async function getOrderCurrent(): Promise<OrderCurrent> {
  return get('/orders/current')
}

export async function getValidation(): Promise<ValidationScenarios> {
  return get('/validation/scenarios')
}

export async function runCalculation(): Promise<unknown> {
  return post('/calculations')
}

export async function skuAction(skuId: string, payload: Record<string, unknown>): Promise<unknown> {
  return post(`/skus/${encodeURIComponent(skuId)}/actions`, payload)
}

export async function orderAction(payload: Record<string, unknown>): Promise<unknown> {
  return post('/orders/current/actions', payload)
}

export async function setRole(role: 'manager' | 'head'): Promise<{ header: AppHeader }> {
  const res = await fetch(`${BASE}/session/role`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }) })
  if (!res.ok) throw new Error(`${res.status} /session/role`)
  return res.json()
}

export async function saveExportSettings(payload: Record<string, unknown>): Promise<{ order: OrderCurrent }> {
  return patch('/orders/current/export-settings', payload)
}

export async function exportOrder(supplierId?: string): Promise<void> {
  const res = await fetch(`${BASE}/orders/export`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(supplierId ? { supplier_id: supplierId } : {}) })
  if (!res.ok) throw new Error(`${res.status} /orders/export`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  const disposition = res.headers.get('Content-Disposition') || ''
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/)?.[1]
  anchor.download = encodedName ? decodeURIComponent(encodedName) : 'заказ.xlsx'
  anchor.click()
  URL.revokeObjectURL(url)
}

export async function getOrderVersions(): Promise<Array<{ version: number; approved_at: string; approved_by_text: string; lines: number }>> {
  return get('/orders/versions')
}

export async function getAuditLog(): Promise<{ items: Array<{ version: number; text: string; user_text: string; at: string }> }> {
  return get('/audit-log')
}

export async function getVersionDiff(version: number): Promise<{ title_text: string; rows: Array<{ code_1c: string; name: string; in_version_text: string; current_text: string }> }> {
  return get(`/orders/versions/${version}/diff`)
}
