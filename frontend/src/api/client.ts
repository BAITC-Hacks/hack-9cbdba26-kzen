// TODO: replace mock returns with actual fetch() calls to /api/v1/...
import { mockHeader, mockRecommendations, mockSkuExplanation, mockOrder, mockValidation } from '../mock/data'
import type { RecommendationsPage, SkuExplanation, OrderCurrent, AppHeader, ValidationScenarios } from '../types'

export async function getSession(): Promise<AppHeader> {
  return mockHeader
}

export async function searchRecommendations(_query: {
  q?: string; supplier_id?: string | null; category?: string | null;
  status?: string | null; sort?: string;
}): Promise<RecommendationsPage> {
  return mockRecommendations
}

export async function getSkuExplanation(_skuId: string): Promise<SkuExplanation> {
  return mockSkuExplanation
}

export async function getOrderCurrent(): Promise<OrderCurrent> {
  return mockOrder
}

export async function getValidation(): Promise<ValidationScenarios> {
  return mockValidation
}