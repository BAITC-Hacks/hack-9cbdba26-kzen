import { useCallback, useEffect, useRef, useState } from 'react'
import type { AgentTraceEvent, AppHeader, SkuExplanation, SkuId } from '../types'
import { getSkuExplanation, getSkuNarrative, skuAction } from '../api/client'

interface Props { skuId: SkuId | null; onBack: () => void; onSkuChange: (id: SkuId) => void; onOrderChanged?: (header: AppHeader) => void }

const traceTone: Record<AgentTraceEvent['status'], { background: string; color: string }> = {
  ok: { background: '#e8f5ed', color: '#17663a' },
  warning: { background: '#fff3d6', color: '#825900' },
  blocked: { background: '#ffebeb', color: '#a02e2e' },
  waiting: { background: 'var(--color-neutral-200)', color: 'var(--color-neutral-700)' },
}

const traceIcon: Record<string, string> = {
  decision: '◆', tool_call: '⚙', observation: '◎', flag: '⚑', awaiting_approval: '◷',
}

function factText(value: unknown): string {
  if (value == null) return '—'
  return typeof value === 'string' ? value : JSON.stringify(value)
}

export default function SkuScreen({ skuId, onBack, onSkuChange, onOrderChanged }: Props) {
  const [data, setData] = useState<SkuExplanation | null>(null)
  const [narrative, setNarrative] = useState<{ text: string; source: string } | null>(null)
  const [narrativeLoading, setNarrativeLoading] = useState(false)
  const narrativeRequest = useRef(0)
  const [qty, setQty] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const loadNarrative = useCallback(async (id: SkuId) => {
    const request = ++narrativeRequest.current
    setNarrative(null)
    setNarrativeLoading(true)
    try {
      const result = await getSkuNarrative(id)
      if (request === narrativeRequest.current) setNarrative(result)
    } catch {
      // Карточка остаётся полезной и при временной недоступности отдельного обоснования.
    } finally {
      if (request === narrativeRequest.current) setNarrativeLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!skuId) return
    let active = true
    const pendingNarrative = narrativeRequest
    getSkuExplanation(skuId).then(card => {
      if (!active) return
      setData(card)
      void loadNarrative(skuId)
    }).catch(cause => { if (active) setError(String(cause)) })
    return () => { active = false; pendingNarrative.current++ }
  }, [skuId, loadNarrative])

  async function applyManual(action: 'set_manual_qty' | 'clear_manual_qty') {
    if (!skuId || !data) return
    setSaving(true)
    setError('')
    try {
      const orderVersion = data.header.order?.version
      const orderRevision = data.header.order?.revision
      const payload = action === 'set_manual_qty'
        ? { action, qty: Number(qty), reason: reason.trim(), order_version: orderVersion, order_revision: orderRevision }
        : { action, order_version: orderVersion, order_revision: orderRevision }
      const result = await skuAction(skuId, payload)
      onOrderChanged?.(result.header)
      setData(await getSkuExplanation(skuId))
      void loadNarrative(skuId)
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

  const maxSales = Math.max(
    ...data.chart.months.map(m => Math.max(m.sales, Math.max(0, m.sales - m.one_off_excluded) + m.restored)),
    ...data.chart.forecast.map(f => f.qty),
    1,
  )
  const barHeight = (value: number) => value > 0 ? Math.max(2, Math.round((value / maxSales) * 100)) : 0
  const restoredMonths = data.chart.months.filter(m => m.restored > 0).length
  const shownSales = data.chart.months.reduce((sum, m) => sum + m.sales, 0)
  const formatQty = (value: number) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(value)

  return (
    <div className="page">
      <div className="page-head">
        <div><button className='btn btn-ghost' onClick={onBack}>← К рекомендациям</button><h1 style={{ marginTop: 10 }}>{data.sku.name}</h1><p className="page-subtitle">История и прогноз, поправки спроса, остатки, поступления и пошаговая арифметика заказа.</p></div>
        <div className="inline-actions"><button className="btn btn-secondary" disabled={!data.nav.prev_sku_id} onClick={() => data.nav.prev_sku_id && onSkuChange(data.nav.prev_sku_id)}>← Предыдущая</button><button className="btn btn-secondary" disabled={!data.nav.next_sku_id} onClick={() => data.nav.next_sku_id && onSkuChange(data.nav.next_sku_id)}>Следующая →</button></div>
      </div>
      {error && <div className="notice" role="alert" style={{ marginBottom: 16 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <span className='tag tag-outline'>{data.sku.code_1c}</span>
        {data.sku.supplier_article && <span className='tag tag-outline'>{data.sku.supplier_article}</span>}
        <span className='tag tag-outline'>{data.sku.supplier.name}</span>
        <span className='tag tag-outline'>{data.sku.category ? `Кат. ${data.sku.category}` : 'Без категории'}</span>
        {data.status === 'order' && <span className='tag tag-accent'>Заказать</span>}
        {data.urgency === 'urgent' && <span className="tag tag-outline">Срочно</span>}
        {data.excess && <span className="tag tag-neutral">Избыточный запас</span>}
      </div>

      {data.issues.length > 0 && <div className="notice" style={{ marginBottom: 20 }}>{data.issues.map(issue => <div key={issue.key}>{issue.text}</div>)}</div>}

      <div className="data-two-column">        <div>
          <h2 style={{ marginBottom: 12 }}>История и прогноз</h2>
          {data.chart.months.length === 0 ? (
            <div className="notice" role="status">Истории продаж нет. Прогноз и рекомендуемое количество для этой позиции не рассчитаны. Проверьте источник данных; при необходимости укажите количество вручную с причиной.</div>
          ) : <>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 120, marginBottom: 8, overflowX: 'auto' }}>
            {data.chart.months.map(m => {
              const regularSales = Math.max(0, m.sales - m.one_off_excluded)
              const adjustedDemand = regularSales + m.restored
              return (
                <div key={m.month} title={`${m.month}: продано ${formatQty(m.sales)}, учтено ${formatQty(regularSales)}, восстановлено ${formatQty(m.restored)}${m.one_off_excluded ? `, разовые продажи исключены ${formatQty(m.one_off_excluded)}` : ''}`} style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center', minWidth: 28 }}>
                  <div style={{ width: '100%', height: 100, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 2 }}>
                    <div style={{ width: '42%', height: barHeight(m.sales), background: 'var(--color-neutral-300)', borderRadius: '2px 2px 0 0' }} />
                    <div style={{ width: '42%', height: barHeight(adjustedDemand), display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                      {m.restored > 0 && <div style={{ height: `${(m.restored / adjustedDemand) * 100}%`, background: 'repeating-linear-gradient(135deg, var(--color-accent-400) 0, var(--color-accent-400) 3px, var(--color-accent-100) 3px, var(--color-accent-100) 6px)', border: '1px dashed var(--color-accent-600)', boxSizing: 'border-box' }} />}
                      {regularSales > 0 && <div style={{ height: `${(regularSales / adjustedDemand) * 100}%`, background: 'var(--color-accent)', borderRadius: m.restored > 0 ? 0 : '2px 2px 0 0' }} />}
                    </div>
                  </div>
                  <span style={{ fontSize: 9, color: 'var(--color-neutral-600)', marginTop: 2 }}>{m.label}</span>
                </div>
              )
            })}
            {data.chart.forecast.map(f => (
              <div key={f.month} style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center', minWidth: 28, background: 'var(--color-accent-100)', borderRadius: 2 }}>
                <div title={`${f.month}: прогноз ${formatQty(f.qty)}`} style={{ width: '100%', height: barHeight(f.qty), background: 'var(--color-accent-400)', borderRadius: '2px 2px 0 0' }} />
                <span style={{ fontSize: 9, color: 'var(--color-accent-700)', marginTop: 2 }}>{f.label}</span>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 11, color: 'var(--color-neutral-600)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-neutral-300)', display: 'inline-block', borderRadius: 1 }} />Факт продаж</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-accent)', display: 'inline-block', borderRadius: 1 }} />Регулярные продажи</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'repeating-linear-gradient(135deg, var(--color-accent-400) 0, var(--color-accent-400) 3px, var(--color-accent-100) 3px, var(--color-accent-100) 6px)', border: '1px dashed var(--color-accent-600)', display: 'inline-block', borderRadius: 1 }} />Оценка по нулевому/пустому остатку</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-accent-100)', border: '1px solid var(--color-accent-400)', display: 'inline-block', borderRadius: 1 }} />Прогноз</span>
          </div>
          {restoredMonths > 0 && <p className="tiny" style={{ marginTop: 8 }}>За показанный период фактически продано {formatQty(shownSales)} шт. Спрос оценён в {restoredMonths} из {data.chart.months.length} месяцев. Месяцев с нулевым/пустым остатком за всю историю: {data.stockouts?.length ?? 0}. Оценку нужно проверить по исходным остаткам.</p>}

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
          </>}

          <div className="page-section">
            <h3 className="card-title" style={{ fontSize: 18, marginBottom: 8 }}>Поправки спроса</h3>
            <p className="tiny">Разовые продажи и месяцы с нулевым или пустым начальным остатком показываются по расчёту. Подтверждение периодов выполняется в источнике данных.</p>
            {data.events?.map(event => <div className="blueprint panel" style={{ marginTop: 8 }} key={event.id}><strong>{event.title_text}</strong><p className="tiny" style={{ marginTop: 4 }}>{event.note_text}</p></div>)}
            {!!data.stockouts?.length && <details style={{ marginTop: 12 }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Месяцы с нулевым/пустым остатком ({data.stockouts.length})</summary>
              {data.stockouts.map(item => <div className="blueprint panel" style={{ marginTop: 8 }} key={item.id}><strong>{item.title_text}</strong><p className="tiny" style={{ marginTop: 4 }}>{item.note_text}</p></div>)}
            </details>}
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
                <div style={{ fontSize: 20, fontFamily: 'var(--font-heading)', fontWeight: 600 }}>{data.stock.reserve ?? '—'}</div>
                <div style={{ fontSize: 11, color: 'var(--color-neutral-600)' }}>в резерве</div>
              </div>
            </div>
            {data.header.data_mode === 'imported' && data.sku.supplier.id === 'IEK' && data.stock.free !== null && (
              <div className="notice tiny" style={{ marginBottom: 12 }}>
                Для ИЭК нет отдельного снимка свободного остатка на дату расчёта. Показанное значение взято из начального остатка последнего месяца; проверьте его перед утверждением заказа.
              </div>
            )}
            {data.inbound.length > 0 && (
              <table className='table' style={{ fontSize: 12 }}>
                <thead><tr><th>Документ</th><th>Кол-во</th><th>ETA</th><th>Учтён</th></tr></thead>
                <tbody>
                  {data.inbound.map(ib => (
                    <tr key={ib.id}>
                      <td>{ib.doc_text}</td>
                      <td>{new Intl.NumberFormat('ru-RU').format(ib.qty)}</td>
                      <td>{ib.eta ?? '—'} <span style={{ color: 'var(--color-neutral-500)' }}>({ib.where_text})</span></td>
                      <td>{ib.counted ? <span className='tag tag-accent'>Да</span> : <span className='tag tag-neutral'>Нет</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>        <div>
          <h2 style={{ marginBottom: 12 }}>Расчёт рекомендации</h2>
          <div className='notice' style={{ marginBottom: 16 }}>
            {narrative?.text || data.explanation_text}
            <div className="tiny" style={{ marginTop: 8 }}>
              {narrativeLoading ? 'Формулирую обоснование…' : narrative?.source.startsWith('nvidia:') ? 'Сформулировано ИИ, числа из расчёта' : 'Шаблон'}
            </div>
          </div>
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

          {!!data.agent_trace?.length && (
            <section className="blueprint panel" style={{ marginTop: 20 }}>
              <h3 className="card-title" style={{ marginBottom: 12 }}>Что проверил агент</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {data.agent_trace.map(event => (
                  <div key={event.seq} style={{ padding: '10px 12px', border: '1px solid var(--color-divider)', borderRadius: 2 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span aria-hidden="true" style={{ ...traceTone[event.status], borderRadius: 2, minWidth: 24, textAlign: 'center' }}>{traceIcon[event.type] || '•'}</span>
                      <strong style={{ fontSize: 13 }}>{event.title}</strong>
                    </div>
                    {event.tool && <div className="tiny muted" style={{ marginTop: 4, marginLeft: 32 }}>{event.tool}</div>}
                    {Object.keys(event.facts || {}).length > 0 && (
                      <details style={{ marginTop: 8, marginLeft: 32 }}>
                        <summary className="tiny" style={{ cursor: 'pointer' }}>Факты расчёта</summary>
                        <table className="table" style={{ fontSize: 11, marginTop: 6 }}>
                          <tbody>{Object.entries(event.facts).map(([key, value]) => (
                            <tr key={key}><th scope="row">{key}</th><td>{factText(value)}</td></tr>
                          ))}</tbody>
                        </table>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

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
