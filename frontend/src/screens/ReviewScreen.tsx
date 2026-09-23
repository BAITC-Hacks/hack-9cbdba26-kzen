import { useEffect, useState } from 'react'
import type { AppHeader, OrderCurrent, Role } from '../types'
import { exportOrder, getAuditLog, getOrderCurrent, getOrderVersions, getVersionDiff, orderAction, saveExportSettings, setRole } from '../api/client'
import Icon from '../components/ui/Icon'
import { formatInt } from '../components/ui/format'
import { Badge, Card, CardHeader, EmptyState, Loading, Notice } from '../components/ui'

type Version = { version: number; approved_at: string; approved_by_text: string; lines: number }
type Audit = { version: number; text: string; user_text: string; at: string }
type Diff = { title_text: string; rows: Array<{ code_1c: string; name: string; in_version_text: string; current_text: string }> }
type Message = { tone: 'info' | 'danger' | 'success'; text: string }

const WORKFLOW: Array<{ key: OrderCurrent['status']; label: string }> = [
  { key: 'draft', label: 'Черновик' },
  { key: 'submitted', label: 'На согласовании' },
  { key: 'approved', label: 'Утверждён' },
]

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
  const [message, setMessage] = useState<Message | null>(null)

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
      .catch(cause => setMessage({ tone: 'danger', text: String(cause) }))
  }, [onHeaderChange])

  async function changeAuditPage(nextPage: number) {
    setAuditBusy(true)
    setMessage(null)
    try {
      const log = await getAuditLog(nextPage)
      setAudit(log.items)
      setAuditPage(log.page)
      setAuditPages(log.pages)
      setAuditTotal(log.total)
    } catch (cause) { setMessage({ tone: 'danger', text: `Не удалось загрузить журнал: ${String(cause)}` }) }
    finally { setAuditBusy(false) }
  }

  async function switchRole(next: Role) {
    setBusy(true)
    setMessage(null)
    try {
      const result = await setRole(next)
      setCurrentRole(next)
      onHeaderChange?.(result.header)
    } catch (cause) {
      setMessage({ tone: 'danger', text: `Не удалось сменить роль: ${String(cause)}` })
      setBusy(false)
      return
    }
    try { await refresh() }
    catch (cause) { setMessage({ tone: 'danger', text: `Роль изменена, но не удалось обновить заказ: ${String(cause)}` }) }
    finally { setBusy(false) }
  }

  async function act(action: 'submit' | 'approve' | 'reject') {
    if (!data) return
    setBusy(true)
    setMessage(null)
    try {
      const result = await orderAction({ action, order_version: data.version, order_revision: data.revision, ...(action === 'reject' ? { comment } : {}) })
      onHeaderChange?.(result.header)
      setData(result.order)
      setComment('')
    } catch (cause) {
      setMessage({ tone: 'danger', text: `Действие не выполнено: ${String(cause)}` })
      setBusy(false)
      return
    }
    try {
      await refresh()
      setMessage({ tone: 'success', text: action === 'submit' ? 'Версия отправлена на согласование' : action === 'approve' ? 'Заказ утверждён. Теперь его можно выгрузить для 1С.' : 'Версия возвращена на доработку' })
    } catch (cause) { setMessage({ tone: 'danger', text: `Заказ изменён, но не удалось обновить журнал: ${String(cause)}` }) }
    finally { setBusy(false) }
  }

  async function updateExport(patch: Partial<OrderCurrent['export_settings']>) {
    if (!data) return
    const next = { ...data.export_settings, ...patch }
    setData({ ...data, export_settings: next })
    try { const result = await saveExportSettings({ format: next.format, separator: next.separator, encoding: next.encoding, columns: next.columns.map(({ key, enabled }) => ({ key, enabled })) }); setData(result.order) }
    catch (cause) { setData(data); setMessage({ tone: 'danger', text: `Не удалось сохранить настройки экспорта: ${String(cause)}` }) }
  }

  async function download(supplierId?: string) {
    setBusy(true)
    setMessage(null)
    try { await exportOrder(supplierId) }
    catch (cause) { setMessage({ tone: 'danger', text: `Не удалось выгрузить заказ: ${String(cause)}` }) }
    finally { setBusy(false) }
  }

  if (!data) return (
    <div className="page">
      <h1>Согласование и выгрузка</h1>
      {message ? <Notice tone={message.tone} role="alert">{message.text}</Notice> : <Loading text="Загружаем заказ…" />}
    </div>
  )

  const currentIndex = WORKFLOW.findIndex(step => step.key === data.status)
  const statusTone = data.status === 'approved' ? 'success' : data.status === 'submitted' ? 'warning' : 'neutral'
  const totalLines = data.groups.reduce((sum, group) => sum + group.lines.length, 0)

  return (
    <div className="page stack">
      <header className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Согласование и выгрузка</h1>
          <p className="page-subtitle">Менеджер проверяет количества и отправляет версию руководителю. После утверждения заказ выгружается в файл для 1С. Поставщику сервис ничего не отправляет.</p>
        </div>
        <Badge tone={statusTone} icon={data.status === 'approved' ? 'check' : data.status === 'submitted' ? 'clock' : 'edit'}>{data.status_text}</Badge>
      </header>

      {message && <Notice tone={message.tone} role="status">{message.text}</Notice>}

      <Card>
        <div className="card-body">
          <div className="row-between" style={{ alignItems: 'flex-start' }}>
            <div className="stack-sm">
              <div className="stepper" aria-label="Статус согласования">
                {WORKFLOW.map((step, index) => (
                  <span key={step.key} className="row" style={{ gap: 0 }}>
                    {index > 0 && <span className="step-line" />}
                    <span className={`step${index < currentIndex ? ' is-done' : index === currentIndex ? ' is-current' : ''}`}>
                      <span className="step-dot">{index < currentIndex ? <Icon name="check" size={12} /> : index + 1}</span>
                      {step.label}
                    </span>
                  </span>
                ))}
              </div>
              <p className="muted">{data.hint_text}</p>
            </div>
            <div className="row">
              <span className="tiny">Смотреть как</span>
              <div className="seg" role="radiogroup" aria-label="Роль">
                <div className="seg-opt"><input type="radio" name="review-role" id="manager-role" checked={role === 'manager'} onChange={() => void switchRole('manager')} disabled={busy} /><label htmlFor="manager-role">Менеджер</label></div>
                <div className="seg-opt"><input type="radio" name="review-role" id="head-role" checked={role === 'head'} onChange={() => void switchRole('head')} disabled={busy} /><label htmlFor="head-role">Руководитель</label></div>
              </div>
            </div>
          </div>
          {data.blocked_reason_text && <Notice tone="warning" role="status">{data.blocked_reason_text}</Notice>}
        </div>
        <div className="card-footer">
          <div className="row" style={{ gap: 10, alignItems: 'flex-end' }}>
            {data.permissions.can_submit && <button className="btn btn-primary" type="button" onClick={() => void act('submit')} disabled={busy}><Icon name="send" />Отправить на согласование</button>}
            {data.permissions.can_approve && <button className="btn btn-success" type="button" onClick={() => void act('approve')} disabled={busy}><Icon name="check" />Утвердить версию v{data.version}</button>}
            {data.permissions.can_reject && (
              <>
                <div className="field" style={{ width: 320 }}>
                  <label htmlFor="reject-comment">Комментарий к возврату</label>
                  <input id="reject-comment" className="input" value={comment} onChange={event => setComment(event.target.value)} placeholder="Что нужно исправить" />
                </div>
                <button className="btn btn-danger" type="button" onClick={() => void act('reject')} disabled={busy}><Icon name="arrow-left" />Вернуть на доработку</button>
              </>
            )}
            {data.permissions.can_export && <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void download()}><Icon name="download" />Скачать файл для 1С</button>}
            {!data.permissions.can_submit && !data.permissions.can_approve && !data.permissions.can_reject && !data.permissions.can_export && <span className="tiny">В этой роли действий по текущей версии нет.</span>}
            {data.status === 'approved' && <span className="tiny">Отправка поставщику выполняется вне системы.</span>}
          </div>
        </div>
      </Card>

      <div className="section-head" style={{ marginBottom: 0 }}>
        <h2>Состав заказа <Badge tone="neutral">{formatInt(totalLines)} строк</Badge></h2>
      </div>
      {data.groups.map(group => (
        <Card key={group.supplier.id}>
          <div className="group-header">
            <div>
              <div className="group-title"><h2>{group.supplier.name}</h2></div>
              <p className="tiny">{group.summary_text} · {group.cost_text}</p>
            </div>
            <button type="button" className="btn btn-secondary btn-sm" disabled={!data.permissions.can_export || busy} onClick={() => void download(group.supplier.id)} title={data.permissions.can_export ? undefined : 'Выгрузка доступна после утверждения'}><Icon name="download" size={14} />Выгрузить {group.supplier.name}</button>
          </div>
          {group.pending_text && <div style={{ padding: '12px 20px 0' }}><Notice tone="warning">{group.pending_text}</Notice></div>}
          {group.lines.length ? (
            <div className="table-wrap" style={{ marginTop: group.pending_text ? 12 : 0 }}>
              <table className="table" style={{ minWidth: 880 }}>
                <thead><tr><th>Код 1С</th><th style={{ minWidth: 240 }}>Наименование</th><th>Ед.</th><th className="numeric">Рекомендовано</th><th className="numeric">Итог</th><th className="numeric">Цена</th><th className="numeric">Сумма</th><th>Причина изменения</th></tr></thead>
                <tbody>
                  {group.lines.map(line => (
                    <tr key={line.sku_id}>
                      <td><code className="mono">{line.code_1c}</code></td>
                      <td className="cell-primary">{line.name}</td>
                      <td className="muted">{line.purchase_unit}</td>
                      <td className="numeric muted">{formatInt(line.recommended_qty)}</td>
                      <td className="numeric"><span className="qty-strong">{formatInt(line.final_qty)}</span>{line.manual && <div><Badge tone="outline" icon="edit">вручную</Badge></div>}</td>
                      <td className="numeric muted">{formatInt(line.price)}</td>
                      <td className="numeric">{formatInt(line.cost)}</td>
                      <td className="cell-secondary" style={{ whiteSpace: 'normal' }}>{line.reason || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="card-body"><EmptyState icon="package" title="Строк к заказу нет" /></div>}
        </Card>
      ))}

      <Card>
        <CardHeader icon="download" title="Настройки файла для 1С" subtitle={data.export_settings.note_text} />
        <div className="card-body stack-sm">
          <div className="row" style={{ gap: 12 }}>
            <div className="field" style={{ width: 140 }}><label htmlFor="export-format">Формат</label><select id="export-format" className="input" value={data.export_settings.format} onChange={event => void updateExport({ format: event.target.value as 'csv' | 'xlsx' })}>{data.export_settings.format_options.map(option => <option key={option} value={option}>{option.toUpperCase()}</option>)}</select></div>
            <div className="field" style={{ width: 160 }}><label htmlFor="export-separator">Разделитель CSV</label><select id="export-separator" className="input" value={data.export_settings.separator} onChange={event => void updateExport({ separator: event.target.value })}>{data.export_settings.separator_options.map(option => <option key={option} value={option}>{option}</option>)}</select></div>
            <div className="field" style={{ width: 180 }}><label htmlFor="export-encoding">Кодировка CSV</label><select id="export-encoding" className="input" value={data.export_settings.encoding} onChange={event => void updateExport({ encoding: event.target.value })}>{data.export_settings.encoding_options.map(option => <option key={option} value={option}>{option}</option>)}</select></div>
          </div>
          <div>
            <div className="field-label" style={{ marginBottom: 8 }}>Колонки в файле</div>
            <div className="row" style={{ gap: 6 }}>
              {data.export_settings.columns.map(column => (
                <label key={column.key} className="checkbox">
                  <input type="checkbox" checked={column.enabled} onChange={() => void updateExport({ columns: data.export_settings.columns.map(item => item.key === column.key ? { ...item, enabled: !item.enabled } : item) })} />
                  {column.label}
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="card-footer row">
          <button type="button" className="btn btn-primary" disabled={!data.permissions.can_export || busy} onClick={() => void download()}><Icon name="download" />Скачать утверждённый заказ</button>
          {!data.permissions.can_export && <span className="tiny">Файл доступен после утверждения руководителем.</span>}
        </div>
      </Card>

      <div className="grid-2">
        <Card>
          <CardHeader icon="layers" title="Утверждённые версии" />
          {versions.length ? (
            <div className="table-wrap">
              <table className="table table-compact">
                <thead><tr><th>Версия</th><th>Утверждена</th><th>Кем</th><th className="numeric">Строк</th><th /></tr></thead>
                <tbody>{versions.map(version => <tr key={version.version}><td className="cell-primary">v{version.version}</td><td className="muted">{version.approved_at}</td><td>{version.approved_by_text}</td><td className="numeric">{formatInt(version.lines)}</td><td><button className="btn btn-ghost btn-sm" onClick={() => void getVersionDiff(version.version).then(setDiff).catch(cause => setMessage({ tone: 'danger', text: String(cause) }))}>Сравнить</button></td></tr>)}</tbody>
              </table>
            </div>
          ) : <div className="card-body"><EmptyState icon="layers" title="Утверждённых версий пока нет">Первая появится после утверждения руководителем.</EmptyState></div>}
          {diff && (
            <div className="card-body" style={{ borderTop: '1px solid var(--color-border)' }}>
              <div className="row-between" style={{ marginBottom: 8 }}><h3>{diff.title_text}</h3><button className="btn btn-ghost btn-sm" onClick={() => setDiff(null)}><Icon name="x" size={14} />Закрыть</button></div>
              {diff.rows.length ? <div className="table-wrap"><table className="table table-compact"><thead><tr><th>Код 1С</th><th>Наименование</th><th>В версии</th><th>Сейчас</th></tr></thead><tbody>{diff.rows.map(row => <tr key={row.code_1c}><td><code className="mono">{row.code_1c}</code></td><td>{row.name}</td><td className="muted">{row.in_version_text}</td><td className="cell-primary">{row.current_text}</td></tr>)}</tbody></table></div> : <p className="muted">Различий нет.</p>}
            </div>
          )}
        </Card>
        <Card>
          <CardHeader icon="history" title="Журнал изменений" actions={auditTotal > 0 && <Badge tone="neutral">{formatInt(auditTotal)}</Badge>} />
          {audit.length ? (
            <div className="table-wrap">
              <table className="table table-compact">
                <thead><tr><th>Время</th><th>Версия</th><th>Действие</th><th>Кто</th></tr></thead>
                <tbody>{audit.map((entry, index) => <tr key={`${entry.version}-${entry.at}-${index}`}><td className="cell-secondary">{entry.at}</td><td>v{entry.version}</td><td style={{ whiteSpace: 'normal' }}>{entry.text}</td><td className="muted">{entry.user_text}</td></tr>)}</tbody>
              </table>
            </div>
          ) : <div className="card-body"><EmptyState icon="history" title="Записей пока нет" /></div>}
          {auditPages > 1 && (
            <div className="card-footer row-between">
              <span className="tiny">Страница {auditPage} из {auditPages}</span>
              <div className="row">
                <button className="btn btn-ghost btn-sm" type="button" onClick={() => void changeAuditPage(auditPage - 1)} disabled={auditBusy || busy || auditPage <= 1}><Icon name="chevron-left" size={14} />Назад</button>
                <button className="btn btn-ghost btn-sm" type="button" onClick={() => void changeAuditPage(auditPage + 1)} disabled={auditBusy || busy || auditPage >= auditPages}>Далее<Icon name="chevron-right" size={14} /></button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
