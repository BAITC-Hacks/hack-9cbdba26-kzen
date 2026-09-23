import { useEffect, useRef, useState } from 'react'
import type { AppHeader, ImportJob, ImportSeverity, ImportSupplier } from '../types'
import { getImport, getSession, listImports, startImport } from '../api/client'

/*
  Панель загрузки выгрузок 1С и история загрузок.
  Самодостаточна: выбор файлов, POST /imports, опрос статуса и отчёт живут здесь,
  чтобы экран «Данные» менялся одной строкой монтирования.
*/

interface Props {
  /* История из data_overview; если экран её не передал, панель запросит GET /imports сама. */
  imports?: ImportJob[]
  /* Вызывается после успешного импорта: бэкенд сбросил расчёт, версии и правки,
     поэтому родитель должен обновить шапку и вернуть приложение в исходное состояние. */
  onDataReplaced: (header: AppHeader) => void
}

const SUPPLIERS: Array<{ value: ImportSupplier; label: string }> = [
  { value: 'IEK', label: 'ИЭК' },
  { value: 'Systeme Electric', label: 'Systeme Electric' },
]

const EXPECTED_FILES = ['ежемесячные продажи', 'ежемесячные остатки', 'динамика продаж', 'MOQ', 'товар в пути', 'сезонность']
const MAX_FILES = 6
const POLL_MS = 1000

const STATUS_TEXT: Record<ImportJob['status'], string> = { running: 'Загружается', done: 'Готово', failed: 'Ошибка' }
const SEVERITY_TEXT: Record<ImportSeverity, string> = { error: 'ошибка', warning: 'предупреждение', info: 'инфо' }

function Corners() {
  return <><i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" /></>
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

/* Значения метрик бэкенд не типизирует: число, строка, список или объект — показываем читаемо. */
function formatMetric(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return value.toLocaleString('ru-RU')
  if (typeof value === 'string' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(formatMetric).join(', ')
  return JSON.stringify(value)
}

function supplierLabel(value: string): string {
  return SUPPLIERS.find(item => item.value === value)?.label ?? value
}

function severityClass(severity: ImportSeverity): string {
  return severity === 'error' ? 'import-tag-error' : severity === 'warning' ? 'import-tag-warning' : 'import-tag-info'
}

function validateFiles(files: File[]): string {
  if (files.length === 0) return 'Выберите хотя бы один файл .xlsx'
  if (files.length > MAX_FILES) return `Можно загрузить не больше ${MAX_FILES} файлов за раз`
  const wrong = files.filter(file => !file.name.toLowerCase().endsWith('.xlsx'))
  if (wrong.length) return `Ожидаются файлы .xlsx, а выбраны: ${wrong.map(file => file.name).join(', ')}`
  return ''
}

export default function ImportPanel({ imports, onDataReplaced }: Props) {
  const [supplier, setSupplier] = useState<ImportSupplier>('IEK')
  const [files, setFiles] = useState<File[]>([])
  const [job, setJob] = useState<ImportJob | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [localHistory, setLocalHistory] = useState<ImportJob[] | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  /* Колбэк родителя читаем через ref, чтобы эффект опроса не перезапускался
     при каждом рендере родителя, который передаёт новую стрелку. */
  const onDataReplacedRef = useRef(onDataReplaced)
  useEffect(() => { onDataReplacedRef.current = onDataReplaced }, [onDataReplaced])

  /* История: приоритет у overview (родитель перезапрашивает его после импорта),
     GET /imports — запасной вариант, если экран поля не передал. */
  useEffect(() => {
    if (imports !== undefined) return
    listImports().then(setLocalHistory).catch(() => setLocalHistory([]))
  }, [imports])

  /* Опрос статуса раз в секунду, пока задача выполняется. Интервал живёт ровно столько,
     сколько есть активный import_id; размонтирование или смена id очищают его. */
  useEffect(() => {
    if (!activeId) return
    let cancelled = false
    let inFlight = false

    async function finish(finished: ImportJob) {
      setActiveId(null)
      if (imports === undefined) listImports().then(setLocalHistory).catch(() => undefined)
      if (finished.status !== 'done') return
      try {
        /* Ответ /imports/{id} не содержит шапку, поэтому берём её из /session:
           там уже data_mode = "uploaded" и сброшенный расчёт. */
        const header = await getSession()
        if (!cancelled) onDataReplacedRef.current(header)
      } catch (cause) {
        if (!cancelled) setError(`Данные загружены, но не удалось обновить сессию: ${String(cause)}`)
      }
    }

    async function tick() {
      if (inFlight) return
      inFlight = true
      try {
        const current = await getImport(activeId as string)
        if (cancelled) return
        setJob(current)
        if (current.status !== 'running') await finish(current)
      } catch (cause) {
        if (cancelled) return
        setError(`Не удалось получить статус загрузки: ${String(cause)}`)
        setActiveId(null)
      } finally {
        inFlight = false
      }
    }

    tick()
    const timer = window.setInterval(tick, POLL_MS)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [activeId, imports])

  function onFilesChange(event: React.ChangeEvent<HTMLInputElement>) {
    setFiles(Array.from(event.target.files ?? []))
    setError('')
  }

  function clearFiles() {
    setFiles([])
    if (fileInput.current) fileInput.current.value = ''
  }

  async function upload() {
    const problem = validateFiles(files)
    if (problem) { setError(problem); return }
    setUploading(true)
    setError('')
    setJob(null)
    try {
      const started = await startImport(supplier, files)
      /* Показываем «Загружаем…» сразу по 202, не дожидаясь первого ответа опроса. */
      setJob({ import_id: started.import_id, status: started.status, supplier: started.supplier, files: started.files, started_at: new Date().toISOString(), finished_at: null, report: null, error: null, applied: false })
      setActiveId(started.import_id)
      clearFiles()
    } catch (cause) {
      setError(`Не удалось загрузить файлы: ${String(cause instanceof Error ? cause.message : cause)}`)
    } finally {
      setUploading(false)
    }
  }

  const busy = uploading || activeId !== null
  const history = imports ?? localHistory ?? []
  const metrics = job?.report ? Object.entries(job.report.metrics) : []

  return (
    <>
      <section className="blueprint panel page-section"><Corners />
        <h2 className="card-title">Загрузка выгрузок 1С</h2>
        <p className="tiny" style={{ marginTop: 6 }}>
          Можно загрузить от одного до шести файлов .xlsx одного поставщика: {EXPECTED_FILES.join(', ')}. Недостающие типы берутся из текущего набора данных. Исходные файлы не изменяются.
        </p>

        <div className="field-grid" style={{ marginTop: 14 }}>
          <div className="field">
            <label id="import-supplier-label">Поставщик</label>
            <div className="seg" role="radiogroup" aria-labelledby="import-supplier-label">
              {SUPPLIERS.map(item => (
                <div className="seg-opt" key={item.value}>
                  <input type="radio" id={`import-supplier-${item.value}`} name="import-supplier" value={item.value} checked={supplier === item.value} disabled={busy} onChange={() => setSupplier(item.value)} />
                  <label htmlFor={`import-supplier-${item.value}`}>{item.label}</label>
                </div>
              ))}
            </div>
          </div>
          <div className="field">
            <label htmlFor="import-files">Файлы выгрузок (1–{MAX_FILES})</label>
            <input id="import-files" ref={fileInput} className="input" type="file" multiple accept=".xlsx" disabled={busy} onChange={onFilesChange} />
          </div>
        </div>

        {files.length > 0 && (
          <ul className="import-files">
            {files.map(file => <li key={`${file.name}-${file.size}`}><span>{file.name}</span><span className="tiny">{formatSize(file.size)}</span></li>)}
          </ul>
        )}

        <div className="inline-actions" style={{ marginTop: 14 }}>
          <button className="btn btn-primary blueprint" type="button" onClick={upload} disabled={busy || files.length === 0}><Corners />{uploading ? 'Отправка…' : 'Загрузить'}</button>
          {files.length > 0 && !busy && <button className="btn btn-ghost" type="button" onClick={clearFiles}>Очистить выбор</button>}
        </div>

        {error && <div className="import-notice-error" role="alert" style={{ marginTop: 14 }}>{error}</div>}

        {job && job.status === 'running' && (
          <div className="notice" role="status" style={{ marginTop: 14 }}>
            Загружаем… {supplierLabel(job.supplier)}: {job.files.join(', ')}
          </div>
        )}

        {job && job.status === 'failed' && (
          <div className="import-notice-error" role="alert" style={{ marginTop: 14 }}>
            <b>Импорт не выполнен.</b> {job.error || 'Сервер не сообщил причину.'}
            <div className="tiny" style={{ marginTop: 4, color: 'inherit' }}>Проверьте набор файлов: поставщик, формат .xlsx и состав выгрузок из подсказки выше.</div>
          </div>
        )}

        {job && job.status === 'done' && (
          <div style={{ marginTop: 14 }}>
            <div className="import-notice-ok" role="status">
              <b>Данные обновлены:</b> расчёт, версии и правки сброшены. Запустите расчёт заново.
            </div>
            {job.report && (
              <div className="data-two-column" style={{ marginTop: 14 }}>
                <div>
                  <h3 className="section-heading">Сводка импорта</h3>
                  <div className="scroll-table"><table className="table"><thead><tr><th>Показатель</th><th>Значение</th></tr></thead><tbody>
                    {metrics.map(([key, value]) => <tr key={key}><td className="tiny" style={{ fontFamily: 'var(--font-mono)' }}>{key}</td><td>{formatMetric(value)}</td></tr>)}
                    {metrics.length === 0 && <tr><td colSpan={2} className="muted">Метрики не переданы.</td></tr>}
                  </tbody></table></div>
                  <p className="tiny" style={{ marginTop: 8 }}>Файлы: {job.report.files.join(', ') || '—'}</p>
                </div>
                <div>
                  <h3 className="section-heading">Замечания <span className="tiny">{job.report.issues.length}</span></h3>
                  <div className="scroll-table"><table className="table"><thead><tr><th>Уровень</th><th>Замечание</th><th className="numeric">Кол-во</th></tr></thead><tbody>
                    {job.report.issues.map((issue, index) => (
                      <tr key={`${issue.code}-${index}`}>
                        <td><span className={`tag ${severityClass(issue.severity)}`}>{SEVERITY_TEXT[issue.severity] ?? issue.severity}</span></td>
                        <td>{issue.message}<div className="tiny">{issue.code}{issue.supplier ? ` · ${supplierLabel(issue.supplier)}` : ''}</div></td>
                        <td className="numeric">{issue.count.toLocaleString('ru-RU')}</td>
                      </tr>
                    ))}
                    {job.report.issues.length === 0 && <tr><td colSpan={3} className="muted">Замечаний нет.</td></tr>}
                  </tbody></table></div>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="page-section">
        <h2 className="section-heading">История загрузок <span className="tiny">{history.length}</span></h2>
        <div className="scroll-table">
          <table className="table" style={{ minWidth: 700 }}>
            <thead><tr><th>Время</th><th>Поставщик</th><th>Файлы</th><th>Статус</th></tr></thead>
            <tbody>
              {history.map(item => (
                <tr key={item.import_id}>
                  <td className="numeric" style={{ textAlign: 'left' }}>{formatDateTime(item.started_at)}</td>
                  <td><span className="tag tag-neutral">{supplierLabel(item.supplier)}</span></td>
                  <td className="tiny">{item.files.join(', ') || '—'}</td>
                  <td>
                    <span className={`tag ${item.status === 'done' ? 'tag-accent' : item.status === 'failed' ? 'import-tag-error' : 'tag-outline'}`}>{STATUS_TEXT[item.status] ?? item.status}</span>
                    {item.status === 'failed' && item.error && <div className="tiny">{item.error}</div>}
                    {item.status === 'done' && !item.applied && <div className="tiny">не применён</div>}
                  </td>
                </tr>
              ))}
              {history.length === 0 && <tr><td colSpan={4} className="muted">Загрузок ещё не было</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
