import * as React from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  Clock,
  FileText,
  Lock,
  MessageSquare,
  RotateCcw,
  Send,
  Shuffle,
  StickyNote,
  UserCheck,
  UserPlus,
  X,
} from 'lucide-react'
import type {
  Agent,
  Ticket,
  TicketActivity,
  TicketCategory,
  TicketPriority,
  TicketStatus,
} from '@/types/ticket'
import type { CustomerReply } from '@/types/reply'
import { ReplyComposer } from './reply-composer'
import {
  CATEGORY_LABELS,
  CHANNEL_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
  TEAM_LABELS,
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
  TICKET_STATUSES,
} from '@/lib/ticket-config'
import { formatDateTime, formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { ticketService, TicketServiceError } from '@/services'
import { DEMO_USER } from '@/data'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Avatar, Skeleton } from '@/components/ui/misc'
import { Badge } from '@/components/ui/badge'
import { EmptyState, ErrorState } from '@/components/shared/states'
import {
  CategoryBadge,
  PriorityBadge,
  StatusBadge,
} from '@/components/shared/ticket-badges'

function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const [ticket, setTicket] = React.useState<Ticket | null>(null)
  const [activities, setActivities] = React.useState<TicketActivity[]>([])
  const [replies, setReplies] = React.useState<CustomerReply[]>([])
  const [agents, setAgents] = React.useState<Agent[]>([])
  const [adjacent, setAdjacent] = React.useState<{
    prevId: string | null
    nextId: string | null
  }>({ prevId: null, nextId: null })

  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<Error | null>(null)

  // Internal note composer state
  const [noteContent, setNoteContent] = React.useState('')
  const [noteError, setNoteError] = React.useState<string | null>(null)
  const [submittingNote, setSubmittingNote] = React.useState(false)

  // Triage update in-flight state
  const [updatingField, setUpdatingField] = React.useState<string | null>(null)

  // Feedback notifications
  const [feedback, setFeedback] = React.useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)

  const returnTo = (location.state as { returnTo?: string })?.returnTo ?? '/tickets'
  const returnLabel = returnTo.startsWith('/activity')
    ? 'Activity Logs'
    : returnTo.startsWith('/approvals')
      ? 'Reply Approvals'
      : 'Tickets'

  const showFeedback = React.useCallback(
    (message: string, type: 'success' | 'error' = 'success') => {
      setFeedback({ message, type })
    },
    [],
  )

  // Auto-dismiss success feedback after 4 seconds
  React.useEffect(() => {
    if (!feedback) return
    if (feedback.type === 'success') {
      const timer = window.setTimeout(() => setFeedback(null), 4000)
      return () => window.clearTimeout(timer)
    }
  }, [feedback])

  // Load ticket, agents, activities, adjacent IDs and replies
  const loadTicketData = React.useCallback(
    async (id: string, isInitial = false) => {
      if (isInitial) {
        setLoading(true)
      }
      setError(null)
      try {
        const [ticketData, activityData, agentList, adjacentData, replyList] =
          await Promise.all([
            ticketService.getTicket(id),
            ticketService.getTicketActivities(id),
            ticketService.listAgents(),
            ticketService.getAdjacentTicketIds(id),
            ticketService.getReplies(id),
          ])

        setTicket(ticketData)
        setActivities(activityData)
        setAgents(agentList)
        setAdjacent(adjacentData)
        setReplies(replyList)
      } catch (err) {
        setError(
          err instanceof Error
            ? err
            : new TicketServiceError('Failed to load ticket details'),
        )
      } finally {
        if (isInitial) {
          setLoading(false)
        }
      }
    },
    [],
  )

  React.useEffect(() => {
    if (!ticketId) return
    loadTicketData(ticketId, true)
  }, [ticketId, loadTicketData])

  // Reactive listener for mutations across views
  React.useEffect(() => {
    if (!ticketId) return
    const unsubscribe = ticketService.subscribe(() => {
      loadTicketData(ticketId, false)
    })
    return unsubscribe
  }, [ticketId, loadTicketData])

  // Triage actions
  async function handleStatusChange(newStatus: string) {
    if (!ticket || newStatus === ticket.status) return
    const targetStatus = newStatus as TicketStatus
    setUpdatingField('status')
    try {
      const updated = await ticketService.updateStatus(ticket.id, targetStatus)
      setTicket(updated)
      showFeedback(`Ticket status updated to ${STATUS_LABELS[targetStatus]}.`)
    } catch (err) {
      showFeedback(
        err instanceof Error ? err.message : 'Failed to update status.',
        'error',
      )
    } finally {
      setUpdatingField(null)
    }
  }

  async function handlePriorityChange(newPriority: string) {
    if (!ticket || newPriority === ticket.priority) return
    const targetPriority = newPriority as TicketPriority
    setUpdatingField('priority')
    try {
      const updated = await ticketService.updatePriority(
        ticket.id,
        targetPriority,
      )
      setTicket(updated)
      showFeedback(
        `Ticket priority updated to ${PRIORITY_LABELS[targetPriority]}.`,
      )
    } catch (err) {
      showFeedback(
        err instanceof Error ? err.message : 'Failed to update priority.',
        'error',
      )
    } finally {
      setUpdatingField(null)
    }
  }

  async function handleCategoryChange(newCategory: string) {
    if (!ticket || newCategory === ticket.category) return
    const targetCategory = newCategory as TicketCategory
    setUpdatingField('category')
    try {
      const updated = await ticketService.updateCategory(
        ticket.id,
        targetCategory,
      )
      setTicket(updated)
      showFeedback(
        `Category updated to ${CATEGORY_LABELS[targetCategory]} (routed to ${TEAM_LABELS[updated.assignedTeam ?? 'customer_support']}).`,
      )
    } catch (err) {
      showFeedback(
        err instanceof Error ? err.message : 'Failed to update category.',
        'error',
      )
    } finally {
      setUpdatingField(null)
    }
  }

  async function handleAssignmentChange(newAgentId: string) {
    if (!ticket) return
    const targetAgentId = newAgentId === 'unassigned' ? null : newAgentId
    if (targetAgentId === ticket.assignedAgentId) return

    setUpdatingField('assignment')
    try {
      const updated = await ticketService.assignTicket(ticket.id, targetAgentId)
      setTicket(updated)
      const agent = targetAgentId
        ? agents.find((a) => a.id === targetAgentId)
        : null
      showFeedback(
        agent
          ? `Ticket assigned to ${agent.name}.`
          : 'Ticket unassigned.',
      )
    } catch (err) {
      showFeedback(
        err instanceof Error ? err.message : 'Failed to update assignment.',
        'error',
      )
    } finally {
      setUpdatingField(null)
    }
  }

  async function handleAddNote(e: React.FormEvent) {
    e.preventDefault()
    if (!ticket) return

    const trimmed = noteContent.trim()
    if (!trimmed) {
      setNoteError('Internal note cannot be empty. Please enter some text.')
      return
    }

    setNoteError(null)
    setSubmittingNote(true)
    try {
      await ticketService.addInternalNote(ticket.id, trimmed, DEMO_USER)
      setNoteContent('')
      showFeedback('Internal note added to activity timeline.')
    } catch (err) {
      setNoteError(
        err instanceof Error ? err.message : 'Failed to save internal note.',
      )
    } finally {
      setSubmittingNote(false)
    }
  }

  function navigateAdjacent(targetId: string | null) {
    if (!targetId) return
    navigate(`/tickets/${targetId}`, {
      state: { returnTo },
    })
  }

  if (loading) {
    return (
      <div className="space-y-6" role="status" aria-busy="true">
        <span className="sr-only">Loading ticket details…</span>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-7 w-72" />
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-9 w-28" />
            <Skeleton className="h-9 w-20" />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Skeleton className="h-64 w-full rounded-lg" />
            <Skeleton className="h-44 w-full rounded-lg" />
            <Skeleton className="h-72 w-full rounded-lg" />
          </div>
          <div className="space-y-6 lg:col-span-1">
            <Skeleton className="h-80 w-full rounded-lg" />
            <Skeleton className="h-64 w-full rounded-lg" />
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Link
          to={returnTo}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Back to {returnLabel}
        </Link>
        <ErrorState
          title="Ticket could not be loaded"
          description={error.message}
          onRetry={() => ticketId && loadTicketData(ticketId, true)}
        />
      </div>
    )
  }

  if (!ticket) {
    return (
      <div className="space-y-4">
        <EmptyState
          title={`Ticket ${ticketId ?? ''} was not found`}
          description="Check the ticket number or return to the active queue."
          action={
            <Button variant="outline" size="sm" asChild>
              <Link to={returnTo}>
                <ArrowLeft aria-hidden="true" />
                Back to {returnLabel}
              </Link>
            </Button>
          }
        />
      </div>
    )
  }

  const assignedAgent = ticket.assignedAgentId
    ? agents.find((a) => a.id === ticket.assignedAgentId)
    : null

  const isAssignedToMe = ticket.assignedAgentId === DEMO_USER.id

  return (
    <div className="space-y-6">
      {/* ------------------ Breadcrumb & Navigation Bar ------------------ */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Link
              to={returnTo}
              className="inline-flex items-center gap-1 font-medium transition-colors hover:text-foreground hover:underline"
            >
              <ArrowLeft className="size-3" aria-hidden="true" />
              {returnLabel}
            </Link>
            <span aria-hidden="true" className="text-subtle-foreground">
              /
            </span>
            <span className="font-mono font-medium text-foreground">
              {ticket.id}
            </span>
          </nav>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-semibold text-muted-foreground tabular-nums">
              {ticket.id}
            </span>
            <h1 className="text-lg font-semibold tracking-tight text-foreground sm:text-xl">
              {ticket.subject}
            </h1>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
            <CategoryBadge category={ticket.category} />
            {ticket.assignedTeam ? (
              <Badge variant="outline" className="text-2xs text-subtle-foreground font-normal">
                {TEAM_LABELS[ticket.assignedTeam]}
              </Badge>
            ) : null}
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex shrink-0 items-center gap-2">
          <div className="flex items-center rounded-md border border-border bg-card p-0.5 shadow-xs">
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              disabled={!adjacent.prevId}
              onClick={() => navigateAdjacent(adjacent.prevId)}
              title={adjacent.prevId ? `Previous ticket (${adjacent.prevId})` : 'First ticket in queue'}
              aria-label="Previous ticket"
            >
              <ChevronLeft className="size-4" aria-hidden="true" />
            </Button>
            <span aria-hidden="true" className="h-4 w-px bg-border" />
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              disabled={!adjacent.nextId}
              onClick={() => navigateAdjacent(adjacent.nextId)}
              title={adjacent.nextId ? `Next ticket (${adjacent.nextId})` : 'Last ticket in queue'}
              aria-label="Next ticket"
            >
              <ChevronRight className="size-4" aria-hidden="true" />
            </Button>
          </div>

          <Button variant="outline" size="sm" asChild>
            <Link to={returnTo}>
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              Back to {returnLabel}
            </Link>
          </Button>
        </div>
      </div>

      {/* ------------------ Inline Feedback Toast ------------------ */}
      {feedback ? (
        <div
          role="status"
          aria-live="polite"
          className={cn(
            'flex items-center justify-between gap-3 rounded-lg border px-4 py-2.5 text-xs font-medium shadow-xs transition-all',
            feedback.type === 'success'
              ? 'border-success/30 bg-success-tint text-success'
              : 'border-danger/30 bg-danger-tint text-danger',
          )}
        >
          <div className="flex items-center gap-2">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
            ) : (
              <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="rounded p-0.5 opacity-70 hover:opacity-100 focus:outline-none"
            aria-label="Dismiss feedback"
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {/* ------------------ Two-Column Main Content Grid ------------------ */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ================= LEFT COLUMN: Customer Inquiry & Workspace ================= */}
        <div className="space-y-6 lg:col-span-2">
          {/* 1. Customer Message Card */}
          <Card className="overflow-hidden border-border bg-card shadow-xs">
            <CardHeader className="border-b border-border bg-card-muted/60 px-5 py-3.5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Avatar initials={initials(ticket.requesterName)} size="default" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-foreground">
                        {ticket.requesterName}
                      </span>
                      <Badge variant="primary" className="text-2xs py-0">
                        Customer
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {ticket.requesterEmail}
                    </p>
                  </div>
                </div>

                <div className="text-right text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5 font-medium text-foreground">
                    <Clock className="size-3 text-subtle-foreground" aria-hidden="true" />
                    <span>{formatDateTime(ticket.createdAt)}</span>
                  </div>
                  <p className="text-2xs text-subtle-foreground">
                    {formatRelativeTime(ticket.createdAt)} · via {CHANNEL_LABELS[ticket.channel]}
                  </p>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4 p-5">
              {/* Optional Triage Review Note */}
              {ticket.reviewNote ? (
                <div className="rounded-md border border-warning/40 bg-warning-tint/50 p-3.5 text-xs">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
                    <div className="space-y-1">
                      <p className="font-semibold text-foreground">
                        Automated Triage Note
                      </p>
                      <p className="leading-relaxed text-muted-foreground">
                        {ticket.reviewNote}
                      </p>
                      {(ticket.suggestedCategory || ticket.suggestedPriority) ? (
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 pt-1 text-2xs text-subtle-foreground">
                          <span>Suggestions:</span>
                          {ticket.suggestedCategory ? (
                            <CategoryBadge category={ticket.suggestedCategory} />
                          ) : null}
                          {ticket.suggestedPriority ? (
                            <PriorityBadge priority={ticket.suggestedPriority} />
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Customer message body */}
              <div className="rounded-md border border-border/60 bg-background/50 p-4">
                <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
                  {ticket.description}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* 2. Customer Reply Composer & Approval Workflow */}
          <ReplyComposer
            ticket={ticket}
            replies={replies}
            onReplyUpdated={() => loadTicketData(ticket.id, false)}
            showFeedback={showFeedback}
          />

          {/* 3. Internal Workspace & Notes Composer */}
          <Card className="border-warning/30 bg-card shadow-xs">
            <CardHeader className="border-b border-warning/20 bg-warning-tint/20 px-5 py-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Lock className="size-4 text-warning" aria-hidden="true" />
                  <CardTitle className="text-sm font-semibold text-foreground">
                    Internal Workspace
                  </CardTitle>
                </div>
                <Badge variant="outline" className="border-warning/40 bg-card text-2xs text-foreground font-medium">
                  Staff Only — Never visible to customer
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-5">
              <form onSubmit={handleAddNote} className="space-y-3">
                <div className="space-y-1.5">
                  <label htmlFor="internal-note" className="text-xs font-medium text-foreground">
                    Add internal note
                  </label>
                  <Textarea
                    id="internal-note"
                    value={noteContent}
                    onChange={(e) => {
                      setNoteContent(e.target.value)
                      if (noteError) setNoteError(null)
                    }}
                    placeholder="Document your findings, customer communication, or internal handoff instructions…"
                    rows={3}
                    aria-describedby="internal-note-help"
                    disabled={submittingNote}
                    className={cn(noteError && 'border-danger focus-visible:border-danger')}
                  />
                  <div className="flex items-center justify-between text-2xs text-subtle-foreground">
                    <span id="internal-note-help">
                      Notes are recorded in the audit trail as {DEMO_USER.name} (Demo user).
                    </span>
                    <span>{noteContent.length} characters</span>
                  </div>
                </div>

                {noteError ? (
                  <p role="alert" className="text-xs font-medium text-danger">
                    {noteError}
                  </p>
                ) : null}

                <div className="flex justify-end gap-2">
                  <Button
                    type="submit"
                    size="sm"
                    disabled={submittingNote || !noteContent.trim()}
                    className="gap-1.5"
                  >
                    <StickyNote className="size-3.5" aria-hidden="true" />
                    {submittingNote ? 'Saving note…' : 'Add internal note'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* 4. Chronological Activity & Notes History */}
          <Card className="border-border shadow-xs">
            <CardHeader className="border-b border-border px-5 py-3.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MessageSquare className="size-4 text-primary" aria-hidden="true" />
                  <CardTitle className="text-sm font-semibold text-foreground">
                    Activity & Conversation History
                  </CardTitle>
                </div>
                <span className="text-xs text-muted-foreground">
                  {activities.length} {activities.length === 1 ? 'event' : 'events'}
                </span>
              </div>
            </CardHeader>
            <CardContent className="p-5">
              {activities.length === 0 ? (
                <p className="py-4 text-center text-xs text-muted-foreground">
                  No activity recorded for this ticket yet.
                </p>
              ) : (
                <ol className="relative space-y-4 border-l border-border pl-6">
                  {activities.map((item) => {
                    const isNote = item.action === 'note_added' || item.isInternalNote
                    const isReplySent = item.action === 'replied_sent'
                    const isReplyApproved = item.action === 'reply_approved'
                    const isReplyChanges = item.action === 'reply_changes_requested'
                    const isReplySubmitted = item.action === 'reply_submitted'
                    const isReplyDraft = item.action === 'replied_draft'

                    return (
                      <li key={item.id} className="relative">
                        {/* Bullet / icon on line */}
                        <span
                          aria-hidden="true"
                          className={cn(
                            'absolute -left-[31px] top-1 flex size-6 items-center justify-center rounded-full border border-card shadow-xs [&_svg]:size-3',
                            isNote
                              ? 'bg-warning-tint text-warning border-warning/40'
                              : isReplySent
                                ? 'bg-primary-tint text-primary border-primary/40'
                                : isReplyApproved
                                  ? 'bg-success-tint text-success border-success/40'
                                  : isReplyChanges
                                    ? 'bg-danger-tint text-danger border-danger/40'
                                    : isReplySubmitted
                                      ? 'bg-primary-tint text-primary border-primary/40'
                                      : isReplyDraft
                                        ? 'bg-muted text-muted-foreground border-border'
                                        : item.action === 'resolved'
                                          ? 'bg-success-tint text-success border-success/40'
                                          : item.action === 'review_flagged'
                                            ? 'bg-warning-tint text-warning border-warning/40'
                                            : item.action === 'created'
                                              ? 'bg-primary-tint text-primary border-primary/40'
                                              : 'bg-muted text-muted-foreground border-border',
                          )}
                        >
                          {isNote ? (
                            <Lock aria-hidden="true" />
                          ) : isReplySent ? (
                            <Send aria-hidden="true" />
                          ) : isReplyApproved ? (
                            <CheckCircle2 aria-hidden="true" />
                          ) : isReplyChanges ? (
                            <RotateCcw aria-hidden="true" />
                          ) : isReplySubmitted ? (
                            <Clock aria-hidden="true" />
                          ) : isReplyDraft ? (
                            <FileText aria-hidden="true" />
                          ) : item.action === 'resolved' ? (
                            <CheckCircle2 aria-hidden="true" />
                          ) : item.action === 'assigned' ? (
                            <UserPlus aria-hidden="true" />
                          ) : item.action === 'created' ? (
                            <CircleDot aria-hidden="true" />
                          ) : (
                            <Shuffle aria-hidden="true" />
                          )}
                        </span>

                        {isNote ? (
                          /* Internal note card */
                          <div className="rounded-lg border border-warning/30 bg-warning-tint/25 p-3.5 shadow-xs">
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-warning/20 pb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-foreground">
                                  {item.actorName}
                                </span>
                                <Badge variant="outline" className="border-warning/50 bg-card text-2xs text-warning">
                                  Internal note
                                </Badge>
                              </div>
                              <time
                                dateTime={item.createdAt}
                                className="text-2xs text-muted-foreground"
                                title={formatDateTime(item.createdAt)}
                              >
                                {formatDateTime(item.createdAt)} ({formatRelativeTime(item.createdAt)})
                              </time>
                            </div>
                            <p className="mt-2.5 whitespace-pre-line text-sm leading-relaxed text-foreground">
                              {item.detail}
                            </p>
                          </div>
                        ) : isReplyChanges ? (
                          /* Changes requested card */
                          <div className="rounded-lg border border-danger/30 bg-danger-tint/25 p-3.5 shadow-xs">
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-danger/20 pb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-foreground">
                                  {item.actorName}
                                </span>
                                <Badge variant="outline" className="border-danger/50 bg-card text-2xs text-danger font-medium">
                                  Changes Requested
                                </Badge>
                              </div>
                              <time
                                dateTime={item.createdAt}
                                className="text-2xs text-muted-foreground"
                                title={formatDateTime(item.createdAt)}
                              >
                                {formatDateTime(item.createdAt)} ({formatRelativeTime(item.createdAt)})
                              </time>
                            </div>
                            <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-foreground">
                              {item.detail}
                            </p>
                          </div>
                        ) : isReplySent ? (
                          /* Reply sent card */
                          <div className="rounded-lg border border-primary/30 bg-primary-tint/20 p-3.5 shadow-xs">
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-primary/20 pb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-foreground">
                                  {item.actorName}
                                </span>
                                <Badge variant="primary" className="text-2xs">
                                  Customer Reply · Sent (Demo)
                                </Badge>
                              </div>
                              <time
                                dateTime={item.createdAt}
                                className="text-2xs text-muted-foreground"
                                title={formatDateTime(item.createdAt)}
                              >
                                {formatDateTime(item.createdAt)} ({formatRelativeTime(item.createdAt)})
                              </time>
                            </div>
                            <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-foreground">
                              {item.detail}
                            </p>
                          </div>
                        ) : (
                          /* Standard audit entry */
                          <div className="text-xs">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="font-semibold text-foreground">
                                {item.actorName}
                              </span>
                              <span className="text-muted-foreground">
                                {item.detail ?? item.action}
                              </span>
                              {isReplyApproved ? (
                                <Badge variant="outline" className="border-success/50 bg-success-tint text-2xs text-success font-medium py-0">
                                  Approved
                                </Badge>
                              ) : isReplySubmitted ? (
                                <Badge variant="outline" className="border-primary/40 bg-primary-tint text-2xs text-primary font-medium py-0">
                                  Pending Approval
                                </Badge>
                              ) : null}
                            </div>
                            <time
                              dateTime={item.createdAt}
                              className="mt-0.5 block text-2xs text-subtle-foreground"
                              title={formatDateTime(item.createdAt)}
                            >
                              {formatDateTime(item.createdAt)} · {formatRelativeTime(item.createdAt)}
                            </time>
                          </div>
                        )}
                      </li>
                    )
                  })}
                </ol>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ================= RIGHT COLUMN: Context & Triage Sidebar ================= */}
        <div className="space-y-6 lg:col-span-1">
          {/* Triage & Routing Controls */}
          <Card className="border-border shadow-xs">
            <CardHeader className="border-b border-border px-4 py-3">
              <CardTitle className="text-sm font-semibold text-foreground">
                Triage & Routing
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 p-4">
              {/* Status Selector */}
              <div className="space-y-1.5">
                <label
                  htmlFor="status-select"
                  className="flex items-center justify-between text-xs font-medium text-foreground"
                >
                  <span>Status</span>
                  {updatingField === 'status' ? (
                    <span className="text-2xs text-primary animate-pulse">Updating…</span>
                  ) : null}
                </label>
                <Select
                  value={ticket.status}
                  onValueChange={handleStatusChange}
                  disabled={Boolean(updatingField)}
                >
                  <SelectTrigger id="status-select" className="w-full">
                    <SelectValue>
                      <StatusBadge status={ticket.status} />
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {TICKET_STATUSES.map((status) => (
                      <SelectItem key={status} value={status}>
                        <StatusBadge status={status} />
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Priority Selector */}
              <div className="space-y-1.5">
                <label
                  htmlFor="priority-select"
                  className="flex items-center justify-between text-xs font-medium text-foreground"
                >
                  <span>Priority</span>
                  {updatingField === 'priority' ? (
                    <span className="text-2xs text-primary animate-pulse">Updating…</span>
                  ) : null}
                </label>
                <Select
                  value={ticket.priority}
                  onValueChange={handlePriorityChange}
                  disabled={Boolean(updatingField)}
                >
                  <SelectTrigger id="priority-select" className="w-full">
                    <SelectValue>
                      <PriorityBadge priority={ticket.priority} />
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {TICKET_PRIORITIES.map((priority) => (
                      <SelectItem key={priority} value={priority}>
                        <PriorityBadge priority={priority} />
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Category Selector */}
              <div className="space-y-1.5">
                <label
                  htmlFor="category-select"
                  className="flex items-center justify-between text-xs font-medium text-foreground"
                >
                  <span>Category</span>
                  {updatingField === 'category' ? (
                    <span className="text-2xs text-primary animate-pulse">Updating…</span>
                  ) : null}
                </label>
                <Select
                  value={ticket.category}
                  onValueChange={handleCategoryChange}
                  disabled={Boolean(updatingField)}
                >
                  <SelectTrigger id="category-select" className="w-full">
                    <SelectValue>
                      <CategoryBadge category={ticket.category} />
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {TICKET_CATEGORIES.map((category) => (
                      <SelectItem key={category} value={category}>
                        <CategoryBadge category={category} />
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Assignee Selector */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-medium text-foreground">
                  <label htmlFor="agent-select">Assigned Agent</label>
                  {updatingField === 'assignment' ? (
                    <span className="text-2xs text-primary animate-pulse">Updating…</span>
                  ) : null}
                </div>
                <Select
                  value={ticket.assignedAgentId ?? 'unassigned'}
                  onValueChange={handleAssignmentChange}
                  disabled={Boolean(updatingField)}
                >
                  <SelectTrigger id="agent-select" className="w-full">
                    <SelectValue>
                      {assignedAgent ? (
                        <span className="flex items-center gap-2">
                          <Avatar initials={initials(assignedAgent.name)} size="sm" />
                          <span className="truncate">
                            {assignedAgent.name}
                            {assignedAgent.isDemoUser ? ' (You)' : ''}
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">Unassigned</span>
                      )}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unassigned">
                      <span className="text-muted-foreground font-normal">
                        Unassigned
                      </span>
                    </SelectItem>
                    {agents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        <div className="flex items-center gap-2">
                          <Avatar initials={initials(agent.name)} size="sm" />
                          <span className="truncate font-medium">
                            {agent.name}
                            {agent.isDemoUser ? ' (You)' : ''}
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* Quick assign to me button */}
                {!isAssignedToMe ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-1.5 w-full text-xs"
                    disabled={Boolean(updatingField)}
                    onClick={() => handleAssignmentChange(DEMO_USER.id)}
                  >
                    <UserCheck className="size-3.5" aria-hidden="true" />
                    Assign to me ({DEMO_USER.name})
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          {/* Ticket Metadata Card */}
          <Card className="border-border shadow-xs">
            <CardHeader className="border-b border-border px-4 py-3">
              <CardTitle className="text-sm font-semibold text-foreground">
                Requester & Metadata
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <dl className="space-y-3 text-xs">
                <div>
                  <dt className="text-2xs uppercase tracking-wide text-subtle-foreground">
                    Requester
                  </dt>
                  <dd className="mt-0.5 font-medium text-foreground">
                    {ticket.requesterName}
                  </dd>
                  <dd className="text-muted-foreground">
                    {ticket.requesterEmail}
                  </dd>
                </div>

                <div>
                  <dt className="text-2xs uppercase tracking-wide text-subtle-foreground">
                    Intake Channel
                  </dt>
                  <dd className="mt-0.5 font-medium text-foreground">
                    {CHANNEL_LABELS[ticket.channel]}
                  </dd>
                </div>

                <div>
                  <dt className="text-2xs uppercase tracking-wide text-subtle-foreground">
                    Assigned Team
                  </dt>
                  <dd className="mt-0.5 font-medium text-foreground">
                    {ticket.assignedTeam ? TEAM_LABELS[ticket.assignedTeam] : 'None'}
                  </dd>
                </div>

                <div>
                  <dt className="text-2xs uppercase tracking-wide text-subtle-foreground">
                    Received Date
                  </dt>
                  <dd className="mt-0.5 font-medium text-foreground">
                    {formatDateTime(ticket.createdAt)}
                  </dd>
                  <dd className="text-subtle-foreground">
                    {formatRelativeTime(ticket.createdAt)}
                  </dd>
                </div>

                <div>
                  <dt className="text-2xs uppercase tracking-wide text-subtle-foreground">
                    Last Updated
                  </dt>
                  <dd className="mt-0.5 font-medium text-foreground">
                    {formatDateTime(ticket.updatedAt)}
                  </dd>
                </div>

                {ticket.dueAt ? (
                  <div>
                    <dt className="text-2xs uppercase tracking-wide text-subtle-foreground">
                      Target SLA
                    </dt>
                    <dd className="mt-0.5 flex items-center gap-1.5 font-medium text-foreground">
                      <Clock className="size-3 text-warning" aria-hidden="true" />
                      {formatDateTime(ticket.dueAt)}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </CardContent>
          </Card>

          {/* Demonstration Notice */}
          <div className="rounded-lg border border-border/60 bg-card-muted/40 p-3.5 text-2xs text-subtle-foreground">
            <p className="font-semibold text-foreground">Demonstration Environment</p>
            <p className="mt-1 leading-relaxed">
              Triage mutations update the in-memory shared dataset and reactively
              propagate across all queue views, sidebar counters, and dashboard
              metrics during this application session.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
