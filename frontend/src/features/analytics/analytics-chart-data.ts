import type { ReplyState } from '@/types/reply'
import type {
  TicketPriority,
  TicketStatus,
} from '@/types/ticket'

/**
 * Chart palette and data-shaping helpers for the analytics page. Kept outside
 * the component module so Fast Refresh stays effective.
 */

export const STATUS_COLORS: Record<TicketStatus, string> = {
  new: '#2563eb',
  open: '#0d9488',
  pending: '#64748b',
  needs_review: '#d97706',
  resolved: '#15803d',
  closed: '#94a3b8',
}

export const PRIORITY_COLORS: Record<TicketPriority, string> = {
  urgent: '#dc2626',
  high: '#d97706',
  normal: '#2563eb',
  low: '#94a3b8',
}

export const REPLY_STATE_COLORS: Record<ReplyState, string> = {
  draft: '#94a3b8',
  pending_approval: '#d97706',
  approved: '#0d9488',
  changes_requested: '#dc2626',
  sent: '#2563eb',
}

export interface BarDatum {
  key: string
  label: string
  value: number
  color: string
}

export function statusBarData(
  distribution: Array<{ status: TicketStatus; count: number }>,
  labels: Record<TicketStatus, string>,
): BarDatum[] {
  return distribution.map((row) => ({
    key: row.status,
    label: labels[row.status],
    value: row.count,
    color: STATUS_COLORS[row.status],
  }))
}

export function priorityBarData(
  distribution: Array<{ priority: TicketPriority; count: number }>,
  labels: Record<TicketPriority, string>,
): BarDatum[] {
  return distribution.map((row) => ({
    key: row.priority,
    label: labels[row.priority],
    value: row.count,
    color: PRIORITY_COLORS[row.priority],
  }))
}

export function replyStateBarData(
  distribution: Array<{ state: ReplyState; count: number }>,
  labels: Record<ReplyState, string>,
): BarDatum[] {
  return distribution.map((row) => ({
    key: row.state,
    label: labels[row.state],
    value: row.count,
    color: REPLY_STATE_COLORS[row.state],
  }))
}
