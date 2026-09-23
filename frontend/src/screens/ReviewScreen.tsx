import { useEffect, useState } from 'react'
import type { AppHeader, OrderCurrent, Role } from '../types'
import { exportOrder, getAuditLog, getOrderCurrent, getOrderVersions, getVersionDiff, orderAction, saveExportSettings, setRole } from '../api/client'

type Version = { version: number; approved_at: string; approved_by_text: string; lines: number }
type Audit = { version: number; text: string; user_text: string; at: string }
type Diff = { title_text: string; rows: Array<{ code_1c: string; name: string; in_version_text: string; current_text: string }> }

const format = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('ru-RU').format(value)

export default function ReviewScreen({ onHeaderChange }: { onHeaderChange?: (header: AppHeader) => void }) {
  const [data, setData] = useState<OrderCurrent | null>(null)
  const [role, setCurrentRole] = useState<Role>('manager')
  const [versions, setVersions] = useState<Version[]>([])
  const [audit, setAudit] = useState<Audit[]>([])
  const [auditPage, setAuditPage] = useState(1)
  const [auditPages, setAuditPages] = useState(1)
  const [auditTotal, setAuditTotal] = useState(0)
  const [auditBusy, setAuditBusy] = useState(false)
  const [diff, setDiff] = useState<Diff | null>(null)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function refresh() {
    const [order, savedVersions, log] = await Promise.all([getOrderCurrent(), getOrderVersions(), getAuditLog(1)])
    setData(order)
    setCurrentRole(order.header.role)
    onHeaderChange?.(order.header)
    setVersions(savedVersions)
    setAudit(log.items)
    setAuditPage(log.page)
    setAuditPages(log.pages)
    setAuditTotal(log.total)
  }

  useEffect(() => {
    Promise.all([getOrderCurrent(), getOrderVersions(), getAuditLog(1)])
      .then(([order, savedVersions, log]) => {
        setData(order)
        setCurrentRole(order.header.role)
        onHeaderChange?.(order.header)
        setVersions(savedVersions)
        setAudit(log.items)
        setAuditPage(log.page)
        setAuditPages(log.pages)
        setAuditTotal(log.total)
      })
      .catch(cause => setMessage(String(cause)))
  }, [onHeaderChange])

  async function changeAuditPage(nextPage: number) {
    setAuditBusy(true)
    setMessage('')
    try {
      const log = await getAuditLog(nextPage)
      setAudit(log.items)
      setAuditPage(log.page)
      setAuditPages(log.pages)
      setAuditTotal(log.total)
    } catch (cause) { setMessage(`Не удалось загрузить журнал: ${String(cause)}`) }
    finally { setAuditBusy(false) }
  }

  async function switchRole(next: Role) {
    setBusy(true)
    setMessage('')
    try {
      const result = await setRole(next)
      setCurrentRole(next)
      onHeaderChange?.(result.header)
    } catch (cause) {
      setMessage(`Не удалось сменить роль: ${String(cause)}`)
      setBusy(false)
      return
    }
    try { await refresh() }
    catch (cause) { setMessage(`Роль изменена, но не удалось обновить заказ: ${String(cause)}`) }
    finally { setBusy(false) }
  }

  async function act(action: 'submit' | 'approve' | 'reject') {
    if (!data) return
    setBusy(true)
    setMessage('')
    try {
      const result = await orderAction({ action, order_version: data.version, order_revision: data.revision, ...(action === 'reject' ? { comment } : {}) })
      onHeaderChange?.(result.header)
      setData(result.order)
      setComment('')
    } catch (cause) {
      setMessage(`Действие не выполнено: ${String(cause)}`)
      setBusy(false)
      return
    }
    try {
      await refresh()
      setMessage(action === 'submit' ? 'Отправлено на согласование' : action === 'approve' ? 'Заказ утверждён' : 'Возвращено на доработку')
    } catch (cause) { setMessage(`Заказ изменён, но не удалось обновить журнал: ${String(cause)}`) }
    finally { setBusy(false) }
  }

  async function updateExport(patch: Partial<OrderCurrent['export_settings']>) {
    if (!data) return
    const next = { ...data.export_settings, ...patch }
    setData({ ...data, export_settings: next })
    try { const result = await saveExportSettings({ format: next.format, separator: next.separator, encoding: next.encoding, columns: next.columns.map(({ key, enabled }) => ({ key, enabled })) }); setData(result.order) }
    catch (cause) { setData(data); setMessage(`Не удалось сохранить настройки экспорта: ${String(cause)}`) }
  }

  async function download(supplierId?: string) {
    setBusy(true)
    setMessage('')
    try { await exportOrder(supplierId) }
    catch (cause) { setMessage(`Не удалось выгрузить заказ: ${String(cause)}`) }
    finally { setBusy(false) }
  }

  if (!data) return <div className="page"><h1>Проверка и экспорт</h1><p className="page-subtitle">{message || 'Загрузка заказа…'}</p></div>

  return <div className="page">
    <header className="page-head"><div><h1>Проверка и экспорт</h1><p className="page-subtitle">Проверьте количества по поставщикам. Менеджер отправляет версию на согласование, руководитель утверждает или возвращает её.</p></div><span className={`tag ${data.status === 'approved' ? 'tag-accent' : 'tag-outline'}`}>{data.status_text}</span></header>
    {message && <div className="notice" role="status" style={{ marginBottom: 18 }}>{message}</div>}
    <section className="blueprint panel">
      <div className="inline-actions" style={{ justifyContent: 'space-between' }}>
        <div><h2 className="card-title">Согласование версии</h2><p className="tiny" style={{ marginTop: 4 }}>{data.hint_text}</p></div>
        <div className="inline-actions"><span className="tiny">Роль</span><div className="seg"><div className="seg-opt"><input type="radio" name="review-role" id="manager-role" checked={role === 'manager'} onChange={() => void switchRole('manager')} disabled={busy} /><label htmlFor="manager-role">Менеджер</label></div><div className="seg-opt"><input type="radio" name="review-role" id="head-role" checked={role === 'head'} onChange={() => void switchRole('head')} disabled={busy} /><label htmlFor="head-role">Руководитель</label></div></div></div>
      </div>
      <div className="inline-actions" style={{ marginTop: 16 }}>
        {data.permissions.can_submit && <button className="btn btn-primary blueprint" type="button" onClick={() => void act('submit')} disabled={busy}>Отправить на согласование</button>}
        {data.permissions.can_approve && <button className="btn btn-primary blueprint" type="button" onClick={() => void act('approve')} disabled={busy}>Утвердить v{data.version}</button>}
        {data.permissions.can_reject && <button className="btn btn-secondary" type="button" onClick={() => void act('reject')} disabled={busy}>Вернуть на доработку</button>}
        {data.status === 'approved' && <span className="tiny">Экспорт доступен; отправка поставщику выполняется вне системы.</span>}
      </div>
      {data.permissions.can_reject && <div className="field" style={{ maxWidth: 520, marginTop: 12 }}><label htmlFor="reject-comment">Комментарий к возврату</label><input id="reject-comment" className="input" value={comment} onChange={event => setComment(event.target.value)} placeholder="Что нужно исправить" /></div>}
      {data.blocked_reason_text && <div className="notice" style={{ marginTop: 12 }}>{data.blocked_reason_text}</div>}
    </section>

    {data.groups.map(group => <section className="page-section" key={group.supplier.id}>
      <div className="inline-actions" style={{ justifyContent: 'space-between', marginBottom: 10 }}><div><h2>{group.supplier.name}</h2><p className="tiny">{group.summary_text} · {group.cost_text}</p></div><button type="button" className="btn btn-secondary" disabled={!data.permissions.can_export || busy} onClick={() => void download(group.supplier.id)}>Экспортировать {group.supplier.name}</button></div>
      {group.pending_text && <div className="notice" style={{ marginBottom: 10 }}>{group.pending_text}</div>}
      <div className="scroll-table"><table className="table" style={{ minWidth: 880 }}><thead><tr><th>Код 1С</th><th style={{ minWidth: 240 }}>Наименование</th><th>Ед.</th><th className="numeric">Рекомендовано</th><th className="numeric">Итого</th><th className="numeric">Цена</th><th className="numeric">Сумма</th><th>Причина изменения</th></tr></thead><tbody>{group.lines.map(line => <tr key={line.sku_id}><td><code>{line.code_1c}</code></td><td>{line.name}</td><td>{line.purchase_unit}</td><td className="numeric">{format(line.recommended_qty)}</td><td className="numeric"><strong>{format(line.final_qty)}</strong>{line.manual && <span className="tag tag-outline" style={{ marginLeft: 5 }}>ручн.</span>}</td><td className="numeric">{format(line.price)}</td><td className="numeric">{format(line.cost)}</td><td className="tiny">{line.reason || '—'}</td></tr>)}</tbody></table></div>
    </section>)}

    <section className="page-section blueprint panel"><h2 className="card-title">Настройки экспорта</h2><p className="tiny" style={{ marginTop: 4 }}>{data.export_settings.note_text}</p>
      <div className="toolbar" style={{ marginTop: 14 }}><div className="field"><label htmlFor="export-format">Формат</label><select id="export-format" className="input" value={data.export_settings.format} onChange={event => void updateExport({ format: event.target.value as 'csv' | 'xlsx' })}>{data.export_settings.format_options.map(option => <option key={option} value={option}>{option.toUpperCase()}</option>)}</select></div><div className="field"><label htmlFor="export-separator">Разделитель CSV</label><select id="export-separator" className="input" value={data.export_settings.separator} onChange={event => void updateExport({ separator: event.target.value })}>{data.export_settings.separator_options.map(option => <option key={option} value={option}>{option}</option>)}</select></div><div className="field"><label htmlFor="export-encoding">Кодировка CSV</label><select id="export-encoding" className="input" value={data.export_settings.encoding} onChange={event => void updateExport({ encoding: event.target.value })}>{data.export_settings.encoding_options.map(option => <option key={option} value={option}>{option}</option>)}</select></div></div>
      <div className="inline-actions" style={{ marginTop: 14 }}>{data.export_settings.columns.map(column => <label key={column.key} className="tiny" style={{ display: 'flex', alignItems: 'center', gap: 5 }}><input type="checkbox" checked={column.enabled} onChange={() => void updateExport({ columns: data.export_settings.columns.map(item => item.key === column.key ? { ...item, enabled: !item.enabled } : item) })} />{column.label}</label>)}</div>
      <button type="button" className="btn btn-primary blueprint" style={{ marginTop: 18 }} disabled={!data.permissions.can_export || busy} onClick={() => void download()}>Экспортировать утверждённый заказ</button>
    </section>

    <section className="page-section"><h2 className="section-heading">Утверждённые версии</h2>{versions.length ? <div className="scroll-table"><table className="table"><thead><tr><th>Версия</th><th>Утверждена</th><th>Кем</th><th className="numeric">Строк</th><th></th></tr></thead><tbody>{versions.map(version => <tr key={version.version}><td>v{version.version}</td><td>{version.approved_at}</td><td>{version.approved_by_text}</td><td className="numeric">{version.lines}</td><td><button className="btn btn-ghost" onClick={() => void getVersionDiff(version.version).then(setDiff).catch(cause => setMessage(String(cause)))}>Сравнить</button></td></tr>)}</tbody></table></div> : <p className="muted">Утверждённых версий пока нет.</p>}
      {diff && <div className="blueprint panel" style={{ marginTop: 12 }}><div className="inline-actions" style={{ justifyContent: 'space-between' }}><h3 className="card-title">{diff.title_text}</h3><button className="btn btn-ghost" onClick={() => setDiff(null)}>Закрыть</button></div>{diff.rows.length ? <div className="scroll-table"><table className="table"><thead><tr><th>Код 1С</th><th>Наименование</th><th>В версии</th><th>Сейчас</th></tr></thead><tbody>{diff.rows.map(row => <tr key={row.code_1c}><td>{row.code_1c}</td><td>{row.name}</td><td>{row.in_version_text}</td><td>{row.current_text}</td></tr>)}</tbody></table></div> : <p className="muted">Различий нет.</p>}</div>}
    </section>

    <section className="page-section"><h2 className="section-heading">Журнал изменений</h2>{audit.length ? <div className="scroll-table"><table className="table"><thead><tr><th>Время</th><th>Версия</th><th>Действие</th><th>Кто</th></tr></thead><tbody>{audit.map((entry, index) => <tr key={`${entry.version}-${entry.at}-${index}`}><td className="tiny">{entry.at}</td><td>v{entry.version}</td><td>{entry.text}</td><td>{entry.user_text}</td></tr>)}</tbody></table></div> : <p className="muted">Записей пока нет.</p>}
      {auditPages > 1 && <div className="inline-actions" style={{ justifyContent: 'space-between', marginTop: 12 }}><span className="tiny">Страница {auditPage} из {auditPages} · всего {auditTotal}</span><div className="inline-actions"><button className="btn btn-secondary" type="button" onClick={() => void changeAuditPage(auditPage - 1)} disabled={auditBusy || busy || auditPage <= 1}>Назад</button><button className="btn btn-secondary" type="button" onClick={() => void changeAuditPage(auditPage + 1)} disabled={auditBusy || busy || auditPage >= auditPages}>Далее</button></div></div>}
    </section>
  </div>
}
