import type { SkuStatus } from '../../types'

export type Tone = 'accent' | 'success' | 'warning' | 'danger' | 'neutral' | 'outline' | 'solid'

// Статус позиции — главный визуальный сигнал в таблице. Один источник правды
// для подписи, цвета и иконки, чтобы на всех экранах статус выглядел одинаково.
export const STATUS: Record<SkuStatus, { label: string; tone: Tone; icon: string }> = {
  order: { label: 'Заказать', tone: 'accent', icon: 'package' },
  enough: { label: 'Достаточно', tone: 'success', icon: 'check' },
  needs_data: { label: 'Нужны данные', tone: 'warning', icon: 'alert' },
  insufficient_history: { label: 'Мало истории', tone: 'neutral', icon: 'history' },
}
export const statusLabel = (status: SkuStatus) => STATUS[status].label
