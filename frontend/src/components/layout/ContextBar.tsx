import type { AppHeader } from '../../types'

interface Props { header: AppHeader }

function dateLabel(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-')
  return year && month && day ? `${day}.${month}.${year}` : value
}

export default function ContextBar({ header }: Props) {
  const status = !header.order ? 'нет версии' : header.order.status === 'draft' ? 'черновик' : header.order.status === 'submitted' ? 'на согласовании' : 'утверждён'
  return (
    <div className="context-bar">
      <span>Склад: <b>{header.warehouse.name}</b></span>
      <span>Категория: <b>{header.category_filter || 'Все категории'}</b></span>
      <span>Дата расчёта: <b>{dateLabel(header.calc_date)}</b></span>
      <span>Срез данных: <b>{dateLabel(header.data_cut_date)}</b></span>
      <span>Версия: <b>{header.order ? `v${header.order.version} · ${status}` : status}</b></span>
      <span>Роль: <b>{header.role === 'head' ? 'Руководитель закупок' : 'Менеджер закупа'}</b></span>
      <span>Расчёт: <b>{header.calc_at ? 'выполнен' : 'не запускался'}</b></span>
      {header.snapshot_stale && <span className="tag tag-outline">Снимок остатка старше 7 дней</span>}
      {header.calc_stale && <span className="tag tag-outline">Расчёт устарел</span>}
      {header.what_if_active && <span className="tag tag-outline">Сценарий «что если» активен</span>}
      <span className="tag tag-neutral context-source">{header.data_mode_text}</span>
    </div>
  )
}
