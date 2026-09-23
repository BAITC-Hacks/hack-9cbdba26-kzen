import { useEffect, useState } from 'react'
import type { DataOverview, ValidationScenarios } from '../types'
import { getDataOverview, getValidation } from '../api/client'

export default function ValidationScreen() {
  const [data, setData] = useState<ValidationScenarios | null>(null)
  const [overview, setOverview] = useState<DataOverview | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getValidation(), getDataOverview()])
      .then(([checks, sources]) => { setData(checks); setOverview(sources) })
      .catch(cause => setError(String(cause)))
  }, [])

  return <div className="page">
    <header className="page-head"><div><h1>Проверки по ТЗ</h1><p className="page-subtitle">Проверки рассчитываются на сервере по сценариям приёмки. Результат отражает текущую версию расчётного ядра.</p></div>{data && <span className={`tag ${data.passed === data.total ? 'tag-accent' : 'tag-outline'}`}>{data.summary_text}</span>}</header>
    {error && <div className="notice" role="alert">Не удалось загрузить проверки: {error}</div>}

    <section>
      <div className="inline-actions" style={{ marginBottom: 10 }}><h2>Проверки по ТЗ</h2>{data && <span className="tag tag-neutral">{data.passed} / {data.total}</span>}</div>
      <div className="scroll-table"><table className="table" style={{ minWidth: 740 }}><thead><tr><th style={{ width: 50 }}>№</th><th>Сценарий</th><th>Ожидаемое поведение</th><th>Фактический результат</th><th>Итог</th></tr></thead><tbody>{data?.items.map(item => <tr key={item.n}><td className="muted">{item.n}</td><td style={{ fontWeight: 500 }}>{item.name}</td><td className="tiny">{item.expected_text || '—'}</td><td>{item.actual_text}</td><td><span className={`tag ${item.passed ? 'tag-accent' : 'tag-outline'}`}>{item.passed ? 'Пройден' : 'Ошибка'}</span></td></tr>)}</tbody></table></div>
      {!data && !error && <p className="muted" style={{ marginTop: 12 }}>Загрузка проверок…</p>}
    </section>

    <section className="page-section blueprint panel"><h2 className="card-title">Хронологический backtest</h2><p className="page-subtitle">Скользящее окно сравнивает прогнозы с регулярным спросом последующих месяцев. Метрики WAPE, MAE и bias появятся после подключения результатов бэктеста к API.</p></section>

    <section className="page-section"><h2 className="section-heading">Участие источников в расчёте</h2><div className="scroll-table"><table className="table"><thead><tr><th>Источник</th><th>Поставщик</th><th>Применение</th><th>Файл</th></tr></thead><tbody>{overview?.sources.map(source => <tr key={source.key}><td>{source.type_text}</td><td>{source.supplier.id === 'SE' ? 'Systeme Electric' : 'ИЭК'}</td><td>{source.usage_text || 'Роль источника не указана'}</td><td className="tiny">{source.file?.name || '—'}</td></tr>)}{overview && overview.sources.length === 0 && <tr><td colSpan={4} className="muted">Источники в текущем окружении не найдены.</td></tr>}</tbody></table></div></section>
  </div>
}
