import type { AppHeader } from '../../types'

interface Props {
  header: AppHeader
  activeScreen: number
  onScreen: (n: number) => void
}

const SCREENS = [
  { n: 1, label: 'Данные и параметры' },
  { n: 2, label: 'Рекомендации' },
  { n: 3, label: 'Объяснение SKU' },
  { n: 4, label: 'Проверка и экспорт' },
  { n: 5, label: 'Проверки ТЗ' },
]

export default function TopNav({ header, activeScreen, onScreen }: Props) {
  return (
    <nav className="nav app-nav" aria-label="Основная навигация">
      <div className="nav-brand">Электрокомплект <span>Пополнение запасов</span></div>
      <div className="nav-tabs">
        {SCREENS.map(screen => (
          <button
            key={screen.n}
            type="button"
            className={`nav-tab${activeScreen === screen.n ? ' is-active' : ''}`}
            aria-current={activeScreen === screen.n ? 'page' : undefined}
            onClick={() => onScreen(screen.n)}
          >
            <span>{String(screen.n).padStart(2, '0')}</span>{screen.label}
          </button>
        ))}
      </div>
      <span className="nav-user">{header.user.name}</span>
    </nav>
  )
}
