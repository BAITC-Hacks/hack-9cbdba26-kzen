// Форматирование чисел и дат вынесено из файла с компонентами: иначе
// Vite Fast Refresh не может горячо обновлять компоненты из того же модуля.
export const formatInt = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('ru-RU').format(value)
export const formatQty = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(value)
export function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  const [year, month, day] = value.slice(0, 10).split('-')
  return year && month && day ? `${day}.${month}.${year}` : value
}
