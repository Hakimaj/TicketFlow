import type { ReplyState } from './reply'
import type {
  TicketCategory,
  TicketPriority,
  TicketStatus,
} from './ticket'

/**
 * Analytics contracts. These intentionally mirror data the demo service can
 * derive from its in-memory records: no SLA, CSAT, revenue or historical
 * snapshot fields are invented.
 */

/** Window length in days, or `'all'` for every fixture record. */
export type AnalyticsRange = 7 | 30 | 'all'

export interface AnalyticsStats {
  range: AnalyticsRange
  /** Inclusive start of the window (ISO 8601). */
  rangeStart: string
  /** When the figures were derived — shown so the page never looks live. */
  generatedAt: string

  /* ---------------------------- Summary ---------------------------- */
  totalTickets: number
  /** Tickets whose `createdAt` falls inside the selected window. */
  ticketsCreatedInRange: number
  /** Current tickets in new/open/pending (the app's active statuses). */
  activeTickets: number
  /** Current active tickets with no assigned agent. */
  unassignedTickets: number
  /** Current active tickets with urgent or high priority. */
  urgentHighTickets: number
  /** Current tickets whose status is `needs_review` (ticket-level review). */
  needsReviewTickets: number
  /** Current customer replies awaiting supervisor approval. */
  pendingReplyApprovals: number
  /** Replies whose `createdAt` falls inside the window. */
  repliesCreatedInRange: number
  /** Demo-sent replies whose `sentAt` falls inside the window. */
  sentRepliesInRange: number
  totalReplies: number

  /* ------------------------- Distributions ------------------------- */
  /** Current status of every ticket, including terminal statuses. */
  statusDistribution: Array<{ status: TicketStatus; count: number }>
  /** Categories of currently active tickets. */
  categoryDistribution: Array<{ category: TicketCategory; count: number }>
  /** Priorities of currently active tickets. */
  priorityDistribution: Array<{ priority: TicketPriority; count: number }>
  /** Current active workload per assignee, plus the unassigned bucket. */
  agentWorkload: Array<{ agentId: string | null; agentName: string; count: number }>
  /** Current state of every customer reply record. */
  replyStateDistribution: Array<{ state: ReplyState; count: number }>

  /**
   * Daily ticket creation counts (by `createdAt`) and resolution counts
   * (by `updatedAt` for resolved/closed tickets) inside the window.
   * Resolution is a proxy: the dataset stores no per-resolution event time.
   */
  volumeTrend: Array<{ date: string; created: number; resolved: number }>
}
