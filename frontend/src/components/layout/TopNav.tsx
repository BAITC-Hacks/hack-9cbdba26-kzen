import type { AppHeader } from '../../types'

interface Props {
  header: AppHeader
  activeScreen: number
  onScreen: (n: number) => void
}

const SCREENS = [
  { n: 1, label: '01 Данные' },
  { n: 2, label: '02 Рекомендации' },
  { n: 3, label: '03 SKU' },
  { n: 4, label: '04 Заказ' },
  { n: 5, label: '05 Проверка' },
]

export default function TopNav({ header, activeScreen, onScreen }: Props) {
  return (
    <nav className='nav' style={{ height: 48, borderBottom: '1px solid var(--color-divider)', justifyContent: 'space-between' }}>
      <span className='nav-brand'>Электрокомплект · Закупки</span>
      <div style={{ display: 'flex', gap: 2 }}>
        {SCREENS.map(s => (
          <button key={s.n} className={'btn btn-ghost' + (activeScreen === s.n ? ' active-tab' : '')}
            style={activeScreen === s.n ? { background: 'var(--color-accent-200)', color: 'var(--color-accent-900)', fontWeight: 600 } : {}}
            onClick={() => onScreen(s.n)}>
            {s.label}
          </button>
        ))}
      </div>
      <span style={{ fontSize: 12, color: 'var(--color-neutral-600)' }}>{header.user.name}</span>
    </nav>
  )
}