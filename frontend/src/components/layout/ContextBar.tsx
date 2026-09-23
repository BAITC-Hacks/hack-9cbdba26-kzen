import type { AppHeader } from '../../types'
import { formatDate } from '../ui/format'
import { Badge } from '../ui'

interface Props { header: AppHeader }

const ORDER_STATUS = {
  draft: { label: 'черновик', tone: 'neutral' as const },
  submitted: { label: 'на согласовании', tone: 'warning' as const },
  approved: { label: 'утверждён', tone: 'success' as const },
}

export default function ContextBar({ header }: Props) {
  const order = header.order ? ORDER_STATUS[header.order.status] : null
  return (
    <div className="context-strip">
      <div className="context-strip-inner">
        <span className="context-item">Склад <b>{header.warehouse.name}</b></span>
        <span className="context-item">Категория <b>{header.category_filter || 'все'}</b></span>
        <span className="context-item">Расчёт на <b>{formatDate(header.calc_date)}</b></span>
        <span className="context-item">Срез данных <b>{formatDate(header.data_cut_date)}</b></span>
        <span className="context-item">
          Заказ{' '}
          {header.order && order
            ? <Badge tone={order.tone}>v{header.order.version} · {order.label}</Badge>
            : <b>нет версии</b>}
        </span>
        <div className="context-flags">
          {!header.calc_at && <Badge tone="warning" icon="alert">Расчёт не запускался</Badge>}
          {header.calc_stale && <Badge tone="warning" icon="clock">Расчёт устарел</Badge>}
          {header.snapshot_stale && <Badge tone="warning" icon="clock">Остаток старше 7 дней</Badge>}
          {header.what_if_active && <Badge tone="accent" icon="sparkles">Сценарий «что если»</Badge>}
          <Badge tone={header.data_mode === 'imported' || header.data_mode === 'uploaded' ? 'success' : 'outline'} icon="database">{header.data_mode_text}</Badge>
        </div>
      </div>
    </div>
  )
}
