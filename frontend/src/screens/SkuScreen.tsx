import { useEffect, useState } from 'react'
import type { SkuExplanation, SkuId } from '../types'
import { getSkuExplanation, skuAction } from '../api/client'

interface Props { skuId: SkuId | null; onBack: () => void; onSkuChange: (id: SkuId) => void }

export default function SkuScreen({ skuId, onBack, onSkuChange }: Props) {
  const [data, setData] = useState<SkuExplanation | null>(null)
  const [qty, setQty] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!skuId) return
    getSkuExplanation(skuId).then(setData).catch(cause => setError(String(cause)))
  }, [skuId])

  async function applyManual(action: 'set_manual_qty' | 'clear_manual_qty') {
    if (!skuId || !data) return
    setSaving(true)
    setError('')
    try {
      const payload = action === 'set_manual_qty' ? { action, qty: Number(qty), reason: reason.trim(), order_version: data.header.order.version } : { action, order_version: data.header.order.version }
      await skuAction(skuId, payload)
      setData(await getSkuExplanation(skuId))
      setQty('')
      setReason('')
    } catch (cause) { setError(`Не удалось сохранить правку: ${String(cause)}`) }
    finally { setSaving(false) }
  }

  if (!skuId || !data) return (
    <div className="page">
      <p style={{ color: 'var(--color-neutral-600)' }}>Выберите позицию из таблицы рекомендаций.</p>
      <button className='btn' style={{ marginTop: 12 }} onClick={onBack}>← Назад</button>
    </div>
  )

  const maxSales = Math.max(...data.chart.months.map(m => Math.max(m.sales, m.restored)), ...data.chart.forecast.map(f => f.qty), 1)

  return (
    <div className="page">
      <div className="page-head">
        <div><button className='btn btn-ghost' onClick={onBack}>← К рекомендациям</button><h1 style={{ marginTop: 10 }}>{data.sku.name}</h1><p className="page-subtitle">История и прогноз, поправки спроса, остатки, поступления и пошаговая арифметика заказа.</p></div>
        <div className="inline-actions"><button className="btn btn-secondary" disabled={!data.nav.prev_sku_id} onClick={() => data.nav.prev_sku_id && onSkuChange(data.nav.prev_sku_id)}>← Предыдущая</button><button className="btn btn-secondary" disabled={!data.nav.next_sku_id} onClick={() => data.nav.next_sku_id && onSkuChange(data.nav.next_sku_id)}>Следующая →</button></div>
      </div>
      {error && <div className="notice" role="alert" style={{ marginBottom: 16 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <span className='tag tag-outline'>{data.sku.code_1c}</span>
        <span className='tag tag-outline'>{data.sku.supplier_article}</span>
        <span className='tag tag-outline'>{data.sku.supplier.name}</span>
        <span className='tag tag-outline'>Кат. {data.sku.category}</span>
        {data.status === 'order' && <span className='tag tag-accent'>Заказать</span>}
        {data.urgency === 'urgent' && <span className="tag tag-outline">Срочно</span>}
        {data.excess && <span className="tag tag-neutral">Избыточный запас</span>}
      </div>

      {data.issues.length > 0 && <div className="notice" style={{ marginBottom: 20 }}>{data.issues.map(issue => <div key={issue.key}>{issue.text}</div>)}</div>}

      <div className="data-two-column">        <div>
          <h2 style={{ marginBottom: 12 }}>История и прогноз</h2>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 120, marginBottom: 8 }}>
            {data.chart.months.map(m => {
              const val = m.restored > 0 ? m.restored : m.sales
              const h = Math.round((val / maxSales) * 100)
              return (
                <div key={m.month} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 28 }}>
                  <div title={String(val)} style={{
                    width: '100%', height: h + '%', minHeight: 2,
                    background: m.in_base ? 'var(--color-accent)' : m.partial ? 'var(--color-accent-400)' : 'var(--color-neutral-300)',
                    borderRadius: '2px 2px 0 0',
                    border: m.restored > 0 ? '2px dashed var(--color-accent-600)' : 'none',
                  }} />
                  <span style={{ fontSize: 9, color: 'var(--color-neutral-600)', marginTop: 2 }}>{m.label}</span>
                </div>
              )
            })}
            {data.chart.forecast.map(f => (
              <div key={f.month} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 28, background: 'var(--color-accent-100)', borderRadius: 2 }}>
                <div style={{ width: '100%', height: Math.round((f.qty / maxSales) * 100) + '%', minHeight: 2, background: 'var(--color-accent-400)', borderRadius: '2px 2px 0 0' }} />
                <span style={{ fontSize: 9, color: 'var(--color-accent-700)', marginTop: 2 }}>{f.label}</span>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--color-neutral-600)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-accent)', display: 'inline-block', borderRadius: 1 }} />В базе</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-neutral-300)', display: 'inline-block', borderRadius: 1 }} />Не в базе</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-accent-100)', border: '1px solid var(--color-accent-400)', display: 'inline-block', borderRadius: 1 }} />Прогноз</span>
          </div>

          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: 13, marginBottom: 8, fontFamily: 'var(--font-body)', fontWeight: 600 }}>Параметры спроса</h3>
            <table className='table' style={{ fontSize: 12 }}>
              <tbody>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Ср. регулярный спрос</td><td>{new Intl.NumberFormat('ru-RU').format(data.demand.regular_avg)} шт/мес</td></tr>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Сезонность</td><td>{data.demand.season} · {data.demand.season_source_text}</td></tr>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Тренд</td><td>{data.demand.trend_estimate_text} · {data.demand.trend_source_text}</td></tr>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Срок поставки L</td><td>{data.params.lead_time_days} дн.</td></tr>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Цикл пересмотра R</td><td>{data.params.review_days} дн.</td></tr>
              </tbody>
            </table>
          </div>

          <div className="page-section">
            <h3 className="card-title" style={{ fontSize: 18, marginBottom: 8 }}>Поправки спроса</h3>
            <p className="tiny">Разовые продажи и периоды отсутствия товара показываются по расчёту. Подтверждение периодов выполняется в источнике данных.</p>
            {data.events?.map(event => <div className="blueprint panel" style={{ marginTop: 8 }} key={event.id}><strong>{event.title_text}</strong><p className="tiny" style={{ marginTop: 4 }}>{event.note_text}</p></div>)}
            {data.stockouts?.map(item => <div className="blueprint panel" style={{ marginTop: 8 }} key={item.id}><strong>{item.title_text}</strong><p className="tiny" style={{ marginTop: 4 }}>{item.note_text}</p></div>)}
            {!data.events?.length && !data.stockouts?.length && <p className="muted" style={{ marginTop: 8 }}>Поправки для этой позиции не применялись.</p>}
          </div>

          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: 13, marginBottom: 8, fontFamily: 'var(--font-body)', fontWeight: 600 }}>Остатки и поступления</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <div className="blueprint" style={{ padding: '8px 12px', flex: 1 }}>
                <div style={{ fontSize: 20, fontFamily: 'var(--font-heading)', fontWeight: 600 }}>{data.stock.free ?? '—'}</div>
                <div style={{ fontSize: 11, color: 'var(--color-neutral-600)' }}>свободно · {data.stock.cover_text}</div>
              </div>
              <div className="blueprint" style={{ padding: '8px 12px', flex: 1 }}>
                <div style={{ fontSize: 20, fontFamily: 'var(--font-heading)', fontWeight: 600 }}>{data.stock.reserve}</div>
                <div style={{ fontSize: 11, color: 'var(--color-neutral-600)' }}>в резерве</div>
              </div>
            </div>
            {data.inbound.length > 0 && (
              <table className='table' style={{ fontSize: 12 }}>
                <thead><tr><th>Документ</th><th>Кол-во</th><th>ETA</th><th>Учтён</th></tr></thead>
                <tbody>
                  {data.inbound.map(ib => (
                    <tr key={ib.id}>
                      <td>{ib.doc_text}</td>
                      <td>{new Intl.NumberFormat('ru-RU').format(ib.qty)}</td>
                      <td>{ib.eta} <span style={{ color: 'var(--color-neutral-500)' }}>({ib.where_text})</span></td>
                      <td>{ib.counted ? <span className='tag tag-accent'>Да</span> : <span className='tag tag-neutral'>Нет</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>        <div>
          <h2 style={{ marginBottom: 12 }}>Расчёт рекомендации</h2>
          <div className='notice' style={{ marginBottom: 16 }}>{data.explanation_text}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.steps.map(step => (
              <div key={step.key} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                padding: step.large ? '12px 16px' : '6px 12px',
                background: step.large ? 'var(--color-accent-100)' : step.emphasis ? 'var(--color-neutral-100)' : 'transparent',
                border: step.large ? '1px solid var(--color-accent-300)' : step.emphasis ? '1px solid var(--color-divider)' : 'none',
                borderRadius: 2,
              }}>
                <div>
                  <span style={{ fontWeight: step.emphasis ? 600 : 400, fontSize: step.large ? 15 : 14 }}>{step.label}</span>
                  {step.note_text && <div style={{ fontSize: 11, color: 'var(--color-neutral-600)', marginTop: 2 }}>{step.note_text}</div>}
                </div>
                <span style={{ fontFamily: 'var(--font-heading)', fontSize: step.large ? 22 : 16, fontWeight: 600, color: step.large ? 'var(--color-accent-900)' : 'var(--color-text)' }}>{step.value_text}</span>
              </div>
            ))}
          </div>

          <div className="blueprint panel" style={{ marginTop: 24 }}>
            <h3 className="card-title" style={{ marginBottom: 12 }}>Ручная корректировка</h3>
            {data.manual.active
              ? <div><div className='notice'>Активна ручная корректировка: {data.manual.qty} {data.sku.purchase_unit}. {data.manual.reason} {data.manual.note_text}</div><button type="button" className="btn btn-secondary" style={{ marginTop: 10 }} onClick={() => void applyManual('clear_manual_qty')} disabled={saving}>Вернуть рекомендацию</button></div>
              : <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <div className='field' style={{ flex: 1 }}>
                    <label htmlFor="manual-qty">Количество ({data.sku.purchase_unit})</label>
                    <input id="manual-qty" className='input' type='number' min="0" step="1" placeholder='Введите вручную' value={qty} onChange={event => setQty(event.target.value)} />
                  </div>
                  <div className='field' style={{ flex: 2 }}>
                    <label htmlFor="manual-reason">Причина</label>
                    <input id="manual-reason" className='input' type='text' placeholder='Укажите причину изменения' value={reason} onChange={event => setReason(event.target.value)} />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                    <button className='btn btn-primary' disabled={saving || qty === '' || Number(qty) < 0 || !reason.trim()} onClick={() => void applyManual('set_manual_qty')}>Сохранить</button>
                  </div>
                </div>
            }
          </div>

          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: 13, marginBottom: 8, fontFamily: 'var(--font-body)', fontWeight: 600 }}>Источники данных</h3>
            <table className='table' style={{ fontSize: 11 }}>
              <thead><tr><th>Показатель</th><th>Источник</th><th>Тип</th></tr></thead>
              <tbody>
                {data.provenance.map((prov, i) => (
                  <tr key={i}>
                    <td>{prov.input}</td>
                    <td style={{ color: 'var(--color-neutral-600)' }}>{prov.source_text}</td>
                    <td><span className={prov.origin === 'synthetic' ? 'tag tag-neutral' : 'tag tag-accent'}>{prov.origin}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
