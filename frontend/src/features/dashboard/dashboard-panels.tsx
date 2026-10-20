import type { ElementType } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowUpDown,
  BellRing,
  CheckCircle2,
  CircleDot,
  MessageSquare,
  PencilLine,
  Send,
  Shuffle,
  UserPlus,
} from 'lucide-react'
import type { ActivityAction, DashboardStats } from '@/types/ticket'
import { formatRelativeTime } from '@/lib/format'
import { ACTIVITY_ACTION_LABELS } from '@/lib/activity-config'
import { StatusBadge, PriorityBadge } from '@/components/shared/ticket-badges'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

/* ---------------------------- Recent tickets ---------------------------- */

export function RecentTickets({ tickets }: { tickets: DashboardStats['recentTickets'] }) {
  const navigate = useNavigate()
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-card-muted">
          <TableHead>Ticket</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="hidden sm:table-cell">Priority</TableHead>
          <TableHead className="pr-4 text-right">Received</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tickets.map((ticket) => (
          <TableRow
            key={ticket.id}
            className="cursor-pointer"
            onClick={() => navigate(`/tickets/${ticket.id}`, { state: { returnTo: '/' } })}
            onKeyDown={(e) => {
              if (e.target !== e.currentTarget) return
              if (e.key === 'Enter') {
                e.preventDefault()
                navigate(`/tickets/${ticket.id}`, { state: { returnTo: '/' } })
              }
            }}
            tabIndex={0}
          >
            <TableCell className="max-w-[280px] pl-4">
              <span className="block truncate font-medium text-foreground">
                {ticket.subject}
              </span>
              <span className="block text-xs text-muted-foreground tabular-nums">
                {ticket.id}
              </span>
            </TableCell>
            <TableCell>
              <StatusBadge status={ticket.status} />
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              <PriorityBadge priority={ticket.priority} />
            </TableCell>
            <TableCell className="whitespace-nowrap pr-4 text-right text-xs text-muted-foreground">
              {formatRelativeTime(ticket.createdAt)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

/* -------------------------- Compact priority summary -------------------------- */

export function PrioritySummary({
  data,
}: {
  data: DashboardStats['prioritySummary']
}) {
  const byPriority = new Map(data.map((row) => [row.priority, row]))

  return (
    <Table aria-label="Open tickets by priority">
      <TableHeader>
        <TableRow className="hover:bg-card-muted">
          <TableHead className="pl-4">Priority</TableHead>
          <TableHead className="text-right">Open</TableHead>
          <TableHead className="text-right">Pending</TableHead>
          <TableHead className="pr-4 text-right">Review</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {(['urgent', 'high', 'normal', 'low'] as const).map((priority) => {
          const row = byPriority.get(priority)
          if (!row) return null
          return (
            <TableRow key={priority}>
              <TableCell className="pl-4">
                <PriorityBadge priority={priority} />
              </TableCell>
              <TableCell className={cn('text-right tabular-nums', row.open > 0 ? 'text-foreground' : 'text-subtle-foreground')}>
                {row.open}
              </TableCell>
              <TableCell className={cn('text-right tabular-nums', row.pending > 0 ? 'text-foreground' : 'text-subtle-foreground')}>
                {row.pending}
              </TableCell>
              <TableCell
                className={cn(
                  'pr-4 text-right tabular-nums',
                  row.needsReview > 0 ? 'text-foreground' : 'text-subtle-foreground',
                )}
              >
                {row.needsReview}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}

/* ----------------------------- Recent activity ----------------------------- */

const ACTIVITY_ICONS: Record<ActivityAction, ElementType> = {
  created: CircleDot,
  categorized: Shuffle,
  assigned: UserPlus,
  replied_draft: PencilLine,
  replied_sent: Send,
  status_changed: Shuffle,
  escalated: BellRing,
  review_flagged: BellRing,
  merged: Shuffle,
  resolved: CheckCircle2,
  priority_changed: ArrowUpDown,
  note_added: MessageSquare,
  reply_submitted: Send,
  reply_approved: CheckCircle2,
  reply_changes_requested: AlertTriangle,
}

export function RecentActivity({
  activity,
}: {
  activity: DashboardStats['recentActivity']
}) {
  return (
    <ol className="space-y-3 px-4 pb-4">
      {activity.map((event) => {
        const Icon = ACTIVITY_ICONS[event.action] ?? CircleDot
        const label = ACTIVITY_ACTION_LABELS[event.action]
        const safeDetail =
          event.action === 'note_added' ||
          event.action === 'reply_changes_requested'
            ? null
            : event.detail
        return (
          <li key={event.id} className="flex gap-2.5">
            <span
              aria-hidden="true"
              className={cn(
                'mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full [&_svg]:size-3',
                event.action === 'review_flagged' ||
                  event.action === 'escalated' ||
                  event.action === 'reply_changes_requested'
                  ? 'bg-warning-tint text-warning'
                  : event.action === 'resolved' ||
                      event.action === 'reply_approved' ||
                      event.action === 'replied_sent'
                    ? 'bg-success-tint text-success'
                    : event.action === 'note_added' ||
                        event.action === 'reply_submitted'
                      ? 'bg-primary-tint text-primary'
                      : 'bg-muted text-muted-foreground',
              )}
            >
              <Icon />
            </span>
            <div className="min-w-0">
              <p className="text-sm leading-snug">
                <span className="font-medium text-foreground">{label}</span>{' '}
                <span className="font-mono text-xs text-muted-foreground">{event.ticketId}</span>
                <span className="text-muted-foreground"> — {event.actorName}</span>
                <span className="text-xs text-subtle-foreground"> · {formatRelativeTime(event.createdAt)}</span>
              </p>
              {safeDetail ? (
                <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground" title={safeDetail}>
                  {safeDetail}
                </p>
              ) : null}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
