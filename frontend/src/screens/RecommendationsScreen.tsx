import { useState } from 'react'
import type { RecommendationsPage, SkuId, SkuStatus, Urgency } from '../types'

interface Props {
  data: RecommendationsPage
  onSkuClick: (id: SkuId) => void
}

function statusTag(status: SkuStatus) {
  if (status === 'order') return <span className='tag tag-accent'>Заказать</span>
  if (status === 'enough') return <span className='tag tag-neutral'>Запаса достаточно</span>
  if (status === 'needs_data') return <span className='tag tag-outline'>Нужны данные</span>
  return <span className='tag tag-neutral'>Недостаточно истории</span>
}

function urgencyLabel(u: Urgency) {
  if (u === 'urgent') return <span style={{ color: '#c0392b', fontWeight: 600 }}>Срочно</span>
  if (u === 'this_cycle') return <span style={{ color: 'var(--color-accent-700)' }}>В этом цикле</span>
  return <span style={{ color: 'var(--color-neutral-500)' }}>—</span>
}

export default function RecommendationsScreen({ data, onSkuClick }: Props) {
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterSupplier, setFilterSupplier] = useState<string>('all')
  const [search, setSearch] = useState('')
  const { summary } = data
  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ marginBottom: 4 }}>Рекомендации по закупке</h1>
      </div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'К заказу', val: summary.order, accent: true },
          { label: 'Достаточно', val: summary.enough, accent: false },
          { label: 'Нужны данные', val: summary.needs_data, accent: false },
          { label: 'Мало истории', val: summary.insufficient_history, accent: false },
          { label: 'Избыток', val: summary.excess, accent: false },
        ].map(s => (
          <div key={s.label} style={{ background: s.accent ? 'var(--color-accent-100)' : 'white', border: '1px solid var(--color-divider)', borderRadius: 2, padding: '10px 16px', minWidth: 100 }}>
            <div style={{ fontSize: 24, fontFamily: 'var(--font-heading)', fontWeight: 600, color: s.accent ? 'var(--color-accent-900)' : 'var(--color-text)' }}>{s.val}</div>
            <div style={{ fontSize: 12, color: 'var(--color-neutral-600)', marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <input className='input' style={{ width: 240 }} placeholder='Поиск...' value={search} onChange={e => setSearch(e.target.value)} />
        <select className='input' style={{ width: 160 }} value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value='all'>Все статусы</option>
          <option value='order'>К заказу</option>
          <option value='enough'>Достаточно</option>
          <option value='needs_data'>Нужны данные</option>
        </select>
        <select className='input' style={{ width: 180 }} value={filterSupplier} onChange={e => setFilterSupplier(e.target.value)}>
          <option value='all'>Все поставщики</option>
          <option value='SE'>Systeme Electric</option>
          <option value='IEK'>ИЭК</option>
        </select>
      </div>      {data.groups
        .filter(g => filterSupplier === 'all' || g.supplier.id === filterSupplier)
        .map(group => {
          const rows = group.rows.filter(r => {
            if (filterStatus !== 'all' && r.status !== filterStatus) return false
            if (search && !r.name.toLowerCase().includes(search.toLowerCase()) && !r.code_1c.toLowerCase().includes(search.toLowerCase())) return false
            return true
          })
          if (rows.length === 0) return null
          return (
            <div key={group.supplier.id} style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <h2 style={{ fontSize: 18 }}>{group.supplier.name}</h2>
                <span className='tag tag-neutral'>{group.count_text}</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className='table' style={{ minWidth: 1180 }}>
                  <thead><tr>
                    <th>Поставщик</th><th>Код 1С</th><th>Артикул</th>
                    <th style={{ minWidth: 220 }}>Наименование</th><th>Ед.</th>
                    <th>Свободно</th><th>Путь</th><th>Заказ</th>
                    <th style={{ minWidth: 200 }}>Обоснование</th>
                    <th>Срочность</th><th>Статус</th>
                  </tr></thead>
                  <tbody>
                    {rows.map(row => (
                      <tr key={row.sku_id} className='clickable' onClick={() => onSkuClick(row.sku_id)}>
                        <td style={{ fontSize: 12 }}>{row.supplier.name}</td>
                        <td><code style={{ fontSize: 12 }}>{row.code_1c}</code></td>
                        <td style={{ fontSize: 12, color: 'var(--color-neutral-600)' }}>{row.supplier_article}</td>
                        <td style={{ fontSize: 13 }}>{row.name}</td>
                        <td>{row.unit}</td>
                        <td style={{ textAlign: 'right' }}>{row.free_stock != null ? new Intl.NumberFormat('ru-RU').format(row.free_stock) : '—'}</td>
                        <td style={{ textAlign: 'right', fontSize: 12 }}>{row.inbound.length > 0 ? row.inbound.map(ib => new Intl.NumberFormat('ru-RU').format(ib.qty)).join(' + ') : '—'}</td>
                        <td style={{ textAlign: 'right', fontWeight: row.final_qty ? 600 : 400 }}>
                          {row.final_qty != null ? new Intl.NumberFormat('ru-RU').format(row.final_qty) : '—'}
                          {row.manual && <span className='tag tag-outline' style={{ marginLeft: 4, fontSize: 10 }}>ручн.</span>}
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--color-neutral-600)', maxWidth: 200 }}>{row.reason_short}</td>
                        <td>{urgencyLabel(row.urgency)}</td>
                        <td>{statusTag(row.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        })}
    </div>
  )
}