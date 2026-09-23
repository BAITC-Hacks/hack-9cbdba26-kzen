import { useEffect, useState } from 'react'
import type { DataOverview, ValidationScenarios } from '../types'
import { getDataOverview, getValidation } from '../api/client'
import Icon from '../components/ui/Icon'
import { Badge, Card, CardHeader, EmptyState, Loading, Notice } from '../components/ui'

export default function ValidationScreen() {
  const [data, setData] = useState<ValidationScenarios | null>(null)
  const [overview, setOverview] = useState<DataOverview | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getValidation(), getDataOverview()])
      .then(([checks, sources]) => { setData(checks); setOverview(sources) })
      .catch(cause => setError(String(cause)))
  }, [])

  const allPassed = data ? data.passed === data.total : false
  const ratio = data && data.total ? Math.round((data.passed / data.total) * 100) : 0

  return (
    <div className="page stack">
      <header className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Проверки по ТЗ</h1>
          <p className="page-subtitle">Сценарии приёмки из технического задания прогоняются на сервере против текущей версии расчётного ядра.</p>
        </div>
      </header>

      {error && <Notice tone="danger" role="alert">Не удалось загрузить проверки: {error}</Notice>}

      <Card>
        <div className="card-body">
          <div className="row-between">
            <div className="row" style={{ gap: 14 }}>
              <div className={`check-icon ${allPassed ? 'pass' : 'fail'}`} style={{ width: 44, height: 44 }}><Icon name={allPassed ? 'shield' : 'alert'} size={22} /></div>
              <div>
                <h2>{data ? data.summary_text : 'Проверяем…'}</h2>
                <p className="tiny">{allPassed ? 'Все обязательные требования выполнены.' : data ? 'Часть сценариев не прошла, подробности ниже.' : ''}</p>
              </div>
            </div>
            {data && <Badge tone={allPassed ? 'success' : 'warning'}>{data.passed} / {data.total}</Badge>}
          </div>
          <div className="progress" style={{ marginTop: 16 }}><i style={{ width: `${ratio}%` }} /></div>
        </div>
        {data ? (
          <div className="check-list" style={{ borderTop: '1px solid var(--color-border)' }}>
            {data.items.map(item => (
              <div className="check-item" key={item.n}>
                <div className={`check-icon ${item.passed ? 'pass' : 'fail'}`}><Icon name={item.passed ? 'check' : 'x'} size={16} /></div>
                <div>
                  <div className="check-name">{item.n}. {item.name}</div>
                  {item.expected_text && <div className="tiny" style={{ marginTop: 2 }}>Ожидание: {item.expected_text}</div>}
                  <div className="muted" style={{ marginTop: 4, fontSize: 'var(--text-sm)' }}>{item.actual_text}</div>
                </div>
                <Badge tone={item.passed ? 'success' : 'danger'}>{item.passed ? 'Пройден' : 'Ошибка'}</Badge>
              </div>
            ))}
          </div>
        ) : !error && <Loading text="Загружаем сценарии…" />}
      </Card>

      <div className="grid-2">
        <Card>
          <CardHeader icon="database" title="Какие источники участвуют в расчёте" />
          {overview ? (
            overview.sources.length ? (
              <div className="table-wrap">
                <table className="table table-compact">
                  <thead><tr><th>Поставщик</th><th>Файл</th><th>Применение</th></tr></thead>
                  <tbody>{overview.sources.map(source => <tr key={source.key}><td><Badge tone="outline">{source.supplier.id === 'SE' ? 'Systeme Electric' : 'ИЭК'}</Badge></td><td className="cell-primary" style={{ whiteSpace: 'normal' }}>{source.file?.name || source.type_text}</td><td className="muted" style={{ whiteSpace: 'normal' }}>{source.usage_text || 'применён в расчёте'}</td></tr>)}</tbody>
                </table>
              </div>
            ) : <div className="card-body"><EmptyState icon="database" title="Источники не найдены" /></div>
          ) : <Loading />}
        </Card>
        <Card className="card-muted">
          <CardHeader icon="history" title="Хронологический бэктест" actions={<Badge tone="outline">скоро</Badge>} />
          <div className="card-body">
            <p className="muted">Скользящее окно сравнивает прогноз с фактическим регулярным спросом следующих месяцев. Метрики WAPE, MAE и bias появятся, когда результаты бэктеста будут отдаваться через API.</p>
          </div>
        </Card>
      </div>
    </div>
  )
}
