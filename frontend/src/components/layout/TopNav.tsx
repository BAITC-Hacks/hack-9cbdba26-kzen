import type { AppHeader } from '../../types'
import Icon from '../ui/Icon'

interface Props {
  header: AppHeader
  activeScreen: number
  onScreen: (n: number) => void
}

// Карточка позиции (экран 3) — не отдельный шаг процесса, а раскрытие строки
// из рекомендаций, поэтому в навигации её нет: вкладка «Объяснение SKU» без
// выбранной позиции только путала.
const STEPS = [
  { n: 1, label: 'Данные', icon: 'database' },
  { n: 2, label: 'Рекомендации', icon: 'list' },
  { n: 4, label: 'Согласование', icon: 'file-check' },
  { n: 5, label: 'Проверки', icon: 'shield' },
]

export default function TopNav({ header, activeScreen, onScreen }: Props) {
  const active = activeScreen === 3 ? 2 : activeScreen
  const initials = header.user.name.split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase()
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="brand">
          <div className="brand-mark"><Icon name="bolt" size={18} /></div>
          <div>
            <div className="brand-name">Электрокомплект</div>
            <div className="brand-sub">Пополнение запасов</div>
          </div>
        </div>
        <nav className="nav-steps" aria-label="Шаги процесса">
          {STEPS.map((step, index) => (
            <span key={step.n} className="row" style={{ gap: 4 }}>
              {index > 0 && <Icon name="chevron-right" size={14} className="nav-step-arrow" />}
              <button
                type="button"
                className={`nav-step${active === step.n ? ' is-active' : ''}`}
                aria-current={active === step.n ? 'page' : undefined}
                onClick={() => onScreen(step.n)}
                title={step.label}
              >
                <span className="nav-step-num">{index + 1}</span>
                <span className="nav-step-text">{step.label}</span>
              </button>
            </span>
          ))}
        </nav>
        <div className="header-user">
          <div className="avatar" aria-hidden="true">{initials || 'М'}</div>
          <div>
            <div className="header-user-name">{header.user.name}</div>
            <div className="header-user-role">{header.role === 'head' ? 'Руководитель закупок' : 'Менеджер закупа'}</div>
          </div>
        </div>
      </div>
    </header>
  )
}
