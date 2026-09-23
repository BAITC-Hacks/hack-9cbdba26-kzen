import type { ReactNode } from 'react'
import type { SkuStatus, Urgency } from '../../types'
import Icon from './Icon'
import { STATUS, type Tone } from './status'

export function Badge({ tone = 'neutral', icon, children, dot }: { tone?: Tone; icon?: string; children: ReactNode; dot?: boolean }) {
  return <span className={`badge badge-${tone}${dot ? ' badge-dot' : ''}`}>{icon && <Icon name={icon} size={12} />}{children}</span>
}

export function StatusBadge({ status }: { status: SkuStatus }) {
  const item = STATUS[status]
  return <Badge tone={item.tone} icon={item.icon}>{item.label}</Badge>
}

export function UrgencyBadge({ urgency }: { urgency: Urgency }) {
  if (urgency === 'urgent') return <Badge tone="danger" dot>Срочно</Badge>
  if (urgency === 'this_cycle') return <Badge tone="warning" dot>В этом цикле</Badge>
  return null
}

export function Notice({ tone = 'info', icon, children, role }: { tone?: 'info' | 'warning' | 'danger' | 'success' | 'neutral'; icon?: string; children: ReactNode; role?: 'status' | 'alert' }) {
  const defaultIcon = tone === 'warning' ? 'alert' : tone === 'danger' ? 'alert' : tone === 'success' ? 'check-circle' : 'info'
  return (
    <div className={`notice${tone === 'info' ? '' : ` notice-${tone}`}`} role={role}>
      <Icon name={icon ?? defaultIcon} size={16} />
      <div className="notice-body">{children}</div>
    </div>
  )
}

export function Card({ children, className = '', ...rest }: { children: ReactNode; className?: string; style?: React.CSSProperties }) {
  return <section className={`card ${className}`.trim()} {...rest}>{children}</section>
}

export function CardHeader({ title, subtitle, icon, actions }: { title: ReactNode; subtitle?: ReactNode; icon?: string; actions?: ReactNode }) {
  return (
    <div className="card-header">
      <div>
        <h3>{icon && <Icon name={icon} size={16} className="muted" />}{title}</h3>
        {subtitle && <p className="tiny">{subtitle}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  )
}

export function EmptyState({ icon = 'list', title, children }: { icon?: string; title: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <Icon name={icon} size={32} />
      <h3>{title}</h3>
      {children && <p className="tiny">{children}</p>}
    </div>
  )
}

export function Loading({ text = 'Загрузка…' }: { text?: string }) {
  return <div className="loading-block"><span className="spinner" />{text}</div>
}

export function Stat({ label, value, hint, tone = 'neutral', active, onClick }: { label: string; value: string; hint?: string; tone?: 'accent' | 'success' | 'warning' | 'danger' | 'neutral'; active?: boolean; onClick?: () => void }) {
  const className = `stat stat-tone-${tone}${active ? ' is-active' : ''}`
  const body = <><span className="stat-label">{label}</span><span className="stat-value">{value}</span>{hint && <span className="stat-hint">{hint}</span>}</>
  return onClick
    ? <button type="button" className={className} onClick={onClick} aria-pressed={active}>{body}</button>
    : <div className={className}>{body}</div>
}
