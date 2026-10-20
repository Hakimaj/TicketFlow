import type {
  Agent,
  ActivityAction,
  CustomerReply,
  DashboardStats,
  Ticket,
  TicketActivity,
  TicketCategory,
  TicketPage,
  TicketPriority,
  TicketQuery,
  TicketStatus,
} from '@/types/ticket'
import {
  ACTIVE_STATUSES,
  CATEGORY_LABELS,
  CATEGORY_TEAM,
  CHANNEL_LABELS,
  PRIORITY_LABELS,
  PRIORITY_RANK,
  STATUS_LABELS,
  TEAM_LABELS,
  TICKET_STATUSES,
} from '@/lib/ticket-config'
import { dayKey } from '@/lib/format'
import {
  DEMO_ACTIVITY,
  DEMO_AGENTS,
  DEMO_AGENTS_BY_ID,
  DEMO_REPLIES,
  DEMO_TICKETS,
  DEMO_USER,
} from '@/data'
import { TicketServiceError, type TicketService } from './ticketService'

/**
 * Phase 1 & 2 data source: the demonstration dataset, held in memory.
 *
 * Simulates a small amount of network latency so loading and error states
 * are exercised the way they will be against a real API. No data is ever
 * persisted to a server and nothing pretends to be a live backend.
 */

const SIMULATED_LATENCY_MS = 280

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** Case-insensitive "contains" search across the searchable fields. */
function matchesSearch(ticket: Ticket, needle: string): boolean {
  const haystack = [
    ticket.id,
    ticket.subject,
    ticket.requesterName,
    ticket.requesterEmail,
  ]
    .join(' ')
    .toLowerCase()
  return haystack.includes(needle)
}

const SORT_FIELD_GETTERS: Record<
  NonNullable<TicketQuery['sortBy']>,
  (ticket: Ticket) => string | number
> = {
  createdAt: (t) => new Date(t.createdAt).getTime(),
  updatedAt: (t) => new Date(t.updatedAt).getTime(),
  priority: (t) => PRIORITY_RANK[t.priority],
  status: (t) => TICKET_STATUSES.indexOf(t.status),
  subject: (t) => t.subject.toLowerCase(),
  category: (t) => CATEGORY_LABELS[t.category].toLowerCase(),
}

export class DemoTicketService implements TicketService {
  private readonly tickets: Ticket[]
  private readonly activities: TicketActivity[]
  private readonly replies: CustomerReply[]
  private readonly listeners = new Set<() => void>()
  private activitySequence = 0

  constructor(
    tickets: Ticket[] = DEMO_TICKETS,
    activities: TicketActivity[] = DEMO_ACTIVITY,
    replies: CustomerReply[] = DEMO_REPLIES,
  ) {
    // Clone tickets and sort newest-first for stable default pagination.
    this.tickets = tickets.map((t) => ({ ...t })).sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    )
    this.activities = activities.map((a) => ({ ...a }))
    this.replies = replies.map((r) => ({ ...r }))

    // Ensure every ticket has a creation event in the activity timeline.
    const existingTicketIds = new Set(this.activities.map((a) => a.ticketId))
    for (const ticket of this.tickets) {
      if (!existingTicketIds.has(ticket.id)) {
        this.activities.push({
          id: `ACT-INIT-${ticket.id}`,
          ticketId: ticket.id,
          actorName: ticket.requesterName,
          actorType: 'system',
          action: 'created',
          detail: `Ticket created via ${CHANNEL_LABELS[ticket.channel]}.`,
          createdAt: ticket.createdAt,
        })
      }
    }
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  private notify(): void {
    for (const listener of this.listeners) {
      try {
        listener()
      } catch (err) {
        console.error('Error in TicketService listener:', err)
      }
    }
  }

  async listTickets(query: TicketQuery): Promise<TicketPage> {
    await delay(SIMULATED_LATENCY_MS)

    let result = this.tickets

    if (query.search && query.search.trim()) {
      const needle = query.search.trim().toLowerCase()
      result = result.filter((t) => matchesSearch(t, needle))
    }
    if (query.statuses && query.statuses.length > 0) {
      const allowed = new Set(query.statuses)
      result = result.filter((t) => allowed.has(t.status))
    }
    if (query.categories && query.categories.length > 0) {
      const allowed = new Set(query.categories)
      result = result.filter((t) => allowed.has(t.category))
    }
    if (query.priorities && query.priorities.length > 0) {
      const allowed = new Set(query.priorities)
      result = result.filter((t) => allowed.has(t.priority))
    }
    if (query.assignedTeam) {
      result = result.filter((t) => t.assignedTeam === query.assignedTeam)
    }
    if (query.assignmentScope === 'mine') {
      // The demo user is AG-01 — see data/demo-user.ts.
      result = result.filter((t) => t.assignedAgentId === 'AG-01')
    } else if (query.assignmentScope === 'unassigned') {
      result = result.filter((t) => t.assignedAgentId === null)
    }

    const sortBy = query.sortBy ?? 'createdAt'
    const dir = query.sortDir ?? 'desc'
    const getter = SORT_FIELD_GETTERS[sortBy]
    result = [...result].sort((a, b) => {
      const av = getter(a)
      const bv = getter(b)
      if (av < bv) return dir === 'asc' ? -1 : 1
      if (av > bv) return dir === 'asc' ? 1 : -1
      // Secondary sort: newest first, for determinism.
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    })

    const pageSize = Math.max(1, query.pageSize)
    const total = result.length
    const pageCount = Math.max(1, Math.ceil(total / pageSize))
    const page = Math.min(Math.max(1, query.page), pageCount)
    const items = result.slice((page - 1) * pageSize, page * pageSize)

    return { items, total, page, pageSize, pageCount }
  }

  async getTicket(id: string): Promise<Ticket | null> {
    await delay(SIMULATED_LATENCY_MS)
    const found = this.tickets.find((t) => t.id === id)
    return found ? { ...found } : null
  }

  async getAdjacentTicketIds(id: string): Promise<{ prevId: string | null; nextId: string | null }> {
    await delay(40)
    const idx = this.tickets.findIndex((t) => t.id === id)
    if (idx === -1) return { prevId: null, nextId: null }
    return {
      prevId: idx > 0 ? this.tickets[idx - 1].id : null,
      nextId: idx < this.tickets.length - 1 ? this.tickets[idx + 1].id : null,
    }
  }

  async getAgent(id: string | null): Promise<Agent | null> {
    if (!id) return null
    return DEMO_AGENTS_BY_ID.get(id) ?? null
  }

  async listAgents(): Promise<Agent[]> {
    await delay(40)
    return [...DEMO_AGENTS]
  }

  async listActivity(limit?: number): Promise<TicketActivity[]> {
    await delay(SIMULATED_LATENCY_MS)
    const sorted = [...this.activities].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    )
    return typeof limit === 'number' ? sorted.slice(0, limit) : sorted
  }

  async getTicketActivities(ticketId: string): Promise<TicketActivity[]> {
    await delay(SIMULATED_LATENCY_MS)
    return this.activities
      .filter((a) => a.ticketId === ticketId)
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
  }

  async updateStatus(id: string, status: TicketStatus, agent: Agent = DEMO_USER): Promise<Ticket> {
    await delay(SIMULATED_LATENCY_MS)
    const ticket = this.tickets.find((t) => t.id === id)
    if (!ticket) throw new TicketServiceError(`Ticket ${id} was not found.`)
    if (ticket.status === status) return { ...ticket }

    const prevStatus = ticket.status
    ticket.status = status
    ticket.updatedAt = new Date().toISOString()
    if (status === 'resolved' || status === 'closed') {
      ticket.dueAt = null
    }

    const action: ActivityAction =
      status === 'resolved'
        ? 'resolved'
        : status === 'needs_review'
          ? 'review_flagged'
          : 'status_changed'

    const activity: TicketActivity = {
      id: `ACT-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      ticketId: id,
      actorName: agent.name,
      actorType: 'agent',
      action,
      detail: `Status changed from ${STATUS_LABELS[prevStatus]} to ${STATUS_LABELS[status]}.`,
      createdAt: new Date().toISOString(),
    }
    this.activities.push(activity)
    this.notify()
    return { ...ticket }
  }

  async updatePriority(id: string, priority: TicketPriority, agent: Agent = DEMO_USER): Promise<Ticket> {
    await delay(SIMULATED_LATENCY_MS)
    const ticket = this.tickets.find((t) => t.id === id)
    if (!ticket) throw new TicketServiceError(`Ticket ${id} was not found.`)
    if (ticket.priority === priority) return { ...ticket }

    const prevPriority = ticket.priority
    ticket.priority = priority
    ticket.updatedAt = new Date().toISOString()

    if (ticket.status !== 'resolved' && ticket.status !== 'closed') {
      if (priority === 'urgent' || priority === 'high') {
        ticket.dueAt = new Date(Date.now() + 8 * 3600 * 1000).toISOString()
      } else {
        ticket.dueAt = null
      }
    }

    const activity: TicketActivity = {
      id: `ACT-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      ticketId: id,
      actorName: agent.name,
      actorType: 'agent',
      action: 'priority_changed',
      detail: `Priority changed from ${PRIORITY_LABELS[prevPriority]} to ${PRIORITY_LABELS[priority]}.`,
      createdAt: new Date().toISOString(),
    }
    this.activities.push(activity)
    this.notify()
    return { ...ticket }
  }

  async updateCategory(id: string, category: TicketCategory, agent: Agent = DEMO_USER): Promise<Ticket> {
    await delay(SIMULATED_LATENCY_MS)
    const ticket = this.tickets.find((t) => t.id === id)
    if (!ticket) throw new TicketServiceError(`Ticket ${id} was not found.`)
    if (ticket.category === category) return { ...ticket }

    const prevCategory = ticket.category
    ticket.category = category
    ticket.assignedTeam = CATEGORY_TEAM[category]
    ticket.updatedAt = new Date().toISOString()

    const activity: TicketActivity = {
      id: `ACT-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      ticketId: id,
      actorName: agent.name,
      actorType: 'agent',
      action: 'categorized',
      detail: `Category changed from ${CATEGORY_LABELS[prevCategory]} to ${CATEGORY_LABELS[category]} (routed to ${TEAM_LABELS[ticket.assignedTeam]}).`,
      createdAt: new Date().toISOString(),
    }
    this.activities.push(activity)
    this.notify()
    return { ...ticket }
  }

  async assignTicket(id: string, agentId: string | null, agent: Agent = DEMO_USER): Promise<Ticket> {
    await delay(SIMULATED_LATENCY_MS)
    const ticket = this.tickets.find((t) => t.id === id)
    if (!ticket) throw new TicketServiceError(`Ticket ${id} was not found.`)
    if (ticket.assignedAgentId === agentId) return { ...ticket }

    const prevAgentId = ticket.assignedAgentId
    const prevAgent = prevAgentId ? DEMO_AGENTS_BY_ID.get(prevAgentId) : null
    const newAgent = agentId ? DEMO_AGENTS_BY_ID.get(agentId) : null

    ticket.assignedAgentId = agentId
    ticket.updatedAt = new Date().toISOString()

    const detail = newAgent
      ? prevAgent
        ? `Reassigned from ${prevAgent.name} to ${newAgent.name}.`
        : `Assigned to ${newAgent.name}.`
      : `Unassigned (previously assigned to ${prevAgent?.name ?? 'unknown'}).`

    const activity: TicketActivity = {
      id: `ACT-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      ticketId: id,
      actorName: agent.name,
      actorType: 'agent',
      action: 'assigned',
      detail,
      createdAt: new Date().toISOString(),
    }
    this.activities.push(activity)
    this.notify()
    return { ...ticket }
  }

  async addInternalNote(id: string, note: string, agent: Agent = DEMO_USER): Promise<TicketActivity> {
    await delay(SIMULATED_LATENCY_MS)
    const ticket = this.tickets.find((t) => t.id === id)
    if (!ticket) throw new TicketServiceError(`Ticket ${id} was not found.`)
    const trimmed = note.trim()
    if (!trimmed) {
      throw new TicketServiceError('Internal note content cannot be empty.')
    }

    ticket.updatedAt = new Date().toISOString()

    const activity: TicketActivity = {
      id: `ACT-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      ticketId: id,
      actorName: agent.name,
      actorType: 'agent',
      action: 'note_added',
      detail: trimmed,
      createdAt: new Date().toISOString(),
      isInternalNote: true,
    }
    this.activities.push(activity)
    this.notify()
    return activity
  }

  /* ---------------- Phase 3: Reply Drafting & Human Approval ---------------- */

  async getReplies(ticketId: string): Promise<CustomerReply[]> {
    await delay(SIMULATED_LATENCY_MS)
    return this.replies
      .filter((r) => r.ticketId === ticketId)
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .map((r) => ({ ...r }))
  }

  async getReply(replyId: string): Promise<CustomerReply | null> {
    await delay(SIMULATED_LATENCY_MS)
    const found = this.replies.find((r) => r.id === replyId)
    return found ? { ...found } : null
  }

  async listPendingReplies(): Promise<CustomerReply[]> {
    await delay(SIMULATED_LATENCY_MS)
    return this.replies
      .filter((r) => r.state === 'pending_approval')
      .sort((a, b) => {
        const timeA = a.submittedAt ? new Date(a.submittedAt).getTime() : 0
        const timeB = b.submittedAt ? new Date(b.submittedAt).getTime() : 0
        return timeB - timeA
      })
      .map((r) => ({ ...r }))
  }

  async listAllReplies(): Promise<Array<{ reply: CustomerReply; ticket: Ticket }>> {
    await delay(SIMULATED_LATENCY_MS)
    const result: Array<{ reply: CustomerReply; ticket: Ticket }> = []
    for (const reply of this.replies) {
      const ticket = this.tickets.find((t) => t.id === reply.ticketId)
      if (ticket) {
        result.push({
          reply: { ...reply },
          ticket: { ...ticket },
        })
      }
    }
    return result.sort((a, b) => {
      // Prioritize pending approval replies at the top
      if (a.reply.state === 'pending_approval' && b.reply.state !== 'pending_approval') return -1
      if (b.reply.state === 'pending_approval' && a.reply.state !== 'pending_approval') return 1
      const timeA = new Date(a.reply.updatedAt).getTime()
      const timeB = new Date(b.reply.updatedAt).getTime()
      return timeB - timeA
    })
  }

  /* ---------------- Phase 3: Reply Drafting & Human Approval ---------------- */

  /** Internal: append an audit event for a reply workflow transition. */
  private recordReplyActivity(
    ticketId: string,
    actorName: string,
    action: ActivityAction,
    detail: string,
  ): void {
    this.activities.push({
      id: `ACT-${Date.now()}-${this.activitySequence++}`,
      ticketId,
      actorName,
      actorType: 'agent',
      action,
      detail,
      createdAt: new Date().toISOString(),
    })
  }

  /** The one editable/reviewable reply for a ticket (sent replies are final). */
  private findActiveReply(ticketId: string): CustomerReply | undefined {
    return this.replies.find(
      (reply) => reply.ticketId === ticketId && reply.state !== 'sent',
    )
  }

  /**
   * Save an editable reply. Saving never submits, approves or sends.
   *
   * Revision rules:
   * - Editing a draft updates its text only.
   * - Editing an approved or pending reply withdraws it and bumps the
   *   version, invalidating any previous approval.
   * - Editing after `changes_requested` counts as a revision: the version is
   *   bumped and the reply returns to draft.
   * - Once a reply is sent it is immutable; saving starts a new draft.
   */
  async saveReplyDraft(
    ticketId: string,
    body: string,
    author: Agent = DEMO_USER,
  ): Promise<CustomerReply> {
    await delay(SIMULATED_LATENCY_MS)
    const trimmed = body.trim()
    if (!trimmed) {
      throw new TicketServiceError('Reply text cannot be empty.')
    }

    const ticket = this.tickets.find((t) => t.id === ticketId)
    if (!ticket) {
      throw new TicketServiceError(`Ticket ${ticketId} was not found.`)
    }

    const now = new Date().toISOString()
    let reply = this.findActiveReply(ticketId)

    if (reply) {
      if (reply.body === trimmed) {
        // No-op save: keep timestamps fresh but never churn the version.
        reply.updatedAt = now
        this.notify()
        return { ...reply }
      }

      const previousState = reply.state
      reply.body = trimmed
      reply.updatedAt = now

      if (
        previousState === 'approved' ||
        previousState === 'pending_approval' ||
        previousState === 'changes_requested'
      ) {
        reply.state = 'draft'
        reply.version += 1
        reply.submittedAt = null
        reply.reviewedAt = null
        reply.reviewerId = null
        reply.reviewerName = null
        reply.reviewerFeedback = null

        const reason =
          previousState === 'approved'
            ? 'The previous supervisor approval was invalidated'
            : previousState === 'pending_approval'
              ? 'The reply was withdrawn from the approval queue'
              : 'The reply was revised after reviewer feedback'
        this.recordReplyActivity(
          ticketId,
          author.name,
          'replied_draft',
          `Customer reply revised to v${reply.version} by ${author.name}. ${reason}; it must be resubmitted for approval before it can be sent.`,
        )
      } else {
        this.recordReplyActivity(
          ticketId,
          author.name,
          'replied_draft',
          `Customer reply draft (v${reply.version}) updated by ${author.name}.`,
        )
      }
    } else {
      reply = {
        id: `REP-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
        ticketId,
        authorId: author.id,
        authorName: author.name,
        body: trimmed,
        state: 'draft',
        version: 1,
        createdAt: now,
        updatedAt: now,
        submittedAt: null,
        reviewedAt: null,
        reviewerId: null,
        reviewerName: null,
        reviewerFeedback: null,
        sentAt: null,
        sentByActorName: null,
      }
      this.replies.push(reply)

      this.recordReplyActivity(
        ticketId,
        author.name,
        'replied_draft',
        `Customer reply draft started by ${author.name}.`,
      )
    }

    this.notify()
    return { ...reply }
  }

  /**
   * Submit a draft (or a revised reply after feedback) for human approval.
   * Submission never approves and never sends.
   */
  async submitReplyForApproval(
    replyId: string,
    author: Agent = DEMO_USER,
  ): Promise<CustomerReply> {
    await delay(SIMULATED_LATENCY_MS)
    const reply = this.replies.find((r) => r.id === replyId)
    if (!reply) {
      throw new TicketServiceError(`Reply ${replyId} was not found.`)
    }
    if (reply.state === 'sent') {
      throw new TicketServiceError('This reply has already been sent.')
    }
    if (reply.state === 'pending_approval') {
      throw new TicketServiceError('This reply is already awaiting approval.')
    }
    if (reply.state === 'approved') {
      throw new TicketServiceError(
        'This reply is already approved. Revise the draft before resubmitting it.',
      )
    }
    if (!reply.body.trim()) {
      throw new TicketServiceError('Cannot submit an empty reply for approval.')
    }

    const wasChangesRequested = reply.state === 'changes_requested'
    const now = new Date().toISOString()

    reply.state = 'pending_approval'
    reply.submittedAt = now
    reply.updatedAt = now
    // A new review decision is required for this submission. The audit trail
    // keeps the previous reviewer feedback as activity events.
    reply.reviewedAt = null
    reply.reviewerId = null
    reply.reviewerName = null
    reply.reviewerFeedback = null

    this.recordReplyActivity(
      reply.ticketId,
      author.name,
      'reply_submitted',
      wasChangesRequested
        ? `Revised customer reply (v${reply.version}) resubmitted for approval by ${author.name}.`
        : `Customer reply (v${reply.version}) submitted for supervisor approval by ${author.name}.`,
    )

    this.notify()
    return { ...reply }
  }

  /**
   * Approve a pending reply. Approval is an explicit human decision and does
   * NOT send anything — sending is a separate, gated action.
   */
  async approveReply(
    replyId: string,
    reviewer: Agent = DEMO_USER,
  ): Promise<CustomerReply> {
    await delay(SIMULATED_LATENCY_MS)
    const reply = this.replies.find((r) => r.id === replyId)
    if (!reply) {
      throw new TicketServiceError(`Reply ${replyId} was not found.`)
    }
    if (reply.state !== 'pending_approval') {
      throw new TicketServiceError(
        `Only replies awaiting approval can be approved. Current state: ${reply.state}.`,
      )
    }

    const now = new Date().toISOString()
    reply.state = 'approved'
    reply.reviewedAt = now
    reply.reviewerId = reviewer.id
    reply.reviewerName = reviewer.name
    reply.reviewerFeedback = null
    reply.updatedAt = now

    this.recordReplyActivity(
      reply.ticketId,
      reviewer.name,
      'reply_approved',
      `Customer reply (v${reply.version}) approved by ${reviewer.name}. The reply is ready to send.`,
    )

    this.notify()
    return { ...reply }
  }

  /**
   * Request revisions on a pending reply. Reviewer comments are mandatory and
   * remain internal — they are never delivered to the customer.
   */
  async requestReplyChanges(
    replyId: string,
    feedback: string,
    reviewer: Agent = DEMO_USER,
  ): Promise<CustomerReply> {
    await delay(SIMULATED_LATENCY_MS)
    const reply = this.replies.find((r) => r.id === replyId)
    if (!reply) {
      throw new TicketServiceError(`Reply ${replyId} was not found.`)
    }
    if (reply.state !== 'pending_approval') {
      throw new TicketServiceError(
        `Changes can only be requested on replies awaiting approval. Current state: ${reply.state}.`,
      )
    }
    const trimmed = feedback.trim()
    if (!trimmed) {
      throw new TicketServiceError(
        'Internal reviewer comments explaining the requested revisions are required.',
      )
    }

    const now = new Date().toISOString()
    reply.state = 'changes_requested'
    reply.reviewedAt = now
    reply.reviewerId = reviewer.id
    reply.reviewerName = reviewer.name
    reply.reviewerFeedback = trimmed
    reply.updatedAt = now

    this.recordReplyActivity(
      reply.ticketId,
      reviewer.name,
      'reply_changes_requested',
      `Changes requested on reply (v${reply.version}) by ${reviewer.name}. Internal feedback: "${trimmed}"`,
    )

    this.notify()
    return { ...reply }
  }

  /**
   * Mark an approved reply as sent. This is a demo-only action that records
   * an audit event; it does not deliver any real message.
   *
   * The approval gate is enforced here — in the shared service layer, not just
   * in the UI. A reply can only be sent when its *current* version carries a
   * recorded approval; unapproved or stale versions are rejected.
   */
  async markReplySent(
    replyId: string,
    actor: Agent = DEMO_USER,
  ): Promise<CustomerReply> {
    await delay(SIMULATED_LATENCY_MS)
    const reply = this.replies.find((r) => r.id === replyId)
    if (!reply) {
      throw new TicketServiceError(`Reply ${replyId} was not found.`)
    }
    if (reply.state === 'sent' || reply.sentAt) {
      throw new TicketServiceError(`Reply ${replyId} has already been sent.`)
    }
    if (reply.state !== 'approved' || !reply.reviewerId) {
      throw new TicketServiceError(
        `Approval gate rejected sending: reply ${replyId} has state "${reply.state}" and no valid approval for its current version (v${reply.version}). A supervisor must approve this exact version before it can be sent.`,
      )
    }

    const now = new Date().toISOString()
    reply.state = 'sent'
    reply.sentAt = now
    reply.sentByActorName = actor.name
    reply.updatedAt = now

    this.recordReplyActivity(
      reply.ticketId,
      actor.name,
      'replied_sent',
      `Customer reply (v${reply.version}) marked as sent in demo mode by ${actor.name}. No external message was transmitted.`,
    )

    // Move active tickets to "pending" awaiting the customer's response.
    const ticket = this.tickets.find((t) => t.id === reply.ticketId)
    if (ticket && (ticket.status === 'new' || ticket.status === 'open')) {
      const previousStatus = ticket.status
      ticket.status = 'pending'
      ticket.updatedAt = now

      this.recordReplyActivity(
        ticket.id,
        actor.name,
        'status_changed',
        `Status updated from ${STATUS_LABELS[previousStatus]} to ${STATUS_LABELS.pending} after the customer reply was sent.`,
      )
    }

    this.notify()
    return { ...reply }
  }

  async getDashboardStats(trendDays = 30): Promise<DashboardStats> {
    await delay(SIMULATED_LATENCY_MS)

    if (trendDays < 1) {
      throw new TicketServiceError('Trend window must be at least one day.')
    }

    const all = this.tickets
    const active = all.filter((t) => ACTIVE_STATUSES.includes(t.status))

    const statusCounts = Object.fromEntries(
      TICKET_STATUSES.map((s) => [s, all.filter((t) => t.status === s).length]),
    ) as DashboardStats['statusCounts']

    /* ---------------- 30-day received/resolved trend ---------------- */
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const receivedBuckets = new Map<string, number>()
    const resolvedBuckets = new Map<string, number>()
    for (let i = trendDays - 1; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      receivedBuckets.set(dayKey(d), 0)
      resolvedBuckets.set(dayKey(d), 0)
    }
    for (const t of all) {
      const createdKey = dayKey(new Date(t.createdAt))
      if (receivedBuckets.has(createdKey)) {
        receivedBuckets.set(createdKey, (receivedBuckets.get(createdKey) ?? 0) + 1)
      }
      if (t.status === 'resolved' || t.status === 'closed') {
        const updatedKey = dayKey(new Date(t.updatedAt))
        if (resolvedBuckets.has(updatedKey)) {
          resolvedBuckets.set(updatedKey, (resolvedBuckets.get(updatedKey) ?? 0) + 1)
        }
      }
    }
    const receivedTrend = [...receivedBuckets.keys()].map((date) => ({
      date,
      received: receivedBuckets.get(date) ?? 0,
      resolved: resolvedBuckets.get(date) ?? 0,
    }))

    /* ---------------- Category distribution (active tickets) ---------------- */
    const categoryDistribution = (Object.keys(CATEGORY_LABELS) as Array<keyof typeof CATEGORY_LABELS>)
      .map((category) => ({
        category,
        count: active.filter((t) => t.category === category).length,
      }))
      .sort((a, b) => b.count - a.count)

    /* ---------------- Priority summary (active tickets) ---------------- */
    const prioritySummary = (['urgent', 'high', 'normal', 'low'] as const).map(
      (priority) => {
        const open = active.filter((t) => t.priority === priority)
        return {
          priority,
          open: open.filter((t) => t.status === 'open' || t.status === 'new').length,
          pending: open.filter((t) => t.status === 'pending').length,
          needsReview: open.filter((t) => t.status === 'needs_review').length,
          total: open.length,
        }
      },
    )

    return {
      openTickets: active.length,
      unassignedTickets: active.filter((t) => t.assignedAgentId === null).length,
      highPriorityOpen: active.filter(
        (t) => t.priority === 'urgent' || t.priority === 'high',
      ).length,
      needsReviewTickets: statusCounts.needs_review,
      pendingApprovals: this.replies.filter((r) => r.state === 'pending_approval').length,
      statusCounts,
      receivedTrend,
      categoryDistribution,
      prioritySummary,
      recentTickets: all.slice(0, 7),
      recentActivity: [...this.activities]
        .sort(
          (a, b) =>
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
        )
        .slice(0, 6),
    }
  }
}
