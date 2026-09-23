import type { AppHeader } from '../../types'

interface Props { header: AppHeader }

export default function ContextBar({ header }: Props) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '6px 20px', borderBottom: '1px solid var(--color-divider)', fontSize: 12, color: 'var(--color-neutral-700)', flexWrap: 'wrap' }}>
      <span><strong>Склад:</strong> {header.warehouse.name}</span>
      <span><strong>Расчёт:</strong> {header.calc_date}</span>
      <span><strong>Данные до:</strong> {header.data_cut_date}</span>
      <span><strong>Заказ:</strong> v{header.order.version} · {header.order.status === 'draft' ? 'Черновик' : header.order.status === 'submitted' ? 'На согласовании' : 'Утверждён'}</span>
      <span className='tag tag-neutral'>{header.data_mode_text}</span>
      {header.calc_stale && <span className='tag tag-outline' style={{ color: '#c0392b' }}>Расчёт устарел</span>}
    </div>
  )
}