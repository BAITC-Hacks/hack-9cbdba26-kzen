import type { RecommendationsPage, SkuExplanation, OrderCurrent, AppHeader, ValidationScenarios } from '../types'

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

export async function getSession(): Promise<AppHeader> {
  return get('/session')
}

export async function searchRecommendations(query: {
  q?: string; supplier_id?: string | null; category?: string | null;
  status?: string | null; sort?: string;
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
