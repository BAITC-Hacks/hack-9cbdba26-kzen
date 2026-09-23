import { useEffect, useState } from 'react'
import type { AppHeader, DataOverview } from '../types'
import { getDataOverview, resetSession, saveSettings } from '../api/client'

interface Props { header: AppHeader; onCalculate: () => Promise<void>; onReset: (header: AppHeader) => void }

function Corners() {
  return <><i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" /></>
}

export default function DataScreen({ header, onCalculate, onReset }: Props) {
  const [overview, setOverview] = useState<DataOverview | null>(null)
  const [settings, setSettings] = useState<DataOverview['settings'] | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    getDataOverview().then(data => { setOverview(data); setSettings(data.settings) }).catch(error => setMessage(String(error)))
  }, [])

  async function calculate() {
    if (!settings) return
    setSaving(true)
    setMessage('')
    try {
      await saveSettings({ category_filter: settings.category_filter, calc_date: settings.calc_date, suppliers: settings.suppliers.map(({ id, lead_time_days, review_days }) => ({ id, lead_time_days, review_days })), excess_months: settings.excess_months })
      await onCalculate()
    } catch (error) { setMessage(`Не удалось выполнить расчёт: ${String(error)}`) }
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
      setMessage('Сессия сброшена')
    } catch (error) { setMessage(`Не удалось сбросить сессию: ${String(error)}`) }
    finally { setSaving(false) }
  }

  function updateSupplier(id: string, field: 'lead_time_days' | 'review_days', value: number) {
    setSettings(current => current && ({ ...current, suppliers: current.suppliers.map(supplier => supplier.id === id ? { ...supplier, [field]: value, horizon_days: field === 'lead_time_days' ? value + supplier.review_days : supplier.lead_time_days + value } : supplier) }))
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Данные и параметры</h1>
          <p className="page-subtitle">Выгрузки, их актуальность, проверки качества и настройки расчёта. Позиции с проблемами остаются в расчёте со статусом «нужны данные».</p>
        </div>
        <div className="inline-actions">
          <button className="btn btn-ghost" type="button" onClick={reset} disabled={saving}>Сбросить сессию</button>
          <button className="btn btn-primary blueprint" type="button" onClick={calculate} disabled={saving || !settings}><Corners />{saving ? 'Расчёт…' : 'Рассчитать рекомендации'}</button>
        </div>
      </header>

      {message && <div className="notice" role="status">{message}</div>}
      <section className="page-section">
        <h2 className="section-heading">Источники</h2>
        <div className="scroll-table">
          <table className="table" style={{ minWidth: 850 }}>
            <thead><tr><th>Поставщик</th><th>Источник</th><th>Актуальность</th><th className="numeric">Объём (реальный)</th><th>Загруженный файл</th></tr></thead>
            <tbody>
              {overview?.sources.map(source => (
                <tr key={source.key}>
                  <td><span className="tag tag-neutral">{source.supplier.id === 'SE' ? 'Systeme Electric' : 'ИЭК'}</span></td>
                  <td>{source.type_text}<div className="tiny">{source.usage_text}</div></td>
                  <td>{source.freshness_text || '—'}</td>
                  <td className="numeric">{source.volume_text || '—'}</td>
                  <td className="tiny">{source.file?.name || '—'} {source.file?.status_text && <span className="tag tag-outline">{source.file.status_text}</span>}</td>
                </tr>
              ))}
              {overview && overview.sources.length === 0 && <tr><td colSpan={5} className="muted">Файлы пока не найдены. Расчёт использует текущий набор данных сервера.</td></tr>}
            </tbody>
          </table>
        </div>
        <p className="tiny" style={{ marginTop: 10 }}>Данные загружаются и разбираются на сервере. Статус источника показан по фактическому ответу API.</p>
      </section>

      <div className="data-three-column page-section">
        <section className="blueprint panel"><Corners />
          <h2 className="card-title">Параметры расчёта</h2>
          {settings ? <>
            <div className="field-grid" style={{ marginTop: 14 }}>
              <div className="field"><label htmlFor="warehouse">Склад</label><select id="warehouse" className="input" disabled><option>{header.warehouse.name}</option></select></div>
              <div className="field"><label htmlFor="category">Категория</label><select id="category" className="input" value={settings.category_filter || ''} onChange={event => setSettings({ ...settings, category_filter: event.target.value || null })}>{settings.category_options.map(option => <option key={option.value || 'all'} value={option.value || ''}>{option.label}</option>)}</select></div>
              <div className="field"><label htmlFor="calc-date">Дата расчёта</label><input id="calc-date" className="input" type="date" min={settings.calc_date_min} max={settings.calc_date_max} value={settings.calc_date} onChange={event => setSettings({ ...settings, calc_date: event.target.value })} /></div>
              <div className="field"><label htmlFor="excess">Избыточный запас, мес. спроса</label><input id="excess" className="input" type="number" min="0.5" step="0.5" value={settings.excess_months} onChange={event => setSettings({ ...settings, excess_months: Number(event.target.value) })} /></div>
            </div>
            <div className="scroll-table" style={{ marginTop: 18 }}><table className="table"><thead><tr><th>Поставщик</th><th>L, дн.</th><th>R, дн.</th><th>H</th></tr></thead><tbody>{settings.suppliers.map(supplier => <tr key={supplier.id}><td>{supplier.name}</td><td><input className="input" aria-label={`Срок поставки ${supplier.name}`} type="number" min="1" style={{ width: 76 }} value={supplier.lead_time_days} onChange={event => updateSupplier(supplier.id, 'lead_time_days', Number(event.target.value))} /></td><td><input className="input" aria-label={`Период пересмотра ${supplier.name}`} type="number" min="1" style={{ width: 76 }} value={supplier.review_days} onChange={event => updateSupplier(supplier.id, 'review_days', Number(event.target.value))} /></td><td>{supplier.horizon_days} дн.</td></tr>)}</tbody></table></div>
            <p className="tiny" style={{ marginTop: 10 }}>L и R не переданы партнёром: значения — предположения до согласования.</p>
          </> : <p className="muted" style={{ marginTop: 12 }}>Загрузка настроек…</p>}
        </section>
        <section className="blueprint panel"><Corners />
          <h2 className="card-title">Правила по категориям</h2>
          <div className="scroll-table" style={{ marginTop: 14 }}><table className="table"><thead><tr><th>Категория</th><th>Страховой запас, дн.</th><th>Сезонность на H</th></tr></thead><tbody><tr><td colSpan={3} className="muted">Правила категорий пока задаются в расчётном ядре и не меняются через API.</td></tr></tbody></table></div>
          <p className="tiny" style={{ marginTop: 12 }}>Пустая сезонность в прототипе означает коэффициент бренда или SKU.</p>
        </section>
        <section className="blueprint panel"><Corners />
          <h2 className="card-title">Типы документов</h2>
          <div className="scroll-table" style={{ marginTop: 14 }}><table className="table"><thead><tr><th>Тип</th><th>Правило</th></tr></thead><tbody>{overview?.document_rules.map(rule => <tr key={rule.doc_type}><td>{rule.doc_type}</td><td>{rule.rule_text}</td></tr>)}</tbody></table></div>
          <p className="tiny" style={{ marginTop: 12 }}>Правило возврата задаётся на сервере и учитывается при расчёте спроса.</p>
        </section>
      </div>

      <div className="data-two-column page-section">
        <section>
          <h2 className="section-heading">Сопоставление по коду 1С</h2>
          <div className="scroll-table"><table className="table"><thead><tr><th>Проверка</th><th className="numeric">Сопоставлено</th><th>Данные</th></tr></thead><tbody>{overview?.matching.map((item, index) => <tr key={index}><td>{item.label || '—'}</td><td className="numeric">{item.value_text || '—'}</td><td>—</td></tr>)}{overview && overview.matching.length === 0 && <tr><td colSpan={3} className="muted">Сводка сопоставления пока не передана API.</td></tr>}</tbody></table></div>
        </section>
        <section>
          <h2 className="section-heading">Что можно рассчитать</h2>
          <div className="scroll-table"><table className="table"><thead><tr><th>Поставщик</th><th className="numeric">Рассчитано</th><th className="numeric">Нужны данные</th><th className="numeric">Мало истории</th></tr></thead><tbody>{overview?.readiness.map(item => <tr key={item.supplier.id}><td>{item.supplier.name}</td><td className="numeric">{item.calculated}</td><td className="numeric">{item.needs_data}</td><td className="numeric">{item.insufficient_history}</td></tr>)}{overview?.readiness.length === 0 && <tr><td colSpan={4} className="muted">Запустите расчёт, чтобы увидеть готовность.</td></tr>}</tbody></table></div>
          <p className="tiny" style={{ marginTop: 10 }}>Ноль продаж, отсутствие данных и неполный период различаются: «0» — продаж не было, «н/д» — позиции не было в выгрузке.</p>
        </section>
      </div>

      <section className="page-section">
        <h2 className="section-heading">Предположения в расчёте {overview?.assumptions.length ?? ''}</h2>
        <div className="scroll-table"><table className="table"><thead><tr><th>Параметр</th><th>Значение и источник</th><th>Тип</th></tr></thead><tbody>{overview?.assumptions.map(item => <tr key={item.label}><td>{item.label}</td><td>{item.value_text}</td><td><span className="tag tag-outline">{item.origin === 'synthetic' ? 'синтетика' : item.origin === 'real' ? 'реальные данные' : 'допущение'}</span></td></tr>)}</tbody></table></div>
      </section>
      <section className="page-section"><h2 className="section-heading">Проблемы данных <span className="tiny">{overview?.issues.length ?? 0}</span></h2><div className="scroll-table"><table className="table"><thead><tr><th>Источник</th><th>Проверка</th><th>Проблема</th><th>Как учитывается в расчёте</th></tr></thead><tbody>{overview?.issues.map((issue, index) => <tr key={index}><td>—</td><td>{issue.label || '—'}</td><td>{issue.text || '—'}</td><td>—</td></tr>)}{overview && overview.issues.length === 0 && <tr><td colSpan={4} className="muted">Проблемы данных в ответе API не указаны.</td></tr>}</tbody></table></div></section>
    </div>
  )
}
