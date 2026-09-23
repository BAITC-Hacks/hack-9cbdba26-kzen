import { useEffect, useState } from 'react'
import type { AppHeader, DataOverview } from '../types'
import { getDataOverview, resetSession, saveSettings } from '../api/client'
import Icon from '../components/ui/Icon'
import ImportPanel from '../components/ImportPanel'
import { formatDate, formatInt } from '../components/ui/format'
import { Badge, Card, CardHeader, EmptyState, Loading, Notice } from '../components/ui'

interface Props { header: AppHeader; onCalculate: () => Promise<void>; onReset: (header: AppHeader) => void }

const ORIGIN = {
  real: { label: 'реальные данные', tone: 'success' as const },
  synthetic: { label: 'синтетика', tone: 'warning' as const },
  assumption: { label: 'допущение', tone: 'outline' as const },
  manual: { label: 'вручную', tone: 'outline' as const },
  imported: { label: 'импорт', tone: 'success' as const },
  none: { label: 'нет', tone: 'neutral' as const },
}

const FLOW = ['Проверить данные и параметры', 'Рассчитать рекомендации', 'Проверить и поправить позиции', 'Согласовать и выгрузить в 1С']

export default function DataScreen({ header, onCalculate, onReset }: Props) {
  const [overview, setOverview] = useState<DataOverview | null>(null)
  const [settings, setSettings] = useState<DataOverview['settings'] | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ tone: 'info' | 'danger' | 'success'; text: string } | null>(null)

  useEffect(() => {
    getDataOverview().then(data => { setOverview(data); setSettings(data.settings) }).catch(error => setMessage({ tone: 'danger', text: String(error) }))
  }, [])

  async function calculate() {
    if (!settings) return
    setSaving(true)
    setMessage(null)
    try {
      await saveSettings({ category_filter: settings.category_filter, calc_date: settings.calc_date, suppliers: settings.suppliers.map(({ id, lead_time_days, review_days }) => ({ id, lead_time_days, review_days })), excess_months: settings.excess_months })
      await onCalculate()
    } catch (error) { setMessage({ tone: 'danger', text: `Не удалось выполнить расчёт: ${String(error)}` }) }
    finally { setSaving(false) }
  }

  async function reset() {
    if (!window.confirm('Сбросить расчёт, правки и версии текущей сессии?')) return
    setSaving(true)
    try {
      const result = await resetSession()
      const data = await getDataOverview()
      setOverview(data)
      setSettings(data.settings)
      onReset(result.header)
      setMessage({ tone: 'success', text: 'Сессия сброшена' })
    } catch (error) { setMessage({ tone: 'danger', text: `Не удалось сбросить сессию: ${String(error)}` }) }
    finally { setSaving(false) }
  }

  function updateSupplier(id: string, field: 'lead_time_days' | 'review_days', value: number) {
    setSettings(current => current && ({ ...current, suppliers: current.suppliers.map(supplier => supplier.id === id ? { ...supplier, [field]: value, horizon_days: field === 'lead_time_days' ? value + supplier.review_days : supplier.lead_time_days + value } : supplier) }))
  }

  const supplierName = (id: string) => id === 'SE' ? 'Systeme Electric' : 'ИЭК'

  return (
    <div className="page stack">
      <header className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Данные и параметры</h1>
          <p className="page-subtitle">Что загружено из выгрузок партнёра, насколько это свежо и с какими параметрами считается заказ. Позиции с проблемами остаются в расчёте со статусом «нужны данные».</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" type="button" onClick={reset} disabled={saving}><Icon name="refresh" />Сбросить сессию</button>
        </div>
      </header>

      {/* Главный призыв к действию: без запуска расчёта остальные экраны пусты. */}
      <Card className="card-accent">
        <div className="hero-cta">
          <div>
            <h2>{header.calc_at ? 'Пересчитать рекомендации' : 'Начните с расчёта'}</h2>
            <p className="tiny" style={{ marginTop: 4 }}>
              {header.calc_at ? `Последний расчёт: ${formatDate(header.calc_at)}. Пересчёт нужен после изменения параметров или свежей выгрузки.` : 'Сервис посчитает потребность по каждой позиции и соберёт черновик заказа по поставщикам.'}
            </p>
            <div className="flow-steps">
              {FLOW.map((step, index) => <span className="flow-step" key={step}><span className="flow-step-num">{index + 1}</span>{step}</span>)}
            </div>
          </div>
          <button className="btn btn-primary btn-lg" type="button" onClick={calculate} disabled={saving || !settings}>
            {saving ? <span className="spinner" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,.35)' }} /> : <Icon name="calculator" size={18} />}
            {saving ? 'Считаем…' : 'Рассчитать рекомендации'}
          </button>
        </div>
      </Card>

      {message && <Notice tone={message.tone} role="status">{message.text}</Notice>}

      <div className="grid-2">
        <Card>
          <CardHeader icon="settings" title="Параметры расчёта" subtitle="Изменения применяются при следующем расчёте." />
          <div className="card-body">
            {settings ? (
              <div className="stack-sm">
                <div className="grid-2" style={{ gap: 12 }}>
                  <div className="field"><label htmlFor="warehouse">Склад</label><select id="warehouse" className="input" disabled><option>{header.warehouse.name}</option></select></div>
                  <div className="field"><label htmlFor="category">Категория</label><select id="category" className="input" value={settings.category_filter || ''} onChange={event => setSettings({ ...settings, category_filter: event.target.value || null })}>{settings.category_options.map(option => <option key={option.value || 'all'} value={option.value || ''}>{option.label}</option>)}</select></div>
                  <div className="field"><label htmlFor="calc-date">Дата расчёта</label><input id="calc-date" className="input" type="date" min={settings.calc_date_min} max={settings.calc_date_max} value={settings.calc_date} onChange={event => setSettings({ ...settings, calc_date: event.target.value })} /></div>
                  <div className="field"><label htmlFor="excess">Избыточный запас, мес. спроса</label><input id="excess" className="input" type="number" min="0.5" step="0.5" value={settings.excess_months} onChange={event => setSettings({ ...settings, excess_months: Number(event.target.value) })} /></div>
                </div>
                <div className="table-wrap" style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', marginTop: 6 }}>
                  <table className="table table-compact">
                    <thead><tr><th>Поставщик</th><th>Срок поставки, дн.</th><th>Пересмотр, дн.</th><th>Горизонт</th></tr></thead>
                    <tbody>
                      {settings.suppliers.map(supplier => (
                        <tr key={supplier.id}>
                          <td className="cell-primary">{supplier.name}</td>
                          <td><input className="input input-compact" aria-label={`Срок поставки ${supplier.name}`} type="number" min="1" value={supplier.lead_time_days} onChange={event => updateSupplier(supplier.id, 'lead_time_days', Number(event.target.value))} /></td>
                          <td><input className="input input-compact" aria-label={`Период пересмотра ${supplier.name}`} type="number" min="1" value={supplier.review_days} onChange={event => updateSupplier(supplier.id, 'review_days', Number(event.target.value))} /></td>
                          <td><Badge tone="neutral">{supplier.horizon_days} дн.</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="tiny">Сроки поставки и пересмотра партнёр не передал: это предположения до согласования.</p>
              </div>
            ) : <Loading text="Загружаем настройки…" />}
          </div>
        </Card>

        <div className="stack">
          <Card>
            <CardHeader icon="check-circle" title="Что можно рассчитать" subtitle="«0» — продаж не было, «нужны данные» — позиции не было в выгрузке." />
            <div className="table-wrap">
              <table className="table table-compact">
                <thead><tr><th>Поставщик</th><th className="numeric">Рассчитано</th><th className="numeric">Нужны данные</th><th className="numeric">Мало истории</th></tr></thead>
                <tbody>
                  {overview?.readiness.map(item => <tr key={item.supplier.id}><td className="cell-primary">{item.supplier.name}</td><td className="numeric"><span style={{ color: 'var(--success-700)', fontWeight: 600 }}>{formatInt(item.calculated)}</span></td><td className="numeric"><span style={{ color: 'var(--warning-700)' }}>{formatInt(item.needs_data)}</span></td><td className="numeric muted">{formatInt(item.insufficient_history)}</td></tr>)}
                  {overview?.readiness.length === 0 && <tr><td colSpan={4} className="muted">Запустите расчёт, чтобы увидеть готовность.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
          <Card>
            <CardHeader icon="layers" title="Типы документов" subtitle="Правило возврата задаётся на сервере и учитывается при расчёте спроса." />
            <div className="table-wrap">
              <table className="table table-compact"><thead><tr><th>Тип</th><th>Правило</th></tr></thead><tbody>{overview?.document_rules.map(rule => <tr key={rule.doc_type}><td className="cell-primary">{rule.doc_type}</td><td className="muted" style={{ whiteSpace: 'normal' }}>{rule.rule_text}</td></tr>)}</tbody></table>
            </div>
          </Card>
        </div>
      </div>

      {/* После успешного импорта бэкенд сбрасывает расчёт и версии: обновляем и шапку, и сводку. */}
      <ImportPanel imports={overview?.imports} onDataReplaced={replaced => { onReset(replaced); getDataOverview().then(data => { setOverview(data); setSettings(data.settings) }).catch(() => undefined) }} />

      <Card>
        <CardHeader icon="database" title="Источники данных" subtitle="Файлы разбираются на сервере. Статус — по фактическому ответу API." actions={overview && <Badge tone="neutral">{overview.sources.length} файлов</Badge>} />
        {overview ? (
          overview.sources.length ? (
            <div className="table-wrap">
              <table className="table" style={{ minWidth: 760 }}>
                <thead><tr><th>Поставщик</th><th>Файл</th><th>Актуальность</th><th className="numeric">Объём</th><th>Статус</th></tr></thead>
                <tbody>
                  {overview.sources.map(source => (
                    <tr key={source.key}>
                      <td><Badge tone="outline">{supplierName(source.supplier.id)}</Badge></td>
                      <td><div className="cell-primary">{source.file?.name || source.type_text}</div>{source.usage_text && <div className="cell-secondary">{source.usage_text}</div>}</td>
                      <td className="muted">{source.freshness_text || '—'}</td>
                      <td className="numeric muted">{source.volume_text || '—'}</td>
                      <td>{source.file?.status_text ? <Badge tone={source.file.status_text === 'применён' ? 'success' : 'warning'} icon={source.file.status_text === 'применён' ? 'check' : 'alert'}>{source.file.status_text}</Badge> : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="card-body"><EmptyState icon="database" title="Файлы не найдены">Расчёт использует текущий набор данных сервера.</EmptyState></div>
        ) : <Loading />}
      </Card>

      <div className="grid-2">
        <Card>
          <CardHeader icon="info" title={<>Предположения в расчёте {overview && <Badge tone="neutral">{overview.assumptions.length}</Badge>}</>} />
          <div className="table-wrap">
            <table className="table table-compact">
              <thead><tr><th>Параметр</th><th>Значение и источник</th><th>Тип</th></tr></thead>
              <tbody>{overview?.assumptions.map(item => <tr key={item.label}><td className="cell-primary">{item.label}</td><td className="muted" style={{ whiteSpace: 'normal' }}>{item.value_text}</td><td><Badge tone={ORIGIN[item.origin].tone}>{ORIGIN[item.origin].label}</Badge></td></tr>)}</tbody>
            </table>
          </div>
        </Card>
        <Card>
          <CardHeader icon="alert" title={<>Проблемы данных {overview && <Badge tone={overview.issues.length ? 'warning' : 'success'}>{overview.issues.length}</Badge>}</>} />
          {overview && overview.issues.length === 0
            ? <div className="card-body"><Notice tone="success">Критичных проблем в данных не найдено. Позиции без кода 1С или истории помечены статусом «нужны данные».</Notice></div>
            : <div className="table-wrap"><table className="table table-compact"><thead><tr><th>Проверка</th><th>Проблема</th></tr></thead><tbody>{overview?.issues.map((issue, index) => <tr key={index}><td className="cell-primary">{issue.label || '—'}</td><td className="muted" style={{ whiteSpace: 'normal' }}>{issue.text || '—'}</td></tr>)}</tbody></table></div>}
        </Card>
      </div>
      {overview && overview.matching.length > 0 && (
        <Card>
          <CardHeader icon="check" title="Сопоставление по коду 1С" />
          <div className="table-wrap"><table className="table table-compact"><thead><tr><th>Проверка</th><th className="numeric">Сопоставлено</th></tr></thead><tbody>{overview.matching.map((item, index) => <tr key={index}><td>{item.label || '—'}</td><td className="numeric">{item.value_text || '—'}</td></tr>)}</tbody></table></div>
        </Card>
      )}
    </div>
  )
}
