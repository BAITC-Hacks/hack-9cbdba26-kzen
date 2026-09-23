import { useCallback, useEffect, useRef, useState } from 'react'
import type { AgentTraceEvent, AppHeader, SkuExplanation, SkuId } from '../types'
import { getSkuExplanation, getSkuNarrative, skuAction } from '../api/client'
import Icon from '../components/ui/Icon'
import { formatInt, formatQty } from '../components/ui/format'
import { statusLabel } from '../components/ui/status'
import { Badge, Card, CardHeader, EmptyState, Loading, Notice } from '../components/ui'

interface Props { skuId: SkuId | null; onBack: () => void; onSkuChange: (id: SkuId) => void; onOrderChanged?: (header: AppHeader) => void }

const TRACE_ICON: Record<string, string> = {
  decision: 'sparkles', tool_call: 'settings', observation: 'eye', flag: 'flag', awaiting_approval: 'clock',
}

function factText(value: unknown): string {
  if (value == null) return '—'
  return typeof value === 'string' ? value : JSON.stringify(value)
}

// Источник обоснования приходит строкой: имя бэкенда LLM либо «template…».
const isAiNarrative = (source: string) => !(source.startsWith('template') || source === 'none')

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

  if (!skuId) return (
    <div className="page">
      <button className="breadcrumb" type="button" onClick={onBack}><Icon name="arrow-left" size={14} />Рекомендации</button>
      <EmptyState icon="package" title="Позиция не выбрана">Откройте строку в таблице рекомендаций, чтобы увидеть расчёт.</EmptyState>
    </div>
  )
  if (!data) return (
    <div className="page">
      <button className="breadcrumb" type="button" onClick={onBack}><Icon name="arrow-left" size={14} />Рекомендации</button>
      {error ? <Notice tone="danger" role="alert">{error}</Notice> : <Loading text="Загружаем расчёт по позиции…" />}
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
  // Итоговый шаг расчёта помечен large; при ручной правке показываем её число.
  const finalStep = data.steps.find(step => step.large)
  const heroValue = data.manual.active && data.manual.qty != null ? formatQty(data.manual.qty) : finalStep?.value_text ?? '—'
  const inboundTotal = data.inbound.filter(item => item.counted).reduce((sum, item) => sum + item.qty, 0)

  return (
    <div className="page stack">
      <header className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <button className="breadcrumb" type="button" onClick={onBack}><Icon name="arrow-left" size={14} />Рекомендации</button>
          <h1>{data.sku.name}</h1>
          <div className="chip-row" style={{ marginTop: 10 }}>
            <Badge tone="outline"><code className="mono">{data.sku.code_1c}</code></Badge>
            {data.sku.supplier_article && <Badge tone="outline">Арт. {data.sku.supplier_article}</Badge>}
            <Badge tone="outline">{data.sku.supplier.name}</Badge>
            <Badge tone="outline">{data.sku.category ? `Категория ${data.sku.category}` : 'Без категории'}</Badge>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" disabled={!data.nav.prev_sku_id} onClick={() => data.nav.prev_sku_id && onSkuChange(data.nav.prev_sku_id)}><Icon name="chevron-left" />Предыдущая</button>
          <button className="btn btn-secondary" disabled={!data.nav.next_sku_id} onClick={() => data.nav.next_sku_id && onSkuChange(data.nav.next_sku_id)}>Следующая<Icon name="chevron-right" /></button>
        </div>
      </header>

      {error && <Notice tone="danger" role="alert">{error}</Notice>}
      {data.issues.length > 0 && <Notice tone="warning">{data.issues.map(issue => <div key={issue.key}>{issue.text}</div>)}</Notice>}

      {/* Главный ответ карточки — сколько заказать — вынесен наверх, остальное объясняет это число. */}
      <div className="sku-hero">
        <div className="sku-hero-main">
          <span className="label">{data.manual.active ? 'Итог после ручной правки' : 'Рекомендуем заказать'}</span>
          <span className="value">{heroValue}{data.manual.active && <small>{data.sku.purchase_unit}</small>}</span>
          <div className="badges">
            <Badge>{statusLabel(data.status)}</Badge>
            {data.urgency === 'urgent' && <Badge tone="danger" dot>Срочно</Badge>}
            {data.urgency === 'this_cycle' && <Badge dot>В этом цикле</Badge>}
            {data.excess && <Badge>Избыточный запас</Badge>}
            {data.manual.active && <Badge icon="edit">Вручную</Badge>}
          </div>
        </div>
        <div className="mini-stat card"><div className="mini-stat-value">{formatInt(data.stock.free)}</div><div className="mini-stat-label">свободный остаток{data.stock.free_manual ? ' · вручную' : ''}</div></div>
        <div className="mini-stat card"><div className="mini-stat-value">{formatInt(data.stock.reserve)}</div><div className="mini-stat-label">в резерве</div></div>
        <div className="mini-stat card"><div className="mini-stat-value" style={{ color: data.stock.early_risk ? 'var(--danger-700)' : undefined }}>{data.stock.cover_days != null ? `${formatInt(data.stock.cover_days)} дн.` : '—'}</div><div className="mini-stat-label">хватит запаса · {data.stock.cover_text}</div></div>
        <div className="mini-stat card"><div className="mini-stat-value">{formatInt(inboundTotal)}</div><div className="mini-stat-label">в пути, учтено в расчёте</div></div>
      </div>

      {data.header.data_mode === 'imported' && data.sku.supplier.id === 'IEK' && data.stock.free !== null && (
        <Notice tone="warning">Для ИЭК нет отдельного снимка свободного остатка на дату расчёта. Показано значение из начального остатка последнего месяца; проверьте его перед утверждением.</Notice>
      )}

      <div className="grid-2">
        <div className="stack">
          <Card>
            <CardHeader icon="trending" title="История продаж и прогноз" subtitle={`База спроса: ${data.chart.base_from} – ${data.chart.base_to}`} />
            <div className="card-body">
              {data.chart.months.length === 0 ? (
                <Notice tone="warning" role="status">Истории продаж нет: прогноз и количество не рассчитаны. Проверьте источник данных или задайте количество вручную с причиной.</Notice>
              ) : (
                <>
                  <div className="chart">
                    {data.chart.months.map(m => {
                      const regularSales = Math.max(0, m.sales - m.one_off_excluded)
                      const adjustedDemand = regularSales + m.restored
                      return (
                        <div key={m.month} className="chart-col" title={`${m.month}: продано ${formatQty(m.sales)}, учтено ${formatQty(regularSales)}, восстановлено ${formatQty(m.restored)}${m.one_off_excluded ? `, разовые исключены ${formatQty(m.one_off_excluded)}` : ''}`}>
                          <div className="chart-bars">
                            <div className="chart-bar fact" style={{ height: barHeight(m.sales) }} />
                            <div className="chart-bar" style={{ height: barHeight(adjustedDemand), display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', background: 'transparent' }}>
                              {m.restored > 0 && <div className="chart-bar restored" style={{ width: '100%', height: `${(m.restored / adjustedDemand) * 100}%`, borderRadius: '3px 3px 0 0' }} />}
                              {regularSales > 0 && <div className="chart-bar regular" style={{ width: '100%', height: `${(regularSales / adjustedDemand) * 100}%`, borderRadius: m.restored > 0 ? 0 : undefined }} />}
                            </div>
                          </div>
                          <span className="chart-label">{m.label}</span>
                        </div>
                      )
                    })}
                    {data.chart.forecast.map(f => (
                      <div key={f.month} className="chart-col is-forecast" title={`${f.month}: прогноз ${formatQty(f.qty)}`}>
                        <div className="chart-bars"><div className="chart-bar forecast" style={{ width: '70%', height: barHeight(f.qty) }} /></div>
                        <span className="chart-label" style={{ color: 'var(--primary-700)' }}>{f.label}</span>
                      </div>
                    ))}
                  </div>
                  <div className="legend">
                    <span><i style={{ background: 'var(--gray-300)' }} />Факт продаж</span>
                    <span><i style={{ background: 'var(--primary-500)' }} />Регулярный спрос</span>
                    <span><i className="chart-bar restored" style={{ width: 12, height: 10 }} />Оценка за месяцы без остатка</span>
                    <span><i style={{ background: 'var(--primary-300)' }} />Прогноз</span>
                  </div>
                  {restoredMonths > 0 && <p className="tiny" style={{ marginTop: 10 }}>За период продано {formatQty(shownSales)} шт. Спрос дооценён в {restoredMonths} из {data.chart.months.length} месяцев; месяцев без остатка за всю историю: {data.stockouts?.length ?? 0}. Оценку стоит сверить с исходными остатками.</p>}
                  {shownSales === 0 && restoredMonths === 0 && data.chart.forecast.some(point => point.qty > 0) && <p className="tiny" style={{ marginTop: 10 }}>В показанных месяцах продаж нет. Прогноз на ближайший месяц — {formatQty(data.chart.forecast[0].qty)} шт. Он основан на более ранней истории; проверьте актуальность позиции перед заказом.</p>}
                  <table className="table table-kv" style={{ marginTop: 14 }}>
                    <tbody>
                      <tr><td>Средний регулярный спрос</td><td className="cell-primary">{formatQty(data.demand.regular_avg)} шт/мес</td></tr>
                      <tr><td>Сезонность</td><td>{data.demand.season} <span className="tiny">· {data.demand.season_source_text}</span></td></tr>
                      <tr><td>Тренд</td><td>{data.demand.trend_estimate_text} <span className="tiny">· {data.demand.trend_source_text}</span></td></tr>
                      <tr><td>Срок поставки</td><td>{data.params.lead_time_days} дн.</td></tr>
                      <tr><td>Цикл пересмотра</td><td>{data.params.review_days} дн.</td></tr>
                    </tbody>
                  </table>
                </>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader icon="flag" title="Поправки спроса" subtitle="Разовые продажи и месяцы без остатка — по расчёту. Подтверждение периодов выполняется в источнике данных." />
            <div className="card-body stack-sm">
              {data.events?.map(event => <Notice key={event.id} tone="neutral" icon="flag"><b>{event.title_text}</b><div className="tiny" style={{ marginTop: 2 }}>{event.note_text}</div></Notice>)}
              {!!data.stockouts?.length && (
                <details className="disclosure">
                  <summary><Icon name="chevron-right" size={12} />Месяцы с нулевым или пустым остатком ({data.stockouts.length})</summary>
                  <div className="stack-sm" style={{ marginTop: 8 }}>{data.stockouts.map(item => <Notice key={item.id} tone="neutral" icon="clock"><b>{item.title_text}</b><div className="tiny" style={{ marginTop: 2 }}>{item.note_text}</div></Notice>)}</div>
                </details>
              )}
              {!data.events?.length && !data.stockouts?.length && <p className="muted">Поправки для этой позиции не применялись.</p>}
            </div>
          </Card>

          {data.inbound.length > 0 && (
            <Card>
              <CardHeader icon="truck" title="Товар в пути" />
              <div className="table-wrap">
                <table className="table table-compact">
                  <thead><tr><th>Документ</th><th className="numeric">Кол-во</th><th>Поступление</th><th>Учтён</th></tr></thead>
                  <tbody>
                    {data.inbound.map(ib => (
                      <tr key={ib.id}>
                        <td className="cell-primary">{ib.doc_text}</td>
                        <td className="numeric">{formatInt(ib.qty)}</td>
                        <td>{ib.eta ?? '—'} <span className="tiny">· {ib.where_text}</span></td>
                        <td>{ib.counted ? <Badge tone="success" icon="check">да</Badge> : <Badge tone="neutral">нет</Badge>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>

        <div className="stack">
          <Card>
            <CardHeader icon="calculator" title="Как получилось это число" actions={
              narrativeLoading
                ? <Badge tone="neutral"><span className="spinner" style={{ width: 10, height: 10 }} />формулируем</Badge>
                : narrative && isAiNarrative(narrative.source)
                  ? <Badge tone="accent" icon="sparkles">Текст ИИ · числа из расчёта</Badge>
                  : <Badge tone="neutral">Шаблон</Badge>
            } />
            <div className="card-body stack-sm">
              <p style={{ lineHeight: 1.6 }}>{narrative?.text || data.explanation_text}</p>
              <div className="calc-steps">
                {data.steps.map(step => (
                  <div key={step.key} className={`calc-step${step.large ? ' is-total' : step.emphasis ? ' is-emphasis' : ''}`}>
                    <div><div className="calc-step-label">{step.label}</div>{step.note_text && <div className="calc-step-note">{step.note_text}</div>}</div>
                    <span className="calc-step-value">{step.value_text}</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader icon="edit" title="Ручная корректировка" subtitle="Правка сохраняется с причиной и видна руководителю при согласовании." />
            <div className="card-body">
              {data.manual.active ? (
                <div className="stack-sm">
                  <Notice tone="info" icon="edit"><b>{formatQty(data.manual.qty)} {data.sku.purchase_unit}</b> — {data.manual.reason}{data.manual.note_text ? ` · ${data.manual.note_text}` : ''}</Notice>
                  <div><button type="button" className="btn btn-secondary" onClick={() => void applyManual('clear_manual_qty')} disabled={saving}><Icon name="refresh" />Вернуть рекомендацию</button></div>
                </div>
              ) : (
                <div className="row" style={{ alignItems: 'flex-end', gap: 10 }}>
                  <div className="field" style={{ flex: '1 1 120px' }}>
                    <label htmlFor="manual-qty">Количество, {data.sku.purchase_unit}</label>
                    <input id="manual-qty" className="input" type="number" min="0" step="1" placeholder="0" value={qty} onChange={event => setQty(event.target.value)} />
                  </div>
                  <div className="field" style={{ flex: '2 1 220px' }}>
                    <label htmlFor="manual-reason">Причина</label>
                    <input id="manual-reason" className="input" type="text" placeholder="Например: проектный заказ клиента" value={reason} onChange={event => setReason(event.target.value)} />
                  </div>
                  <button className="btn btn-primary" disabled={saving || qty === '' || Number(qty) < 0 || !reason.trim()} onClick={() => void applyManual('set_manual_qty')}>Сохранить</button>
                </div>
              )}
            </div>
          </Card>

          {!!data.agent_trace?.length && (
            <Card>
              <CardHeader icon="sparkles" title="Что проверил агент" />
              <div className="card-body timeline">
                {data.agent_trace.map((event: AgentTraceEvent) => (
                  <div className="timeline-item" key={event.seq}>
                    <div className={`timeline-icon ${event.status}`}><Icon name={TRACE_ICON[event.type] || 'info'} size={14} /></div>
                    <div>
                      <div className="timeline-title">{event.title}</div>
                      {event.tool && <div className="tiny">{event.tool}</div>}
                      {Object.keys(event.facts || {}).length > 0 && (
                        <details className="disclosure" style={{ marginTop: 6 }}>
                          <summary><Icon name="chevron-right" size={12} />Факты расчёта</summary>
                          <table className="table table-kv" style={{ marginTop: 6, fontSize: 12 }}><tbody>{Object.entries(event.facts).map(([key, value]) => <tr key={key}><td>{key}</td><td>{factText(value)}</td></tr>)}</tbody></table>
                        </details>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card>
            <CardHeader icon="database" title="Откуда взяты данные" />
            <div className="table-wrap">
              <table className="table table-compact">
                <thead><tr><th>Показатель</th><th>Источник</th><th>Тип</th></tr></thead>
                <tbody>
                  {data.provenance.map((prov, i) => (
                    <tr key={i}>
                      <td className="cell-primary">{prov.input}</td>
                      <td className="muted" style={{ whiteSpace: 'normal' }}>{prov.source_text}</td>
                      <td><Badge tone={prov.origin === 'real' || prov.origin === 'imported' ? 'success' : prov.origin === 'synthetic' ? 'warning' : 'outline'}>{prov.origin === 'real' ? 'реальные' : prov.origin === 'synthetic' ? 'синтетика' : prov.origin === 'assumption' ? 'допущение' : prov.origin}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
