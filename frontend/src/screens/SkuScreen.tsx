import { useEffect, useState } from 'react'
import type { SkuExplanation, SkuId } from '../types'
import { getSkuExplanation } from '../api/client'

interface Props { skuId: SkuId | null; onBack: () => void }

export default function SkuScreen({ skuId, onBack }: Props) {
  const [data, setData] = useState<SkuExplanation | null>(null)

  useEffect(() => {
    if (!skuId) return
    getSkuExplanation(skuId).then(setData)
  }, [skuId])

  if (!skuId || !data) return (
    <div style={{ padding: 24 }}>
      <p style={{ color: 'var(--color-neutral-600)' }}>Выберите позицию из таблицы рекомендаций.</p>
      <button className='btn' style={{ marginTop: 12 }} onClick={onBack}>← Назад</button>
    </div>
  )

  const maxSales = Math.max(...data.chart.months.map(m => Math.max(m.sales, m.restored)), ...data.chart.forecast.map(f => f.qty), 1)

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <button className='btn btn-ghost' onClick={onBack}>← Назад</button>
        <h1 style={{ fontSize: 20 }}>{data.sku.name}</h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <span className='tag tag-outline'>{data.sku.code_1c}</span>
        <span className='tag tag-outline'>{data.sku.supplier_article}</span>
        <span className='tag tag-outline'>{data.sku.supplier.name}</span>
        <span className='tag tag-outline'>Кат. {data.sku.category}</span>
        {data.status === 'order' && <span className='tag tag-accent'>Заказать</span>}
        {data.urgency === 'urgent' && <span style={{ color: '#c0392b', fontWeight: 600, fontSize: 13 }}>Срочно</span>}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>        <div>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Динамика продаж и прогноз</h2>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 120, marginBottom: 8 }}>
            {data.chart.months.map(m => {
              const val = m.restored > 0 ? m.restored : m.sales
              const h = Math.round((val / maxSales) * 100)
              return (
                <div key={m.month} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 28 }}>
                  <div title={String(val)} style={{
                    width: '100%', height: h + '%', minHeight: 2,
                    background: m.in_base ? 'var(--color-accent)' : m.partial ? 'var(--color-accent-400)' : 'var(--color-neutral-300)',
                    borderRadius: '2px 2px 0 0',
                    border: m.restored > 0 ? '2px dashed var(--color-accent-600)' : 'none',
                  }} />
                  <span style={{ fontSize: 9, color: 'var(--color-neutral-600)', marginTop: 2 }}>{m.label}</span>
                </div>
              )
            })}
            {data.chart.forecast.map(f => (
              <div key={f.month} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 28, background: 'var(--color-accent-100)', borderRadius: 2 }}>
                <div style={{ width: '100%', height: Math.round((f.qty / maxSales) * 100) + '%', minHeight: 2, background: 'var(--color-accent-400)', borderRadius: '2px 2px 0 0' }} />
                <span style={{ fontSize: 9, color: 'var(--color-accent-700)', marginTop: 2 }}>{f.label}</span>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--color-neutral-600)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-accent)', display: 'inline-block', borderRadius: 1 }} />В базе</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-neutral-300)', display: 'inline-block', borderRadius: 1 }} />Не в базе</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 12, height: 8, background: 'var(--color-accent-100)', border: '1px solid var(--color-accent-400)', display: 'inline-block', borderRadius: 1 }} />Прогноз</span>
          </div>

          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: 13, marginBottom: 8, fontFamily: 'var(--font-body)', fontWeight: 600 }}>Параметры спроса</h3>
            <table className='table' style={{ fontSize: 12 }}>
              <tbody>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Ср. регулярный спрос</td><td>{new Intl.NumberFormat('ru-RU').format(data.demand.regular_avg)} шт/мес</td></tr>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Сезонность</td><td>{data.demand.season} · {data.demand.season_source_text}</td></tr>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Тренд</td><td>{data.demand.trend_estimate_text} · {data.demand.trend_source_text}</td></tr>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Срок поставки L</td><td>{data.params.lead_time_days} дн.</td></tr>
                <tr><td style={{ color: 'var(--color-neutral-600)' }}>Цикл пересмотра R</td><td>{data.params.review_days} дн.</td></tr>
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: 13, marginBottom: 8, fontFamily: 'var(--font-body)', fontWeight: 600 }}>Остатки и поступления</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <div style={{ background: 'white', border: '1px solid var(--color-divider)', borderRadius: 2, padding: '8px 12px', flex: 1 }}>
                <div style={{ fontSize: 20, fontFamily: 'var(--font-heading)', fontWeight: 600 }}>{data.stock.free ?? '—'}</div>
                <div style={{ fontSize: 11, color: 'var(--color-neutral-600)' }}>свободно · {data.stock.cover_text}</div>
              </div>
              <div style={{ background: 'white', border: '1px solid var(--color-divider)', borderRadius: 2, padding: '8px 12px', flex: 1 }}>
                <div style={{ fontSize: 20, fontFamily: 'var(--font-heading)', fontWeight: 600 }}>{data.stock.reserve}</div>
                <div style={{ fontSize: 11, color: 'var(--color-neutral-600)' }}>в резерве</div>
              </div>
            </div>
            {data.inbound.length > 0 && (
              <table className='table' style={{ fontSize: 12 }}>
                <thead><tr><th>Документ</th><th>Кол-во</th><th>ETA</th><th>Учтён</th></tr></thead>
                <tbody>
                  {data.inbound.map(ib => (
                    <tr key={ib.id}>
                      <td>{ib.doc_text}</td>
                      <td>{new Intl.NumberFormat('ru-RU').format(ib.qty)}</td>
                      <td>{ib.eta} <span style={{ color: 'var(--color-neutral-500)' }}>({ib.where_text})</span></td>
                      <td>{ib.counted ? <span className='tag tag-accent'>Да</span> : <span className='tag tag-neutral'>Нет</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>        <div>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Расчёт рекомендации</h2>
          <div className='notice' style={{ marginBottom: 16 }}>{data.explanation_text}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.steps.map(step => (
              <div key={step.key} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                padding: step.large ? '12px 16px' : '6px 12px',
                background: step.large ? 'var(--color-accent-100)' : step.emphasis ? 'var(--color-neutral-100)' : 'transparent',
                border: step.large ? '1px solid var(--color-accent-300)' : step.emphasis ? '1px solid var(--color-divider)' : 'none',
                borderRadius: 2,
              }}>
                <div>
                  <span style={{ fontWeight: step.emphasis ? 600 : 400, fontSize: step.large ? 15 : 14 }}>{step.label}</span>
                  {step.note_text && <div style={{ fontSize: 11, color: 'var(--color-neutral-600)', marginTop: 2 }}>{step.note_text}</div>}
                </div>
                <span style={{ fontFamily: 'var(--font-heading)', fontSize: step.large ? 22 : 16, fontWeight: 600, color: step.large ? 'var(--color-accent-900)' : 'var(--color-text)' }}>{step.value_text}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 24, padding: 16, border: '1px solid var(--color-divider)', borderRadius: 2 }}>
            <h3 style={{ fontSize: 13, marginBottom: 12, fontFamily: 'var(--font-body)', fontWeight: 600 }}>Ручная корректировка</h3>
            {data.manual.active
              ? <div className='notice'>Активна ручная корректировка: {data.manual.qty} шт. — {data.manual.note_text}</div>
              : <div style={{ display: 'flex', gap: 8 }}>
                  <div className='field' style={{ flex: 1 }}>
                    <label>Кол-во (шт.)</label>
                    <input className='input' type='number' placeholder='Введите вручную...' />
                  </div>
                  <div className='field' style={{ flex: 2 }}>
                    <label>Причина</label>
                    <input className='input' type='text' placeholder='Причина изменения...' />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                    <button className='btn btn-primary'>Сохранить</button>
                  </div>
                </div>
            }
          </div>

          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: 13, marginBottom: 8, fontFamily: 'var(--font-body)', fontWeight: 600 }}>Источники данных</h3>
            <table className='table' style={{ fontSize: 11 }}>
              <thead><tr><th>Показатель</th><th>Источник</th><th>Тип</th></tr></thead>
              <tbody>
                {data.provenance.map((prov, i) => (
                  <tr key={i}>
                    <td>{prov.input}</td>
                    <td style={{ color: 'var(--color-neutral-600)' }}>{prov.source_text}</td>
                    <td><span className={prov.origin === 'synthetic' ? 'tag tag-neutral' : 'tag tag-accent'}>{prov.origin}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}