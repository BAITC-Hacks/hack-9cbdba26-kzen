import { useState } from 'react'
import type { AppHeader } from '../types'

interface Props { header: AppHeader; onCalculate: () => void }

const DATA_SOURCES = [
  { name: 'Свободный остаток SE', file: 'Товар в пути_SystemElectric на 22.09.2026', status: 'used', rows: 847 },
  { name: 'Свободный остаток IEK', file: 'Свободные остатки ИЭК 22.09.2026', status: 'used', rows: 1203 },
  { name: 'Продажи SE', file: 'Ежемесячные продажи SE янв.2024–сент.2026', status: 'used', rows: 3240 },
  { name: 'Продажи IEK', file: 'Ежемесячные продажи IEK янв.2024–сент.2026', status: 'used', rows: 2890 },
  { name: 'Прайс SE', file: '—', status: 'not_used', rows: 0 },
]

export default function DataScreen({ header, onCalculate }: Props) {
  const [leadTime, setLeadTime] = useState(30)
  const [reviewDays, setReviewDays] = useState(14)
  const [safetyDays, setSafetyDays] = useState(10)

  return (
    <div style={{ padding: 24, maxWidth: 900 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ marginBottom: 8 }}>Данные и параметры</h1>
        <p style={{ color: 'var(--color-neutral-600)' }}>Склад: {header.warehouse.name} · Дата расчёта: {header.calc_date}</p>
      </div>

      <section style={{ marginBottom: 24 }}>
        <h2 style={{ marginBottom: 12, fontSize: 18 }}>Источники данных</h2>
        <div style={{ background: 'white', borderRadius: 2, overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
          <table className='table'>
            <thead><tr>
              <th>Источник</th><th>Файл</th><th>Строк</th><th>Статус</th>
            </tr></thead>
            <tbody>
              {DATA_SOURCES.map((ds, i) => (
                <tr key={i}>
                  <td>{ds.name}</td>
                  <td style={{ color: 'var(--color-neutral-600)', fontSize: 12 }}>{ds.file}</td>
                  <td>{ds.rows > 0 ? ds.rows.toLocaleString('ru-RU') : '—'}</td>
                  <td>
                    {ds.status === 'used' && <span className='tag tag-accent'>Загружен</span>}
                    {ds.status === 'not_used' && <span className='tag tag-outline'>Не загружен</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button className='btn btn-secondary'>Загрузить файл</button>
          <button className='btn btn-secondary'>Загрузить из 1С</button>
        </div>
      </section>

      <section style={{ marginBottom: 24 }}>
        <h2 style={{ marginBottom: 12, fontSize: 18 }}>Параметры расчёта</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, maxWidth: 600 }}>
          <div className='field'>
            <label>Срок поставки L (дн.)</label>
            <input className='input' type='number' value={leadTime} onChange={e => setLeadTime(+e.target.value)} />
          </div>
          <div className='field'>
            <label>Цикл пересмотра R (дн.)</label>
            <input className='input' type='number' value={reviewDays} onChange={e => setReviewDays(+e.target.value)} />
          </div>
          <div className='field'>
            <label>Страховой запас (дн.)</label>
            <input className='input' type='number' value={safetyDays} onChange={e => setSafetyDays(+e.target.value)} />
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          <p style={{ fontSize: 12, color: 'var(--color-neutral-600)' }}>
            Горизонт H = L {leadTime} + R {reviewDays} = {leadTime + reviewDays} дн.
          </p>
        </div>
      </section>

      <section style={{ marginBottom: 24 }}>
        <h2 style={{ marginBottom: 12, fontSize: 18 }}>Настройки What-If</h2>
        <div className='notice'>
          What-If режим позволяет смоделировать сдвиг поставки или изменение спроса перед расчётом.
        </div>
        <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, maxWidth: 400 }}>
          <div className='field'>
            <label>Задержка поставки (дн.)</label>
            <input className='input' type='number' defaultValue={0} min={0} />
          </div>
          <div className='field'>
            <label>Изменение спроса (%)</label>
            <input className='input' type='number' defaultValue={100} min={50} max={200} />
          </div>
        </div>
      </section>

      <button className='btn btn-primary blueprint' style={{ fontSize: 15, padding: '10px 24px' }} onClick={onCalculate}>
        <i className='corner tl' /><i className='corner tr' />
        <i className='corner bl' /><i className='corner br' />
        Рассчитать рекомендации
      </button>
    </div>
  )
}