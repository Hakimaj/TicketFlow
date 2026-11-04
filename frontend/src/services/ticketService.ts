import type {
  Agent,
  CustomerReply,
  DashboardStats,
  Ticket,
  TicketActivity,
  TicketCategory,
  TicketChannel,
  TicketPage,
  TicketPriority,
  TicketQuery,
  TicketStatus,
} from '@/types/ticket'
import type { ActivityLogFacets, ActivityLogPage, ActivityLogQuery } from '@/types/activity'
import type { AnalyticsRange, AnalyticsStats } from '@/types/analytics'

/**
 * Expected version for a triage mutation.
 *
 * API mode requires it: the server rejects a stale version with `409` so two
 * operators cannot silently overwrite each other. Demo mode has no concurrent
 * writers and ignores it.
 */
export interface TicketMutationOptions {
  expectedVersion?: number
}

/** Staff intake payload — no actor, status or version fields. */
export interface NewTicketInput {
  subject: string
  description: string
  category: TicketCategory
  priority?: TicketPriority
  channel?: TicketChannel
  requesterName: string
  requesterEmail: string
}

/**
 * Data-access contract for tickets, implemented by both the API-backed and the
 * explicit demo service.
 */
export interface TicketService {
  /** Search, filter, sort and paginate tickets. */
  listTickets(query: TicketQuery): Promise<TicketPage>
  /** A single ticket by its human-readable ID, or null when missing. */
  getTicket(id: string): Promise<Ticket | null>
  /** Adjacent ticket IDs in the overall queue for prev/next triage navigation. */
  getAdjacentTicketIds(id: string): Promise<{ prevId: string | null; nextId: string | null }>
  /** Lookup helper for assignee display. */
  getAgent(id: string | null): Promise<Agent | null>
  /** Roster of available demo agents for assignment. */
  listAgents(): Promise<Agent[]>
  /** Recent activity feed entries across all tickets, newest first. */
  listActivity(limit?: number): Promise<TicketActivity[]>
  /** Chronological activity entries for a specific ticket. */
  getTicketActivities(ticketId: string): Promise<TicketActivity[]>
  /** Everything the overview dashboard needs, derived from one dataset. */
  getDashboardStats(trendDays?: number): Promise<DashboardStats>

  /* ---------------- Phase 4: Analytics & operational audit ---------------- */

  /**
   * Derived support-operations metrics. Current-state distributions are
   * combined with time-windowed creation/resolution counts; see
   * `AnalyticsStats` for the exact timestamp used by each figure.
   */
  getAnalytics(range?: AnalyticsRange): Promise<AnalyticsStats>
  /** Sanitized, searchable activity-log projection (never raw internal content). */
  listActivityLog(query: ActivityLogQuery): Promise<ActivityLogPage>
  /** Distinct actors and actions present in the audit trail, with counts. */
  getActivityLogFacets(): Promise<ActivityLogFacets>
  /** Staff intake: create a persisted ticket. */
  createTicket(input: NewTicketInput): Promise<Ticket>
  /** Triage mutation: update ticket status. */
  updateStatus(
    id: string,
    status: TicketStatus,
    agent?: Agent,
    options?: TicketMutationOptions,
  ): Promise<Ticket>
  /** Triage mutation: update ticket priority. */
  updatePriority(
    id: string,
    priority: TicketPriority,
    agent?: Agent,
    options?: TicketMutationOptions,
  ): Promise<Ticket>
  /** Triage mutation: update ticket category. */
  updateCategory(
    id: string,
    category: TicketCategory,
    agent?: Agent,
    options?: TicketMutationOptions,
  ): Promise<Ticket>
  /** Triage mutation: assign or unassign a ticket. */
  assignTicket(
    id: string,
    agentId: string | null,
    agent?: Agent,
    options?: TicketMutationOptions,
  ): Promise<Ticket>
  /** Triage mutation: add an internal note to the ticket workspace. */
  addInternalNote(id: string, note: string, agent?: Agent): Promise<TicketActivity>

  /* ---------------- Phase 3: Reply Drafting & Human Approval ---------------- */

  /** Get all customer replies associated with a ticket. */
  getReplies(ticketId: string): Promise<CustomerReply[]>
  /** Get a single reply by its ID. */
  getReply(replyId: string): Promise<CustomerReply | null>
  /** List all replies currently in pending_approval state. */
  listPendingReplies(): Promise<CustomerReply[]>
  /** List all replies paired with their parent ticket for the approvals queue. */
  listAllReplies(): Promise<Array<{ reply: CustomerReply; ticket: Ticket }>>
  /** Save or update an in-progress draft for a ticket. */
  saveReplyDraft(ticketId: string, body: string, author?: Agent): Promise<CustomerReply>
  /** Submit a draft for human approval. */
  submitReplyForApproval(replyId: string, author?: Agent): Promise<CustomerReply>
  /** Approve a submitted reply (does NOT send). */
  approveReply(replyId: string, reviewer?: Agent): Promise<CustomerReply>
  /** Request revisions with mandatory reviewer comments. */
  requestReplyChanges(replyId: string, feedback: string, reviewer?: Agent): Promise<CustomerReply>
  /** Mark an approved reply as sent in demo mode (Approval Gate strictly enforced). */
  markReplySent(replyId: string, actor?: Agent): Promise<CustomerReply>

  /** Reactive listener for mutations across the application session. */
  subscribe(listener: () => void): () => void
}

/** Error thrown when a service call fails; consumed by ErrorState UI. */
export class TicketServiceError extends Error {
  readonly cause?: unknown

  constructor(message: string, cause?: unknown) {
    super(message)
    this.name = 'TicketServiceError'
    this.cause = cause
  }
}
