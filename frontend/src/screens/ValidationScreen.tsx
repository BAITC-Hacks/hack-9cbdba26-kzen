import { useEffect, useState } from 'react'
import type { ValidationScenarios } from '../types'
import { getValidation } from '../api/client'

export default function ValidationScreen() {
  const [data, setData] = useState<ValidationScenarios | null>(null)
  useEffect(() => { getValidation().then(setData) }, [])
  if (!data) return <div style={{ padding: 24 }}>Загрузка...</div>

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ marginBottom: 4 }}>Проверка TZ</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 18, fontFamily: 'var(--font-heading)', color: data.passed === data.total ? 'green' : '#c0392b' }}>
            {data.summary_text}
          </span>
          <span className={data.passed === data.total ? 'tag tag-accent' : 'tag tag-outline'}>
            {data.passed === data.total ? 'Все проверки пройдены' : 'Есть ошибки'}
          </span>
        </div>
      </div>

      <div style={{ background: 'white', borderRadius: 2, overflow: 'hidden', boxShadow: 'var(--shadow-sm)', marginBottom: 24 }}>
        <table className='table'>
          <thead><tr>
            <th style={{ width: 40 }}>№</th>
            <th>Сценарий</th>
            <th>Ожидаемое поведение</th>
            <th>Фактический результат</th>
            <th>Итог</th>
          </tr></thead>
          <tbody>
            {data.items.map(item => (
              <tr key={item.n}>
                <td style={{ color: 'var(--color-neutral-500)' }}>{item.n}</td>
                <td style={{ fontWeight: 500 }}>{item.name}</td>
                <td style={{ fontSize: 12, color: 'var(--color-neutral-600)' }}>{item.expected_text}</td>
                <td style={{ fontSize: 12 }}>{item.actual_text}</td>
                <td>
                  {item.passed
                    ? <span className='tag tag-accent'>Пройден</span>
                    : <span className='tag tag-outline' style={{ color: '#c0392b', borderColor: '#c0392b' }}>Ошибка</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 18, marginBottom: 12 }}>Бэктест</h2>
        <div className='notice' style={{ marginBottom: 12 }}>
          Бэктест сравнивает рекомендации алгоритма с фактическими закупками за исторический период.
        </div>
        <div style={{ background: 'white', borderRadius: 2, overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
          <table className='table'>
            <thead><tr>
              <th>Период</th><th>SKU</th><th>Рекоменд.</th><th>Факт</th><th>Отклонение</th>
            </tr></thead>
            <tbody>
              <tr><td>Сент. 2026</td><td>ЦБ-004121</td><td>84</td><td>72</td><td style={{ color: '#c0392b' }}>+17%</td></tr>
              <tr><td>Сент. 2026</td><td>ЦБ-004125</td><td>60</td><td>60</td><td style={{ color: 'green' }}>0%</td></tr>
              <tr><td>Авг. 2026</td><td>КМ-1260</td><td>20</td><td>25</td><td style={{ color: '#c0392b' }}>-20%</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}