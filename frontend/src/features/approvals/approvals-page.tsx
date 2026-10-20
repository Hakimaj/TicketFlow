import * as React from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  FilterX,
  Mail,
  RotateCcw,
  Send,
  ShieldAlert,
  ShieldCheck,
  User,
  X,
} from 'lucide-react'
import type { Ticket, TicketPriority } from '@/types/ticket'
import type { CustomerReply, ReplyState } from '@/types/reply'
import {
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
} from '@/lib/ticket-config'
import { formatDateTime, formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { DEMO_USER } from '@/data'
import { ticketService } from '@/services'
import { PageHeader } from '@/components/shared/page-header'
import { ConfirmDialog } from '@/components/shared/confirm-dialog'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/shared/states'
import {
  CategoryBadge,
  PriorityBadge,
} from '@/components/shared/ticket-badges'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { SearchInput } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

type FilterState = 'all' | ReplyState

const FILTER_STATES: FilterState[] = [
  'pending_approval',
  'approved',
  'changes_requested',
  'sent',
  'draft',
  'all',
]

function readStateFilter(params: URLSearchParams): FilterState {
  const value = params.get('state')
  return FILTER_STATES.find((state) => state === value) ?? 'pending_approval'
}

interface ReplyItem {
  reply: CustomerReply
  ticket: Ticket
}

function ReplyStateBadge({ state }: { state: ReplyState }) {
  switch (state) {
    case 'pending_approval':
      return (
        <Badge variant="warning" className="gap-1 font-medium text-2xs">
          <Clock className="size-3 shrink-0" aria-hidden="true" />
          Pending Approval
        </Badge>
      )
    case 'approved':
      return (
        <Badge variant="success" className="gap-1 font-medium text-2xs">
          <CheckCircle2 className="size-3 shrink-0" aria-hidden="true" />
          Approved · Ready to Send
        </Badge>
      )
    case 'changes_requested':
      return (
        <Badge variant="danger" className="gap-1 font-medium text-2xs">
          <ShieldAlert className="size-3 shrink-0" aria-hidden="true" />
          Changes Requested
        </Badge>
      )
    case 'sent':
      return (
        <Badge variant="primary" className="gap-1 font-medium text-2xs">
          <Send className="size-3 shrink-0" aria-hidden="true" />
          Sent (Demo)
        </Badge>
      )
    case 'draft':
    default:
      return (
        <Badge variant="neutral" className="gap-1 font-medium text-2xs">
          Draft
        </Badge>
      )
  }
}

export function ApprovalsPage() {
  const [items, setItems] = React.useState<ReplyItem[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<Error | null>(null)
  const [searchParams] = useSearchParams()

  // Filters — the page opens on the actionable review queue by default, or on
  // the state requested by a deep link (e.g. Analytics -> Sent (Demo)).
  const [stateFilter, setStateFilter] = React.useState<FilterState>(() =>
    readStateFilter(searchParams),
  )
  const [search, setSearch] = React.useState('')
  const [categoryFilter, setCategoryFilter] = React.useState<string>('all')
  const [priorityFilter, setPriorityFilter] = React.useState<string>('all')
  const [sortBy, setSortBy] = React.useState<'date_desc' | 'date_asc' | 'priority'>('date_desc')

  // Review Dialog State
  const [reviewItem, setReviewItem] = React.useState<ReplyItem | null>(null)
  const [isRequestingChanges, setIsRequestingChanges] = React.useState(false)
  const [feedbackText, setFeedbackText] = React.useState('')
  const [feedbackError, setFeedbackError] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [sendTarget, setSendTarget] = React.useState<ReplyItem | null>(null)

  // Notification Toast
  const [notification, setNotification] = React.useState<{
    message: string
    type: 'success' | 'error'
  } | null>(null)

  const showNotification = React.useCallback(
    (message: string, type: 'success' | 'error' = 'success') => {
      setNotification({ message, type })
    },
    [],
  )

  React.useEffect(() => {
    if (!notification) return
    if (notification.type === 'success') {
      const timer = window.setTimeout(() => setNotification(null), 4000)
      return () => window.clearTimeout(timer)
    }
  }, [notification])

  // Load data
  const loadData = React.useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true)
    setError(null)
    try {
      const allReplies = await ticketService.listAllReplies()
      setItems(allReplies)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load reply approvals.'))
    } finally {
      if (isInitial) setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadData(true)
  }, [loadData])

  // Subscribe to service changes
  React.useEffect(() => {
    const unsubscribe = ticketService.subscribe(() => {
      loadData(false)
    })
    return unsubscribe
  }, [loadData])

  // Counts by state
  const counts = React.useMemo(() => {
    const res: Record<FilterState, number> = {
      all: items.length,
      pending_approval: 0,
      approved: 0,
      changes_requested: 0,
      sent: 0,
      draft: 0,
    }
    for (const item of items) {
      res[item.reply.state] = (res[item.reply.state] || 0) + 1
    }
    return res
  }, [items])

  // Filtered & Sorted items
  const filteredItems = React.useMemo(() => {
    let list = [...items]

    if (stateFilter !== 'all') {
      list = list.filter((item) => item.reply.state === stateFilter)
    }

    if (categoryFilter !== 'all') {
      list = list.filter((item) => item.ticket.category === categoryFilter)
    }

    if (priorityFilter !== 'all') {
      list = list.filter((item) => item.ticket.priority === priorityFilter)
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter(
        (item) =>
          item.ticket.id.toLowerCase().includes(q) ||
          item.ticket.subject.toLowerCase().includes(q) ||
          item.ticket.requesterName.toLowerCase().includes(q) ||
          item.reply.authorName.toLowerCase().includes(q) ||
          item.reply.body.toLowerCase().includes(q),
      )
    }

    const priorityWeight: Record<TicketPriority, number> = {
      urgent: 4,
      high: 3,
      normal: 2,
      low: 1,
    }

    list.sort((a, b) => {
      if (sortBy === 'priority') {
        const diff = priorityWeight[b.ticket.priority] - priorityWeight[a.ticket.priority]
        if (diff !== 0) return diff
      }
      const timeA = new Date(a.reply.updatedAt).getTime()
      const timeB = new Date(b.reply.updatedAt).getTime()
      return sortBy === 'date_asc' ? timeA - timeB : timeB - timeA
    })

    return list
  }, [items, stateFilter, categoryFilter, priorityFilter, search, sortBy])

  // Review Actions
  async function handleApprove(replyId: string) {
    setIsSubmitting(true)
    try {
      await ticketService.approveReply(replyId, DEMO_USER)
      setReviewItem(null)
      showNotification('Customer reply approved. Ready for sending.')
    } catch (err) {
      showNotification(err instanceof Error ? err.message : 'Failed to approve reply.', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleRequestChanges() {
    if (!reviewItem) return
    const trimmed = feedbackText.trim()
    if (!trimmed) {
      setFeedbackError('Internal comments explaining requested revisions are mandatory.')
      return
    }

    setFeedbackError(null)
    setIsSubmitting(true)
    try {
      await ticketService.requestReplyChanges(reviewItem.reply.id, trimmed, DEMO_USER)
      setReviewItem(null)
      setIsRequestingChanges(false)
      setFeedbackText('')
      showNotification('Changes requested. The reply is back with its author for revision.')
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : 'Failed to request changes.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleMarkSent(replyId: string) {
    setIsSubmitting(true)
    try {
      await ticketService.markReplySent(replyId, DEMO_USER)
      showNotification('Customer reply marked as sent in demo mode. Ticket status set to Pending.')
    } catch (err) {
      showNotification(err instanceof Error ? err.message : 'Approval gate rejected send action.', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  function openReviewDialog(item: ReplyItem) {
    setReviewItem(item)
    setIsRequestingChanges(false)
    setFeedbackText('')
    setFeedbackError(null)
  }

  const hasFiltersApplied =
    stateFilter !== 'pending_approval' ||
    search.trim().length > 0 ||
    categoryFilter !== 'all' ||
    priorityFilter !== 'all'

  function resetFilters() {
    setStateFilter('pending_approval')
    setSearch('')
    setCategoryFilter('all')
    setPriorityFilter('all')
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reply Approvals"
        description="Supervise, review, and approve customer reply drafts before sending."
        breadcrumb={
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Link to="/tickets" className="hover:text-foreground">
              Tickets
            </Link>
            <span>/</span>
            <span className="text-foreground font-medium">Approvals</span>
          </div>
        }
      />

      {/* Notification Toast */}
      {notification ? (
        <div
          role="status"
          aria-live="polite"
          className={cn(
            'flex items-center justify-between gap-3 rounded-lg border px-4 py-2.5 text-xs font-medium shadow-xs transition-all',
            notification.type === 'success'
              ? 'border-success/30 bg-success-tint text-success'
              : 'border-danger/30 bg-danger-tint text-danger',
          )}
        >
          <div className="flex items-center gap-2">
            {notification.type === 'success' ? (
              <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
            ) : (
              <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
            )}
            <span>{notification.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setNotification(null)}
            className="rounded p-0.5 opacity-70 hover:opacity-100 focus:outline-none"
            aria-label="Dismiss message"
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {/* State Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border pb-3">
        {(
          [
            { id: 'all', label: 'All Replies', count: counts.all },
            { id: 'pending_approval', label: 'Pending Approval', count: counts.pending_approval },
            { id: 'approved', label: 'Approved', count: counts.approved },
            { id: 'changes_requested', label: 'Changes Requested', count: counts.changes_requested },
            { id: 'sent', label: 'Sent (Demo)', count: counts.sent },
          ] as const
        ).map((tab) => {
          const isActive = stateFilter === tab.id
          const isPending = tab.id === 'pending_approval' && tab.count > 0

          return (
            <button
              key={tab.id}
              type="button"
              aria-pressed={isActive}
              onClick={() => setStateFilter(tab.id)}
              className={cn(
                'inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground shadow-xs'
                  : 'bg-card text-muted-foreground hover:bg-muted hover:text-foreground border border-border/80',
              )}
            >
              <span>{tab.label}</span>
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.2 font-mono text-2xs',
                  isActive
                    ? 'bg-primary-foreground/20 text-primary-foreground'
                    : isPending
                      ? 'bg-warning-tint text-warning font-semibold'
                      : 'bg-muted text-subtle-foreground',
                )}
              >
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Search & Filter Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <SearchInput
            aria-label="Search reply approvals"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ticket ID, customer, author, reply text…"
            className="w-full sm:w-72"
          />

          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-40 text-xs" aria-label="Filter by category">
              <SelectValue placeholder="All Categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              {TICKET_CATEGORIES.map((cat) => (
                <SelectItem key={cat} value={cat}>
                  {CATEGORY_LABELS[cat]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={priorityFilter} onValueChange={setPriorityFilter}>
            <SelectTrigger className="w-36 text-xs" aria-label="Filter by priority">
              <SelectValue placeholder="All Priorities" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Priorities</SelectItem>
              {TICKET_PRIORITIES.map((p) => (
                <SelectItem key={p} value={p}>
                  {PRIORITY_LABELS[p]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {hasFiltersApplied ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              className="gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <FilterX className="size-3.5" aria-hidden="true" />
              Reset filters
            </Button>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-2xs text-muted-foreground">Sort:</span>
          <Select
            value={sortBy}
            onValueChange={(val) => setSortBy(val as 'date_desc' | 'date_asc' | 'priority')}
          >
            <SelectTrigger className="w-40 text-xs" aria-label="Sort replies">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date_desc">Newest First</SelectItem>
              <SelectItem value="date_asc">Oldest First</SelectItem>
              <SelectItem value="priority">Priority (Urgent first)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Main List */}
      {loading ? (
        <ListSkeleton rows={4} label="Loading reply approvals" />
      ) : error ? (
        <ErrorState
          title="Could not load reply queue"
          description={error.message}
          onRetry={() => loadData(true)}
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          title={
            stateFilter === 'pending_approval'
              ? 'Approvals queue is clear'
              : 'No replies match your criteria'
          }
          description={
            stateFilter === 'pending_approval'
              ? 'There are currently no customer replies waiting for supervisor approval.'
              : 'Try clearing the active filters or searching with different terms.'
          }
          action={
            hasFiltersApplied ? (
              <Button variant="outline" size="sm" onClick={resetFilters}>
                Clear filters
              </Button>
            ) : null
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredItems.map(({ reply, ticket }) => {
            const isPending = reply.state === 'pending_approval'
            const isApproved = reply.state === 'approved'
            const isChanges = reply.state === 'changes_requested'

            return (
              <Card
                key={reply.id}
                className={cn(
                  'border transition-shadow hover:shadow-xs',
                  isPending
                    ? 'border-warning/50 bg-card'
                    : isApproved
                      ? 'border-success/40 bg-card'
                      : isChanges
                        ? 'border-danger/30 bg-card'
                        : 'border-border bg-card',
                )}
              >
                <div className="p-4 sm:p-5">
                  {/* Top line: Badges & Identifiers */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-border/60">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/tickets/${ticket.id}`}
                        className="font-mono text-xs font-semibold text-primary hover:underline"
                      >
                        {ticket.id}
                      </Link>
                      <ReplyStateBadge state={reply.state} />
                      <Badge variant="outline" className="font-mono text-2xs py-0">
                        v{reply.version}
                      </Badge>
                      <PriorityBadge priority={ticket.priority} />
                      <CategoryBadge category={ticket.category} />
                    </div>

                    <div className="flex items-center gap-2 text-2xs text-muted-foreground">
                      <Clock className="size-3" aria-hidden="true" />
                      <span>Updated {formatRelativeTime(reply.updatedAt)}</span>
                    </div>
                  </div>

                  {/* Middle content: Ticket Subject & Recipient Info */}
                  <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div className="md:col-span-2 space-y-1.5">
                      <Link
                        to={`/tickets/${ticket.id}`}
                        className="text-sm font-semibold text-foreground hover:text-primary transition-colors line-clamp-1"
                      >
                        {ticket.subject}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        Customer: <span className="font-medium text-foreground">{ticket.requesterName}</span> &lt;{ticket.requesterEmail}&gt;
                      </p>

                      {/* Reply body preview */}
                      <div className="mt-2.5 rounded border border-border/80 bg-background/60 p-3 text-xs leading-relaxed text-foreground">
                        <p className="line-clamp-3 whitespace-pre-line font-sans">
                          {reply.body}
                        </p>
                      </div>

                      {/* Reviewer feedback banner if changes requested */}
                      {isChanges && reply.reviewerFeedback ? (
                        <div className="mt-2 rounded border border-danger/30 bg-danger-tint/30 p-2.5 text-xs text-danger">
                          <div className="flex items-start gap-1.5">
                            <ShieldAlert className="size-4 shrink-0 mt-0.5" aria-hidden="true" />
                            <div>
                              <span className="font-semibold">Supervisor Feedback ({reply.reviewerName}): </span>
                              <span>&ldquo;{reply.reviewerFeedback}&rdquo;</span>
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>

                    {/* Metadata column & actions */}
                    <div className="flex flex-col justify-between rounded-lg border border-border/60 bg-card-muted/30 p-3 text-xs">
                      <div className="space-y-2 text-2xs text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                          <User className="size-3.5 text-subtle-foreground" aria-hidden="true" />
                          <span>Author: <strong className="text-foreground">{reply.authorName}</strong></span>
                        </div>
                        {reply.submittedAt ? (
                          <div className="flex items-center gap-1.5">
                            <Clock className="size-3.5 text-subtle-foreground" aria-hidden="true" />
                            <span>Submitted: {formatRelativeTime(reply.submittedAt)}</span>
                          </div>
                        ) : null}
                        {reply.reviewedAt && reply.reviewerName ? (
                          <div className="flex items-center gap-1.5">
                            <ShieldCheck className="size-3.5 text-subtle-foreground" aria-hidden="true" />
                            <span>Reviewed by: <strong className="text-foreground">{reply.reviewerName}</strong></span>
                          </div>
                        ) : null}
                        {reply.sentAt ? (
                          <div className="flex items-center gap-1.5 text-primary">
                            <Send className="size-3.5" aria-hidden="true" />
                            <span>Sent in demo mode</span>
                          </div>
                        ) : null}
                      </div>

                      {/* Action buttons */}
                      <div className="mt-4 flex flex-col gap-2 pt-2 border-t border-border/60">
                        {isPending ? (
                          <Button
                            size="sm"
                            onClick={() => openReviewDialog({ reply, ticket })}
                            className="w-full gap-1.5 text-xs font-semibold"
                          >
                            <ShieldCheck className="size-3.5" aria-hidden="true" />
                            Review & Decide
                          </Button>
                        ) : isApproved ? (
                          <Button
                            size="sm"
                            onClick={() => setSendTarget({ reply, ticket })}
                            disabled={isSubmitting}
                            className="w-full gap-1.5 text-xs bg-success hover:bg-success/90 text-white"
                          >
                            <Send className="size-3.5" aria-hidden="true" />
                            Mark as Sent (Demo)
                          </Button>
                        ) : null}

                        <Button
                          variant="outline"
                          size="sm"
                          asChild
                          className="w-full gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                        >
                          <Link to={`/tickets/${ticket.id}`}>
                            <span>Open ticket</span>
                            <ArrowRight className="size-3" aria-hidden="true" />
                          </Link>
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* ================= SUPERVISOR REVIEW MODAL ================= */}
      {reviewItem ? (
        <Dialog open={Boolean(reviewItem)} onOpenChange={(open) => !open && setReviewItem(null)}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-5 text-primary" aria-hidden="true" />
                <DialogTitle>Supervisor Reply Review</DialogTitle>
              </div>
              <DialogDescription>
                Review the proposed customer response for ticket{' '}
                <strong className="text-foreground font-mono">{reviewItem.ticket.id}</strong> before authorizing it for delivery.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2 text-xs">
              {/* Ticket Summary & Customer Context */}
              <div className="rounded-lg border border-border bg-card-muted/40 p-3.5 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-foreground text-sm">
                    {reviewItem.ticket.subject}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <PriorityBadge priority={reviewItem.ticket.priority} />
                    <CategoryBadge category={reviewItem.ticket.category} />
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-4 text-muted-foreground text-2xs">
                  <span>Customer: <strong className="text-foreground">{reviewItem.ticket.requesterName}</strong></span>
                  <span>Email: {reviewItem.ticket.requesterEmail}</span>
                  <span>Received: {formatDateTime(reviewItem.ticket.createdAt)}</span>
                </div>
                <div className="mt-1 rounded border border-border/80 bg-background/80 p-2.5 text-muted-foreground leading-relaxed">
                  <p className="font-semibold text-2xs text-foreground uppercase tracking-wide mb-1">
                    Customer Inquiry:
                  </p>
                  <p className="line-clamp-4 whitespace-pre-line text-xs text-foreground">
                    {reviewItem.ticket.description}
                  </p>
                </div>
              </div>

              {/* Proposed Reply Content */}
              <div className="rounded-lg border border-primary/30 bg-primary-tint/15 p-4 space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-primary/20 pb-2">
                  <div className="flex items-center gap-2">
                    <Mail className="size-4 text-primary" aria-hidden="true" />
                    <span className="font-semibold text-foreground">
                      Proposed Customer Reply (v{reviewItem.reply.version})
                    </span>
                  </div>
                  <span className="text-2xs text-muted-foreground">
                    Drafted by <strong className="text-foreground">{reviewItem.reply.authorName}</strong>
                  </span>
                </div>
                <div className="rounded bg-background p-3.5 border border-border font-sans text-xs leading-relaxed text-foreground whitespace-pre-line">
                  {reviewItem.reply.body}
                </div>
                <div className="flex items-center justify-between text-2xs text-muted-foreground pt-1">
                  <span>{reviewItem.reply.body.length} characters · {reviewItem.reply.body.split(/\s+/).filter(Boolean).length} words</span>
                  <span className="text-subtle-foreground">Submitted: {reviewItem.reply.submittedAt ? formatDateTime(reviewItem.reply.submittedAt) : ''}</span>
                </div>
              </div>

              {/* If in Request Changes mode: show comments field */}
              {isRequestingChanges ? (
                <div className="rounded-lg border border-danger/40 bg-danger-tint/30 p-3.5 space-y-2">
                  <div className="flex items-center gap-2 text-danger font-semibold">
                    <RotateCcw className="size-4" aria-hidden="true" />
                    <span>Explain Required Changes</span>
                  </div>
                  <p className="text-2xs text-muted-foreground">
                    These comments will be displayed to {reviewItem.reply.authorName} on the ticket page. Feedback is mandatory.
                  </p>
                  <Textarea
                    aria-label="Internal reviewer feedback"
                    value={feedbackText}
                    onChange={(e) => {
                      setFeedbackText(e.target.value)
                      if (feedbackError) setFeedbackError(null)
                    }}
                    placeholder="E.g., Please clarify our 14-day return window and do not promise a direct courier pickup without warehouse approval."
                    rows={3}
                    className={cn(feedbackError && 'border-danger focus-visible:border-danger')}
                  />
                  {feedbackError ? (
                    <p role="alert" className="text-xs font-medium text-danger">
                      {feedbackError}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>

            <DialogFooter className="gap-2 sm:justify-between border-t border-border pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setReviewItem(null)
                  setIsRequestingChanges(false)
                }}
                disabled={isSubmitting}
              >
                Cancel
              </Button>

              <div className="flex items-center gap-2">
                {!isRequestingChanges ? (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsRequestingChanges(true)}
                      disabled={isSubmitting}
                      className="border-danger/40 text-danger hover:bg-danger-tint"
                    >
                      <RotateCcw className="size-3.5 mr-1" aria-hidden="true" />
                      Request Changes…
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleApprove(reviewItem.reply.id)}
                      disabled={isSubmitting}
                      className="bg-success hover:bg-success/90 text-white gap-1.5"
                    >
                      <Check className="size-3.5" aria-hidden="true" />
                      {isSubmitting ? 'Approving…' : 'Approve Reply'}
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setIsRequestingChanges(false)}
                      disabled={isSubmitting}
                    >
                      Back
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={handleRequestChanges}
                      disabled={isSubmitting}
                      className="gap-1.5"
                    >
                      <RotateCcw className="size-3.5" aria-hidden="true" />
                      {isSubmitting ? 'Submitting…' : 'Submit Revisions Request'}
                    </Button>
                  </>
                )}
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}

      <ConfirmDialog
        open={Boolean(sendTarget)}
        onOpenChange={(open) => {
          if (!open) setSendTarget(null)
        }}
        title="Mark this reply as sent?"
        description={
          sendTarget
            ? `This records reply v${sendTarget.reply.version} for ${sendTarget.ticket.id} as sent by ${DEMO_USER.name} (demo mode). No email is actually delivered.`
            : undefined
        }
        confirmLabel="Mark as Sent (Demo)"
        onConfirm={() => {
          if (sendTarget) void handleMarkSent(sendTarget.reply.id)
        }}
      />
    </div>
  )
}

