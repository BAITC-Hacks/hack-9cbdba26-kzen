import { useMemo, useState } from 'react'
import type { RecommendationsPage, RecommendationRow, SkuId, SkuStatus } from '../types'
import { searchRecommendations } from '../api/client'

interface Props { data: RecommendationsPage; onSkuClick: (id: SkuId) => void }

const format = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('ru-RU').format(value)

function Status({ row }: { row: RecommendationRow }) {
  const label: Record<SkuStatus, string> = { order: 'Заказать', enough: 'Запаса достаточно', needs_data: 'Нужны данные', insufficient_history: 'Недостаточно истории' }
  return <span className={`tag ${row.status === 'order' ? 'tag-accent' : row.status === 'needs_data' ? 'tag-outline' : 'tag-neutral'}`}>{label[row.status]}</span>
}

export default function RecommendationsScreen({ data, onSkuClick }: Props) {
  const [view, setView] = useState(data)
  const [q, setQ] = useState('')
  const [supplier, setSupplier] = useState('')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('deficit')
  const [delay, setDelay] = useState(0)
  const [demand, setDemand] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const categories = useMemo(() => Array.from(new Map(data.groups.flatMap(group => group.rows.map(row => [`${row.supplier.id}|${row.category || '—'}`, { value: `${row.supplier.id}|${row.category || '—'}`, label: `${row.supplier.name} · ${row.category || 'Без категории'}` }]))).values()), [data])

  async function search(useWhatIf = false) {
    setLoading(true)
    setError('')
    try {
      const result = await searchRecommendations({ q, supplier_id: supplier || null, category: category || null, status: status || null, sort, ...(useWhatIf && (delay !== 0 || demand !== 0) ? { what_if: { delay_days: delay, demand_pct: demand } } : {}) })
      setView(result)
    } catch (cause) { setError(`Не удалось обновить рекомендации: ${String(cause)}`) }
    finally { setLoading(false) }
  }

  const { summary } = view
  const metrics = [
    { label: 'Заказать', value: summary.order },
    { label: 'Запаса достаточно', value: summary.enough },
    { label: 'Нужны данные', value: summary.needs_data },
    { label: 'Недостаточно истории', value: summary.insufficient_history },
    { label: 'Избыточный запас', value: summary.excess },
  ]

  return <div className="page page-recommendations">
    <header className="page-head"><div><h1>Рекомендованные заказы</h1><p className="page-subtitle">Нажмите строку, чтобы открыть расчёт по артикулу.</p></div></header>
    <div className="metric-grid recommendation-metrics">{metrics.map(metric => <div className="metric blueprint" key={metric.label}><i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" /><span className="metric-value">{format(metric.value)}</span><div className="metric-label">{metric.label}</div></div>)}</div>

    <section className="recommendation-filters">
      <div className="toolbar">
        <div className="field"><label htmlFor="recommendation-search">Поиск: код 1С, артикул, название</label><input id="recommendation-search" className="input" type="search" value={q} onChange={event => setQ(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void search(!!view.what_if) }} placeholder="например, City9" /></div>
        <div className="field"><label htmlFor="supplier-filter">Поставщик</label><select id="supplier-filter" className="input" value={supplier} onChange={event => { setSupplier(event.target.value); setCategory('') }}><option value="">Все поставщики</option><option value="SE">Systeme Electric</option><option value="IEK">ИЭК</option></select></div>
        <div className="field"><label htmlFor="category-filter">Категория</label><select id="category-filter" className="input" value={category} onChange={event => setCategory(event.target.value)}><option value="">Все категории</option>{categories.filter(item => !supplier || item.value.startsWith(`${supplier}|`)).map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>
        <div className="field"><label htmlFor="status-filter">Статус</label><select id="status-filter" className="input" value={status} onChange={event => setStatus(event.target.value)}><option value="">Все статусы</option><option value="order">К заказу</option><option value="enough">Достаточно</option><option value="needs_data">Нужны данные</option><option value="insufficient_history">Мало истории</option></select></div>
        <div className="field"><label htmlFor="sort-filter">Сортировка</label><select id="sort-filter" className="input" value={sort} onChange={event => setSort(event.target.value)}><option value="deficit">По сроку дефицита</option><option value="code">По коду 1С</option></select></div>
        <button className="btn btn-secondary" type="button" onClick={() => void search(!!view.what_if)} disabled={loading}>Показать</button>
      </div>
    </section>

    <section className="blueprint recommendation-whatif">
      <i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" />
      <div><h2 className="card-title" style={{ fontSize: 18 }}>Что если</h2><p className="tiny">Сценарий не сохраняется в версию; утверждение недоступно, пока он активен.</p></div>
      <div className="toolbar"><div className="field"><label htmlFor="delay-days">Задержка всех поставок, дн.</label><input id="delay-days" className="input" type="number" min="0" value={delay} onChange={event => setDelay(Number(event.target.value))} /></div><div className="field"><label htmlFor="demand-pct">Изменение спроса, %</label><input id="demand-pct" className="input" type="number" min="-100" value={demand} onChange={event => setDemand(Number(event.target.value))} /></div><button type="button" className="btn btn-secondary" disabled={loading} onClick={() => void search(true)}>Применить</button><button type="button" className="btn btn-ghost" disabled={loading} onClick={() => { setDelay(0); setDemand(0); setLoading(true); searchRecommendations({ q, supplier_id: supplier || null, category: category || null, status: status || null, sort }).then(setView).catch(cause => setError(String(cause))).finally(() => setLoading(false)) }}>Сбросить</button></div>
    </section>

    {error && <div className="notice page-section" role="alert">{error}</div>}
    {view.groups.map(group => <section className="recommendation-group" key={group.supplier.id}>
      <div className="inline-actions" style={{ marginBottom: 10 }}><h2>{group.supplier.name}</h2><span className="tag tag-neutral">{group.count_text}</span></div>
      <div className="scroll-table"><table className="table" style={{ minWidth: 1280 }}><thead><tr><th>Поставщик</th><th>Код 1С</th><th>Артикул</th><th style={{ minWidth: 220 }}>Наименование</th><th>Ед.</th><th className="numeric">Свободно</th><th className="numeric">Путь · ETA</th><th className="numeric">Заказ</th><th style={{ minWidth: 230 }}>Обоснование</th><th>Срочность</th><th>Статус</th></tr></thead><tbody>{group.rows.map(row => <tr className="clickable" key={row.sku_id} tabIndex={0} onClick={() => onSkuClick(row.sku_id)} onKeyDown={event => { if (event.key === 'Enter') onSkuClick(row.sku_id) }}><td className="tiny">{group.supplier.name}</td><td><code>{row.code_1c}</code></td><td className="tiny">{row.supplier_article || '—'}</td><td>{row.name}</td><td>{row.unit}</td><td className="numeric">{format(row.free_stock)}</td><td className="numeric">{row.inbound.length ? row.inbound.map(item => `${format(item.qty)}${item.eta ? ` · ${item.eta.slice(5)}` : ''}`).join(', ') : '—'}</td><td className="numeric"><strong>{format(row.final_qty)}</strong>{row.manual && <span className="tag tag-outline" style={{ marginLeft: 4 }}>ручн.</span>}</td><td className="tiny">{row.reason_short}</td><td>{row.urgency === 'urgent' ? 'Срочно' : row.urgency === 'this_cycle' ? 'В этом цикле' : '—'}</td><td><Status row={row} />{row.excess && <span className="tag tag-neutral" style={{ marginLeft: 4 }}>избыток</span>}</td></tr>)}</tbody></table></div>
    </section>)}
    {view.groups.length === 0 && <div className="empty-state page-section">По выбранным фильтрам позиции не найдены.</div>}
    <section className="recommendation-trends"><h2>Тренды по категориям</h2><button className="btn btn-ghost" type="button" disabled title="API пока не отдаёт тренды по категориям">Показать</button></section>
  </div>
}
