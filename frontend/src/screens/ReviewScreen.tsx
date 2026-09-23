import { useEffect, useState } from 'react'
import type { OrderCurrent, OrderStatus, Role } from '../types'
import { getOrderCurrent } from '../api/client'

interface Props { initialRole?: Role }

function orderStatusLabel(s: OrderStatus) {
  if (s === 'draft') return 'Черновик'
  if (s === 'submitted') return 'На согласовании'
  return 'Утверждён'
}

export default function ReviewScreen({ initialRole = 'manager' }: Props) {
  const [data, setData] = useState<OrderCurrent | null>(null)
  const [role, setRole] = useState<Role>(initialRole)
  const [status, setStatus] = useState<OrderStatus>('draft')

  useEffect(() => { getOrderCurrent().then(d => { setData(d); setStatus(d.status) }) }, [])

  if (!data) return <div style={{ padding: 24 }}>Загрузка...</div>

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h1 style={{ marginBottom: 4 }}>Заказ {data.status_text}</h1>
          <p style={{ color: 'var(--color-neutral-600)', fontSize: 13 }}>{data.hint_text}</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
          <div>
            <span style={{ fontSize: 12, color: 'var(--color-neutral-600)', marginRight: 8 }}>Роль:</span>
            <div className='seg' style={{ display: 'inline-flex' }}>
              <div className='seg-opt'>
                <input type='radio' id='role-mgr' name='role' checked={role==='manager'} onChange={() => setRole('manager')} />
                <label htmlFor='role-mgr'>Менеджер</label>
              </div>
              <div className='seg-opt'>
                <input type='radio' id='role-head' name='role' checked={role==='head'} onChange={() => setRole('head')} />
                <label htmlFor='role-head'>Руководитель</label>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {role === 'manager' && status === 'draft' && (
              <button className='btn btn-primary' onClick={() => setStatus('submitted')}>Отправить на согласование</button>
            )}
            {role === 'head' && status === 'submitted' && (
              <>
                <button className='btn btn-primary' onClick={() => setStatus('approved')}>Утвердить</button>
                <button className='btn btn-secondary' onClick={() => setStatus('draft')}>Вернуть на доработку</button>
              </>
            )}
            {status === 'approved' && (
              <button className='btn btn-primary'>Экспорт в CSV</button>
            )}
          </div>
          <span className={'tag ' + (status === 'approved' ? 'tag-accent' : status === 'submitted' ? 'tag-outline' : 'tag-neutral')}>
            {orderStatusLabel(status)}
          </span>
        </div>
      </div>      {data.groups.map(group => (
        <div key={group.supplier.id} style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div>
              <h2 style={{ fontSize: 18 }}>{group.supplier.name}</h2>
              <span style={{ fontSize: 13, color: 'var(--color-neutral-600)' }}>{group.summary_text} · {group.cost_text}</span>
              {group.pending_text && <div className='tag tag-outline' style={{ marginTop: 4 }}>{group.pending_text}</div>}
            </div>
          </div>
          <div style={{ background: 'white', borderRadius: 2, overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
            <table className='table'>
              <thead><tr>
                <th>Код 1С</th><th style={{ minWidth: 200 }}>Наименование</th><th>Ед.</th>
                <th>Рекоменд.</th><th>Итого</th><th>Цена</th><th>Сумма</th><th>Причина</th>
              </tr></thead>
              <tbody>
                {group.lines.map(line => (
                  <tr key={line.sku_id}>
                    <td><code style={{ fontSize: 12 }}>{line.code_1c}</code></td>
                    <td style={{ fontSize: 13 }}>{line.name}</td>
                    <td>{line.purchase_unit}</td>
                    <td style={{ textAlign: 'right', color: 'var(--color-neutral-600)' }}>
                      {line.recommended_qty != null ? new Intl.NumberFormat('ru-RU').format(line.recommended_qty) : '—'}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>
                      {line.final_qty != null ? new Intl.NumberFormat('ru-RU').format(line.final_qty) : '—'}
                      {line.manual && <span className='tag tag-outline' style={{ marginLeft: 6, fontSize: 10 }}>ручн.</span>}
                    </td>
                    <td style={{ textAlign: 'right', color: 'var(--color-neutral-500)' }}>{line.price != null ? line.price : '—'}</td>
                    <td style={{ textAlign: 'right', color: 'var(--color-neutral-500)' }}>{line.cost != null ? new Intl.NumberFormat('ru-RU').format(line.cost) : '—'}</td>
                    <td style={{ fontSize: 12, color: 'var(--color-neutral-600)' }}>{line.reason ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 24, padding: 16, border: '1px solid var(--color-divider)', borderRadius: 2 }}>
        <h2 style={{ fontSize: 16, marginBottom: 12 }}>Настройки экспорта</h2>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
          <div className='field'>
            <label>Формат</label>
            <select className='input' style={{ width: 120 }} defaultValue={data.export_settings.format}>
              {data.export_settings.format_options.map(o => <option key={o}>{o}</option>)}
            </select>
          </div>
          <div className='field'>
            <label>Разделитель</label>
            <select className='input' style={{ width: 100 }} defaultValue={data.export_settings.separator}>
              {data.export_settings.separator_options.map(o => <option key={o}>{o}</option>)}
            </select>
          </div>
          <div className='field'>
            <label>Кодировка</label>
            <select className='input' style={{ width: 140 }} defaultValue={data.export_settings.encoding}>
              {data.export_settings.encoding_options.map(o => <option key={o}>{o}</option>)}
            </select>
          </div>
        </div>
        <p style={{ fontSize: 12, color: 'var(--color-neutral-600)' }}>{data.export_settings.note_text}</p>
        <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {data.export_settings.columns.map(col => (
            <label key={col.key} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, cursor: 'pointer' }}>
              <input type='checkbox' defaultChecked={col.enabled} />
              {col.label}
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}