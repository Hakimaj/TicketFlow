import type {
  TicketCategory,
  TicketPriority,
  TicketStatus,
} from '@/types/ticket'
import {
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
} from '@/lib/ticket-config'
import {
  AlarmClockIcon,
  BellRingIcon,
  CheckCircle2Icon,
  CircleDollarSignIcon,
  CircleHelpIcon,
  InboxIcon,
  MessageSquareIcon,
  PackageOpenIcon,
  WrenchIcon,
  XCircleIcon,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

/**
 * Status and priority indicators. Color is never the only signal — every
 * badge carries an icon plus a text label.
 */

const STATUS_CONFIG: Record<
  TicketStatus,
  { variant: Parameters<typeof Badge>[0]['variant']; icon: React.ElementType }
> = {
  new: { variant: 'primary', icon: InboxIcon },
  open: { variant: 'warning', icon: MessageSquareIcon },
  pending: { variant: 'default', icon: AlarmClockIcon },
  needs_review: { variant: 'warning', icon: BellRingIcon },
  resolved: { variant: 'success', icon: CheckCircle2Icon },
  closed: { variant: 'neutral', icon: XCircleIcon },
}
// `needs_review` uses warning tint + bell; differentiate further via label.

const PRIORITY_CONFIG: Record<
  TicketPriority,
  { variant: Parameters<typeof Badge>[0]['variant']; icon: React.ElementType }
> = {
  urgent: { variant: 'danger', icon: BellRingIcon },
  high: { variant: 'warning', icon: AlarmClockIcon },
  normal: { variant: 'primary', icon: MessageSquareIcon },
  low: { variant: 'neutral', icon: CheckCircle2Icon },
}

const CATEGORY_CONFIG: Record<TicketCategory, React.ElementType> = {
  billing: CircleDollarSignIcon,
  delivery: PackageOpenIcon,
  technical: WrenchIcon,
  returns: PackageOpenIcon,
  general: CircleHelpIcon,
}

export function StatusBadge({
  status,
  className,
}: {
  status: TicketStatus
  className?: string
}) {
  const config = STATUS_CONFIG[status]
  const Icon = config.icon
  return (
    <Badge variant={config.variant} className={cn('gap-1 font-medium', className)} title={STATUS_LABELS[status]}>
      <Icon aria-hidden="true" className="shrink-0" />
      {STATUS_LABELS[status]}
    </Badge>
  )
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const config = PRIORITY_CONFIG[priority]
  const Icon = config.icon
  return (
    <Badge
      variant={config.variant}
      title={`${PRIORITY_LABELS[priority]} priority`}
    >
      <Icon aria-hidden="true" />
      {PRIORITY_LABELS[priority]}
    </Badge>
  )
}

/** Subtle grey category chip with a category-specific icon. */
export function CategoryBadge({ category }: { category: TicketCategory }) {
  const Icon = CATEGORY_CONFIG[category]
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <Icon aria-hidden="true" className="size-3.5 shrink-0 text-subtle-foreground" />
      {CATEGORY_LABELS[category]}
    </span>
  )
}
