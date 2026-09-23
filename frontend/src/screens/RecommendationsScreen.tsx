import { useEffect, useRef, useState } from 'react'
import type { AgentTraceEvent, AppHeader, DataOverview, RecommendationsPage, RecommendationRow, SkuId, SkuStatus, Supplier } from '../types'
import { getDataOverview, searchRecommendations } from '../api/client'

interface Props { data: RecommendationsPage; onSkuClick: (id: SkuId) => void; agentTrace?: AgentTraceEvent[]; onHeaderChange?: (header: AppHeader) => void }

type SearchQuery = Parameters<typeof searchRecommendations>[0]
type SearchMode = 'preserve' | 'apply' | 'reset'
const PAGE_SIZE = 100

const format = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('ru-RU').format(value)

function Status({ row }: { row: RecommendationRow }) {
  const label: Record<SkuStatus, string> = { order: 'Заказать', enough: 'Запаса достаточно', needs_data: 'Нужны данные', insufficient_history: 'Недостаточно истории' }
  return <span className={`tag ${row.status === 'order' ? 'tag-accent' : row.status === 'needs_data' ? 'tag-outline' : 'tag-neutral'}`}>{label[row.status]}</span>
}

function factText(value: unknown): string {
  if (value === null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export default function RecommendationsScreen({ data, onSkuClick, agentTrace = [], onHeaderChange }: Props) {
  const [view, setView] = useState(data)
  const [appliedQuery, setAppliedQuery] = useState<SearchQuery>({ page_size: PAGE_SIZE })
  const [q, setQ] = useState('')
  const [supplier, setSupplier] = useState('')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('deficit')
  const [delay, setDelay] = useState(0)
  const [demand, setDemand] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [categoryOptions, setCategoryOptions] = useState<DataOverview['settings']['category_options']>([])
  const [supplierOptions, setSupplierOptions] = useState<Supplier[]>(data.groups.map(group => group.supplier))
  const [categoryLoading, setCategoryLoading] = useState(true)
  const [categoryError, setCategoryError] = useState('')
  const requestId = useRef(0)

  useEffect(() => {
    let active = true
    getDataOverview()
      .then(overview => {
        if (!active) return
        setCategoryOptions(overview.settings.category_options.filter(option => option.value !== null))
        setSupplierOptions(overview.settings.suppliers.map(({ id, name }) => ({ id, name })))
        setCategoryError('')
      })
      .catch(cause => { if (active) setCategoryError(String(cause)) })
      .finally(() => { if (active) setCategoryLoading(false) })
    return () => { active = false }
  }, [])

  async function search(mode: SearchMode = 'preserve') {
    const scenario = mode === 'apply'
      ? (delay !== 0 || demand !== 0 ? { delay_days: delay, demand_pct: demand } : null)
      : mode === 'reset' ? null : view.what_if
    const query: SearchQuery = {
      q, supplier_id: supplier || null, category: category || null, status: status || null,
      sort, page_size: PAGE_SIZE, ...(scenario ? { what_if: scenario } : {}),
    }
    const currentRequest = ++requestId.current
    setLoading(true)
    setError('')
    try {
      const result = await searchRecommendations(query)
      if (currentRequest !== requestId.current) return
      setView(result)
      setAppliedQuery(query)
      onHeaderChange?.(result.header)
      if (mode === 'reset') { setDelay(0); setDemand(0) }
    } catch (cause) {
      if (currentRequest === requestId.current) setError(`Не удалось обновить рекомендации: ${String(cause)}`)
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }

  async function goToPage(supplierId: string, page: number) {
    const query: SearchQuery = {
      ...appliedQuery,
      page: { ...Object.fromEntries(view.groups.map(group => [group.supplier.id, group.page])), [supplierId]: page },
    }
    const currentRequest = ++requestId.current
    setLoading(true)
    setError('')
    try {
      const result = await searchRecommendations(query)
      if (currentRequest !== requestId.current) return
      setView(result)
      setAppliedQuery(query)
      onHeaderChange?.(result.header)
    } catch (cause) {
      if (currentRequest === requestId.current) setError(`Не удалось открыть страницу: ${String(cause)}`)
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
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
    <header className="page-head"><div><h1>Рекомендованные заказы</h1><p className="page-subtitle">{view.what_if ? 'Сейчас показана симуляция. Сбросьте её, чтобы открыть исходный расчёт по артикулу.' : 'Нажмите строку, чтобы открыть расчёт по артикулу.'}</p></div></header>
    <div className="metric-grid recommendation-metrics">{metrics.map(metric => <div className="metric blueprint" key={metric.label}><i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" /><span className="metric-value">{format(metric.value)}</span><div className="metric-label">{metric.label}</div></div>)}</div>

    <section className="recommendation-filters">
      <div className="toolbar">
        <div className="field"><label htmlFor="recommendation-search">Поиск: код 1С, артикул, название</label><input id="recommendation-search" className="input" type="search" value={q} onChange={event => setQ(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !loading) void search() }} placeholder="например, City9" /></div>
        <div className="field"><label htmlFor="supplier-filter">Поставщик</label><select id="supplier-filter" className="input" value={supplier} onChange={event => { setSupplier(event.target.value); setCategory('') }}><option value="">Все поставщики</option>{supplierOptions.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
        <div className="field"><label htmlFor="category-filter">Категория</label><select id="category-filter" className="input" value={category} disabled={categoryLoading || !!categoryError} onChange={event => setCategory(event.target.value)}><option value="">{categoryLoading ? 'Загрузка категорий…' : categoryError ? 'Категории недоступны' : 'Все категории'}</option>{categoryOptions.filter(item => item.value && (!supplier || item.value.startsWith(`${supplier}|`))).map(item => <option key={item.value} value={item.value || ''}>{supplierOptions.find(option => option.id === item.value?.split('|')[0])?.name || item.value?.split('|')[0]} · {item.label}</option>)}</select></div>
        <div className="field"><label htmlFor="status-filter">Статус</label><select id="status-filter" className="input" value={status} onChange={event => setStatus(event.target.value)}><option value="">Все статусы</option><option value="order">К заказу</option><option value="enough">Достаточно</option><option value="needs_data">Нужны данные</option><option value="insufficient_history">Мало истории</option></select></div>
        <div className="field"><label htmlFor="sort-filter">Сортировка</label><select id="sort-filter" className="input" value={sort} onChange={event => setSort(event.target.value)}><option value="deficit">По сроку дефицита</option><option value="code">По коду 1С</option></select></div>
        <button className="btn btn-secondary" type="button" onClick={() => void search()} disabled={loading}>Показать</button>
      </div>
    </section>

    <section className="blueprint recommendation-whatif">
      <i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" />
      <div><h2 className="card-title" style={{ fontSize: 18 }}>Что если</h2><p className="tiny">Сценарий меняет таблицу и показатели; в сохранённый заказ он не записывается.</p></div>
      <div className="toolbar"><div className="field"><label htmlFor="delay-days">Задержка всех поставок, дн.</label><input id="delay-days" className="input" type="number" min="0" value={delay} onChange={event => setDelay(Number(event.target.value))} /></div><div className="field"><label htmlFor="demand-pct">Изменение спроса, %</label><input id="demand-pct" className="input" type="number" min="-100" value={demand} onChange={event => setDemand(Number(event.target.value))} /></div><button type="button" className="btn btn-secondary" disabled={loading} onClick={() => void search('apply')}>Применить</button><button type="button" className="btn btn-ghost" disabled={loading || !view.what_if} onClick={() => void search('reset')}>Сбросить</button></div>
    </section>

    {view.what_if && <div className="notice" style={{ order: 4 }} role="status">Активна симуляция: строки ниже нельзя открыть, потому что карточка показывает исходный сохранённый расчёт. Экран согласования также показывает исходный заказ; результаты симуляции там не утверждаются. Для работы с исходным заказом нажмите «Сбросить».</div>}
    {categoryError && <div className="notice" style={{ order: 1 }} role="alert">Не удалось загрузить полный список категорий: {categoryError}. Поиск и другие фильтры работают.</div>}
    {agentTrace.length > 0 && <section className="blueprint panel" style={{ order: 4 }}>
      <div className="inline-actions" style={{ marginBottom: 10 }}><h2 className="card-title" style={{ fontSize: 18 }}>Ход работы агента</h2><span className="tag tag-neutral">{agentTrace.length} шагов</span></div>
      <div style={{ display: 'grid', gap: 8 }}>{agentTrace.map(event => <details key={event.seq} style={{ borderTop: '1px solid var(--color-divider)', paddingTop: 8 }}>
        <summary className="inline-actions" style={{ cursor: 'pointer' }}><span className="tiny">{event.seq}.</span><span>{event.title}</span><span className={`tag ${event.status === 'ok' ? 'tag-accent' : event.status === 'waiting' ? 'tag-neutral' : 'tag-outline'}`}>{event.status === 'ok' ? 'Готово' : event.status === 'warning' ? 'Требует внимания' : event.status === 'blocked' ? 'Заблокировано' : 'Ожидает'}</span></summary>
        <div style={{ padding: '8px 18px 2px' }}>{event.tool && <div className="tiny">Инструмент: <code>{event.tool}</code></div>}{event.sku && <div className="tiny">Артикул: <code>{event.sku}</code></div>}
          {Object.entries(event.facts).length > 0 && <div className="scroll-table"><table className="table"><tbody>{Object.entries(event.facts).map(([key, value]) => <tr key={key}><td className="tiny" style={{ width: '35%' }}>{key}</td><td>{factText(value)}</td></tr>)}</tbody></table></div>}
        </div>
      </details>)}</div>
    </section>}
    {error && <div className="notice page-section" role="alert">{error}</div>}
    {view.groups.map(group => <section className="recommendation-group" key={group.supplier.id}>
      <div className="inline-actions" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
        <div className="inline-actions"><h2>{group.supplier.name}</h2><span className="tag tag-neutral">{group.count_text}</span><span className="tiny">Показано {format((group.page - 1) * PAGE_SIZE + 1)}–{format((group.page - 1) * PAGE_SIZE + group.rows.length)} из {format(group.total)}</span></div>
        {group.pages > 1 && <div className="inline-actions"><button className="btn btn-ghost" type="button" disabled={loading || group.page <= 1} onClick={() => void goToPage(group.supplier.id, group.page - 1)}>Назад</button><label className="tiny">Страница <select className="input" style={{ width: 'auto', display: 'inline-block', marginLeft: 4 }} value={group.page} disabled={loading} onChange={event => void goToPage(group.supplier.id, Number(event.target.value))}>{Array.from({ length: group.pages }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select> из {group.pages}</label><button className="btn btn-ghost" type="button" disabled={loading || group.page >= group.pages} onClick={() => void goToPage(group.supplier.id, group.page + 1)}>Вперёд</button></div>}
      </div>
      <div className="scroll-table"><table className="table" style={{ minWidth: 1280 }}><thead><tr><th>Поставщик</th><th>Код 1С</th><th>Артикул</th><th style={{ minWidth: 220 }}>Наименование</th><th>Ед.</th><th className="numeric">Свободно</th><th className="numeric">Путь · ETA</th><th className="numeric">Заказ</th><th style={{ minWidth: 230 }}>Обоснование</th><th>Срочность</th><th>Статус</th></tr></thead><tbody>{group.rows.map(row => <tr className={view.what_if ? '' : 'clickable'} key={row.sku_id} tabIndex={view.what_if ? undefined : 0} onClick={view.what_if ? undefined : () => onSkuClick(row.sku_id)} onKeyDown={view.what_if ? undefined : event => { if (event.key === 'Enter') onSkuClick(row.sku_id) }}><td className="tiny">{group.supplier.name}</td><td><code>{row.code_1c}</code></td><td className="tiny">{row.supplier_article || '—'}</td><td>{row.name}</td><td>{row.unit}</td><td className="numeric">{format(row.free_stock)}</td><td className="numeric">{row.inbound.length ? row.inbound.map(item => `${format(item.qty)}${item.eta ? ` · ${item.eta.slice(5)}` : ''}`).join(', ') : '—'}</td><td className="numeric"><strong>{format(row.final_qty)}</strong>{row.manual && <span className="tag tag-outline" style={{ marginLeft: 4 }}>ручн.</span>}</td><td className="tiny">{row.reason_short}</td><td>{row.urgency === 'urgent' ? 'Срочно' : row.urgency === 'this_cycle' ? 'В этом цикле' : '—'}</td><td><Status row={row} />{row.excess && <span className="tag tag-neutral" style={{ marginLeft: 4 }}>избыток</span>}</td></tr>)}</tbody></table></div>
    </section>)}
    {view.groups.length === 0 && <div className="empty-state page-section">По выбранным фильтрам позиции не найдены.</div>}
    <section className="recommendation-trends"><h2>Тренды по категориям</h2><button className="btn btn-ghost" type="button" disabled title="API пока не отдаёт тренды по категориям">Показать</button></section>
  </div>
}
