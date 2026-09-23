import { useEffect, useRef, useState } from 'react'
import type { AgentTraceEvent, AppHeader, DataOverview, RecommendationsPage, SkuId, SkuStatus, Supplier } from '../types'
import { getDataOverview, searchRecommendations } from '../api/client'
import Icon from '../components/ui/Icon'
import { formatInt } from '../components/ui/format'
import { Badge, Card, EmptyState, Notice, Stat, StatusBadge, UrgencyBadge } from '../components/ui'

interface Props {
  data: RecommendationsPage
  onSkuClick: (id: SkuId) => void
  agentTrace?: AgentTraceEvent[]
  onHeaderChange?: (header: AppHeader) => void
  onGoToData?: () => void
}

type SearchQuery = Parameters<typeof searchRecommendations>[0]
type SearchMode = 'preserve' | 'apply' | 'reset'
const PAGE_SIZE = 100

function factText(value: unknown): string {
  if (value === null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

const TRACE_STATUS = {
  ok: { label: 'Готово', tone: 'success' as const, icon: 'check' },
  warning: { label: 'Требует внимания', tone: 'warning' as const, icon: 'alert' },
  blocked: { label: 'Заблокировано', tone: 'danger' as const, icon: 'x' },
  waiting: { label: 'Ожидает', tone: 'neutral' as const, icon: 'clock' },
}

export default function RecommendationsScreen({ data, onSkuClick, agentTrace = [], onHeaderChange, onGoToData }: Props) {
  const [view, setView] = useState(data)
  const [appliedQuery, setAppliedQuery] = useState<SearchQuery>({ page_size: PAGE_SIZE })
  const [q, setQ] = useState('')
  const [supplier, setSupplier] = useState('')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState('deficit')
  const [delay, setDelay] = useState(0)
  const [demand, setDemand] = useState(0)
  const [whatIfOpen, setWhatIfOpen] = useState(!!data.what_if)
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

  async function runSearch(query: SearchQuery, after?: () => void, failText = 'Не удалось обновить рекомендации') {
    const currentRequest = ++requestId.current
    setLoading(true)
    setError('')
    try {
      const result = await searchRecommendations(query)
      if (currentRequest !== requestId.current) return
      setView(result)
      setAppliedQuery(query)
      onHeaderChange?.(result.header)
      after?.()
    } catch (cause) {
      if (currentRequest === requestId.current) setError(`${failText}: ${String(cause)}`)
    } finally {
      if (currentRequest === requestId.current) setLoading(false)
    }
  }

  function buildQuery(mode: SearchMode, overrides: Partial<{ status: string }> = {}): SearchQuery {
    const scenario = mode === 'apply'
      ? (delay !== 0 || demand !== 0 ? { delay_days: delay, demand_pct: demand } : null)
      : mode === 'reset' ? null : view.what_if
    const statusValue = overrides.status ?? status
    return {
      q, supplier_id: supplier || null, category: category || null, status: statusValue || null,
      sort, page_size: PAGE_SIZE, ...(scenario ? { what_if: scenario } : {}),
    }
  }

  function search(mode: SearchMode = 'preserve') {
    return runSearch(buildQuery(mode), () => { if (mode === 'reset') { setDelay(0); setDemand(0) } })
  }

  // Плитка со счётчиком работает как быстрый фильтр: клик по «Заказать»
  // показывает только позиции к заказу, повторный клик снимает фильтр.
  function toggleStatus(next: SkuStatus) {
    const value = status === next ? '' : next
    setStatus(value)
    void runSearch(buildQuery('preserve', { status: value }))
  }

  function goToPage(supplierId: string, page: number) {
    return runSearch({
      ...appliedQuery,
      page: { ...Object.fromEntries(view.groups.map(group => [group.supplier.id, group.page])), [supplierId]: page },
    }, undefined, 'Не удалось открыть страницу')
  }

  const { summary } = view
  const totalRows = view.groups.reduce((sum, group) => sum + group.total, 0)

  return (
    <div className="page stack">
      <header className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Рекомендованные заказы</h1>
          <p className="page-subtitle">
            {view.what_if
              ? 'Показана симуляция. Сбросьте сценарий, чтобы открывать позиции и работать с сохранённым заказом.'
              : 'Сервис посчитал потребность по каждой позиции. Откройте строку, чтобы увидеть расчёт, или перейдите к согласованию.'}
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn btn-secondary" onClick={onGoToData}><Icon name="settings" />Параметры расчёта</button>
        </div>
      </header>

      <div className="stat-grid">
        <Stat label="Заказать" value={formatInt(summary.order)} tone="accent" active={status === 'order'} onClick={() => toggleStatus('order')} hint="нужна поставка" />
        <Stat label="Достаточно" value={formatInt(summary.enough)} tone="success" active={status === 'enough'} onClick={() => toggleStatus('enough')} hint="запас покрывает горизонт" />
        <Stat label="Нужны данные" value={formatInt(summary.needs_data)} tone="warning" active={status === 'needs_data'} onClick={() => toggleStatus('needs_data')} hint="не попадут в файл для 1С" />
        <Stat label="Мало истории" value={formatInt(summary.insufficient_history)} tone="neutral" active={status === 'insufficient_history'} onClick={() => toggleStatus('insufficient_history')} hint="меньше 3 месяцев продаж" />
        <Stat label="Избыточный запас" value={formatInt(summary.excess)} tone="neutral" hint="заказывать не нужно" />
      </div>

      <Card>
        <div className="card-body">
          <div className="filter-bar">
            <div className="field">
              <label htmlFor="recommendation-search">Поиск</label>
              <div className="input-icon">
                <Icon name="search" size={16} />
                <input id="recommendation-search" className="input" type="search" value={q} onChange={event => setQ(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !loading) void search() }} placeholder="Код 1С, артикул или название" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="supplier-filter">Поставщик</label>
              <select id="supplier-filter" className="input" value={supplier} onChange={event => { setSupplier(event.target.value); setCategory('') }}>
                <option value="">Все поставщики</option>
                {supplierOptions.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="category-filter">Категория</label>
              <select id="category-filter" className="input" value={category} disabled={categoryLoading || !!categoryError} onChange={event => setCategory(event.target.value)}>
                <option value="">{categoryLoading ? 'Загрузка…' : categoryError ? 'Недоступны' : 'Все категории'}</option>
                {categoryOptions.filter(item => item.value && (!supplier || item.value.startsWith(`${supplier}|`))).map(item => (
                  <option key={item.value} value={item.value || ''}>
                    {supplierOptions.find(option => option.id === item.value?.split('|')[0])?.name || item.value?.split('|')[0]} · {item.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="status-filter">Статус</label>
              <select id="status-filter" className="input" value={status} onChange={event => setStatus(event.target.value)}>
                <option value="">Все статусы</option>
                <option value="order">Заказать</option>
                <option value="enough">Достаточно</option>
                <option value="needs_data">Нужны данные</option>
                <option value="insufficient_history">Мало истории</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="sort-filter">Сортировка</label>
              <select id="sort-filter" className="input" value={sort} onChange={event => setSort(event.target.value)}>
                <option value="deficit">Сначала срочные</option>
                <option value="code">По коду 1С</option>
              </select>
            </div>
            <button className="btn btn-primary" type="button" onClick={() => void search()} disabled={loading}>
              {loading ? <span className="spinner" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,.35)' }} /> : <Icon name="search" />}Показать
            </button>
          </div>
        </div>
        <div className="card-footer row-between">
          <div className="row">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setWhatIfOpen(open => !open)} aria-expanded={whatIfOpen}>
              <Icon name="sparkles" size={14} />Сценарий «что если»
              <Icon name={whatIfOpen ? 'chevron-down' : 'chevron-right'} size={14} />
            </button>
            {view.what_if && <Badge tone="accent" icon="sparkles">Задержка {view.what_if.delay_days} дн. · спрос {view.what_if.demand_pct > 0 ? '+' : ''}{view.what_if.demand_pct}%</Badge>}
          </div>
          <span className="tiny">Всего позиций по фильтру: {formatInt(totalRows)}</span>
        </div>
        {whatIfOpen && (
          <div className="card-body" style={{ borderTop: '1px solid var(--color-border)' }}>
            <div className="row-between">
              <div>
                <h3>Что если…</h3>
                <p className="tiny">Пересчитывает таблицу и счётчики. В сохранённый заказ сценарий не записывается.</p>
              </div>
              <div className="whatif-form">
                <div className="field"><label htmlFor="delay-days">Все поставки задержатся на, дн.</label><input id="delay-days" className="input" type="number" min="0" value={delay} onChange={event => setDelay(Number(event.target.value))} /></div>
                <div className="field"><label htmlFor="demand-pct">Спрос изменится на, %</label><input id="demand-pct" className="input" type="number" min="-100" value={demand} onChange={event => setDemand(Number(event.target.value))} /></div>
                <button type="button" className="btn btn-secondary" disabled={loading} onClick={() => void search('apply')}>Применить</button>
                <button type="button" className="btn btn-ghost" disabled={loading || !view.what_if} onClick={() => void search('reset')}>Сбросить</button>
              </div>
            </div>
          </div>
        )}
      </Card>

      {view.what_if && (
        <Notice tone="warning" role="status" icon="sparkles">
          <b>Активна симуляция.</b> Строки нельзя открыть: карточка показывает исходный сохранённый расчёт, а экран согласования — исходный заказ. Чтобы вернуться к нему, нажмите «Сбросить».
        </Notice>
      )}
      {categoryError && <Notice tone="warning" role="alert">Не удалось загрузить список категорий: {categoryError}. Поиск и остальные фильтры работают.</Notice>}
      {error && <Notice tone="danger" role="alert">{error}</Notice>}

      {agentTrace.length > 0 && (
        <Card>
          <div className="card-header">
            <div><h3><Icon name="sparkles" size={16} className="muted" />Что сделал агент при расчёте</h3><p className="tiny">Каждый шаг — бизнес-событие: что проверено и что найдено. Количество считает код, агент решает, какие проверки добавить.</p></div>
            <Badge tone="neutral">{agentTrace.length} шагов</Badge>
          </div>
          <div className="card-body timeline">
            {agentTrace.map(event => {
              const meta = TRACE_STATUS[event.status]
              return (
                <div className="timeline-item" key={event.seq}>
                  <div className={`timeline-icon ${event.status}`}><Icon name={meta.icon} size={14} /></div>
                  <div>
                    <div className="timeline-title">{event.title}<Badge tone={meta.tone}>{meta.label}</Badge></div>
                    {(event.tool || event.sku) && <div className="tiny" style={{ marginTop: 2 }}>{event.tool && <>Инструмент <code>{event.tool}</code></>}{event.tool && event.sku && ' · '}{event.sku && <>Артикул <code>{event.sku}</code></>}</div>}
                    {Object.keys(event.facts).length > 0 && (
                      <details className="disclosure" style={{ marginTop: 6 }}>
                        <summary><Icon name="chevron-right" size={12} />Факты</summary>
                        <table className="table table-kv" style={{ marginTop: 6, fontSize: 12 }}><tbody>{Object.entries(event.facts).map(([key, value]) => <tr key={key}><td>{key}</td><td>{factText(value)}</td></tr>)}</tbody></table>
                      </details>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {view.groups.map(group => (
        <Card key={group.supplier.id}>
          <div className="group-header">
            <div className="group-title">
              <h2>{group.supplier.name}</h2>
              <Badge tone="neutral">{group.count_text}</Badge>
              <span className="tiny">Показано {formatInt((group.page - 1) * PAGE_SIZE + 1)}–{formatInt((group.page - 1) * PAGE_SIZE + group.rows.length)} из {formatInt(group.total)}</span>
            </div>
            {group.pages > 1 && (
              <div className="pagination">
                <button className="btn btn-ghost btn-sm" type="button" disabled={loading || group.page <= 1} onClick={() => void goToPage(group.supplier.id, group.page - 1)} aria-label="Предыдущая страница"><Icon name="chevron-left" size={14} /></button>
                <label>Страница <select className="input" value={group.page} disabled={loading} onChange={event => void goToPage(group.supplier.id, Number(event.target.value))}>{Array.from({ length: group.pages }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select> из {group.pages}</label>
                <button className="btn btn-ghost btn-sm" type="button" disabled={loading || group.page >= group.pages} onClick={() => void goToPage(group.supplier.id, group.page + 1)} aria-label="Следующая страница"><Icon name="chevron-right" size={14} /></button>
              </div>
            )}
          </div>
          <div className="table-wrap">
            <table className="table" style={{ minWidth: 1180 }}>
              <thead>
                <tr>
                  <th>Код 1С</th>
                  <th style={{ minWidth: 240 }}>Наименование</th>
                  <th className="numeric">Свободно</th>
                  <th className="numeric">В пути · ETA</th>
                  <th className="numeric">Заказать</th>
                  <th style={{ minWidth: 240 }}>Обоснование</th>
                  <th>Срочность</th>
                  <th>Статус</th>
                  <th aria-label="Открыть" />
                </tr>
              </thead>
              <tbody>
                {group.rows.map(row => (
                  <tr
                    className={view.what_if ? '' : 'clickable'}
                    key={row.sku_id}
                    tabIndex={view.what_if ? undefined : 0}
                    onClick={view.what_if ? undefined : () => onSkuClick(row.sku_id)}
                    onKeyDown={view.what_if ? undefined : event => { if (event.key === 'Enter') onSkuClick(row.sku_id) }}
                  >
                    <td><code className="mono">{row.code_1c}</code>{row.supplier_article && <div className="cell-secondary">{row.supplier_article}</div>}</td>
                    <td><div className="cell-primary">{row.name}</div><div className="cell-secondary">{row.unit}{row.category ? ` · кат. ${row.category}` : ''}</div></td>
                    <td className="numeric">{formatInt(row.free_stock)}</td>
                    <td className="numeric">{row.inbound.length ? row.inbound.map(item => `${formatInt(item.qty)}${item.eta ? ` · ${item.eta.slice(8, 10)}.${item.eta.slice(5, 7)}` : ''}`).join(', ') : <span className="muted">—</span>}</td>
                    <td className="numeric"><span className="qty-strong">{formatInt(row.final_qty)}</span>{row.manual && <div><Badge tone="outline" icon="edit">вручную</Badge></div>}</td>
                    <td className="cell-secondary" style={{ whiteSpace: 'normal' }}>{row.reason_short}</td>
                    <td><UrgencyBadge urgency={row.urgency} /></td>
                    <td><div className="row" style={{ gap: 4 }}><StatusBadge status={row.status} />{row.excess && <Badge tone="neutral">избыток</Badge>}</div></td>
                    <td style={{ width: 36 }}>{!view.what_if && <Icon name="chevron-right" className="row-chevron" />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
      {view.groups.length === 0 && <EmptyState icon="search" title="Ничего не найдено">Измените фильтры или очистите поиск.</EmptyState>}
    </div>
  )
}
