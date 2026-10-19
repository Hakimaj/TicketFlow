import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { PageHeader } from '@/components/shared/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { Button, buttonVariants } from '@/components/ui/button'
import { EmptyState, ErrorState } from '@/components/shared/states'
import { CategoryBadge, PriorityBadge, StatusBadge } from '@/components/shared/ticket-badges'
import { Skeleton } from '@/components/ui/misc'
import { CHANNEL_LABELS } from '@/lib/ticket-config'
import { formatDateTime, formatRelativeTime } from '@/lib/format'
import { ticketService } from '@/services'
import { cn } from '@/lib/utils'

/**
 * Read-only summary of a single ticket that navigates to the Phase 2 full
 * conversation view. Deliberately minimal — real ticket editing, replies
 * and approvals are later phases; this just proves identity routing works.
 */
export function TicketDetailPlaceholder() {
  const { ticketId } = useParams<{ ticketId: string }>()
  const [ticket, setTicket] = React.useState<Awaited<ReturnType<typeof ticketService.getTicket>>>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<Error | null>(null)

  React.useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    ticketService
      .getTicket(ticketId ?? '')
      .then((result) => {
        if (cancelled) return
        setTicket(result)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err : new Error('Failed to load ticket'))
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [ticketId])

  return (
    <div>
      <PageHeader
        breadcrumb={
          <Link to="/tickets" className="hover:text-foreground hover:underline">
            Tickets
          </Link>
        }
        title={ticketId ? `Ticket ${ticketId}` : 'Ticket'}
        description="Phase 2 will deliver the full conversation, draft replies and approvals. Opening a ticket by ID works in this phase."
      />
      <Card>
        {loading ? (
          <div className="space-y-3 p-4" role="status" aria-busy="true">
            <span className="sr-only">Loading…</span>
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : error ? (
          <ErrorState onRetry={() => window.location.reload()} />
        ) : !ticket ? (
          <EmptyState
            title={`Ticket ${ticketId ?? ''} was not found`}
            description="Check the ticket number, or browse the queues from the All Tickets page."
            action={
              <Button variant="outline" size="sm" asChild>
                <Link to="/tickets">
                  <ArrowLeft aria-hidden="true" />
                  Back to tickets
                </Link>
              </Button>
            }
          />
        ) : (
          <CardContent className="pt-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={ticket.status} />
              <PriorityBadge priority={ticket.priority} />
              <CategoryBadge category={ticket.category} />
            </div>
            <h2 className="mt-3 text-base font-semibold text-foreground">
              {ticket.subject}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              {ticket.description}
            </p>
            <dl className="mt-4 grid gap-x-6 gap-y-2 border-t border-border pt-3 text-sm sm:grid-cols-2">
              <div className="flex justify-between gap-3 sm:block">
                <dt className="text-xs text-subtle-foreground">Requester</dt>
                <dd className="text-foreground">
                  {ticket.requesterName}{' '}
                  <span className="text-xs text-muted-foreground">({ticket.requesterEmail})</span>
                </dd>
              </div>
              <div className="flex justify-between gap-3 sm:block">
                <dt className="text-xs text-subtle-foreground">Channel</dt>
                <dd className="text-foreground">{CHANNEL_LABELS[ticket.channel]}</dd>
              </div>
              <div className="flex justify-between gap-3 sm:block">
                <dt className="text-xs text-subtle-foreground">Received</dt>
                <dd className="text-foreground">
                  {formatDateTime(ticket.createdAt)} (
                  {formatRelativeTime(ticket.createdAt)})
                </dd>
              </div>
              <div className="flex justify-between gap-3 sm:block">
                <dt className="text-xs text-subtle-foreground">Last updated</dt>
                <dd className="text-foreground">{formatDateTime(ticket.updatedAt)}</dd>
              </div>
            </dl>
            <div className="mt-5 flex flex-wrap gap-2">
              <Link to="/tickets" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                <ArrowLeft aria-hidden="true" />
                Back to tickets
              </Link>
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  )
}
