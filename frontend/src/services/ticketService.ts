import type {
  Agent,
  DashboardStats,
  Ticket,
  TicketActivity,
  TicketCategory,
  TicketPage,
  TicketPriority,
  TicketQuery,
  TicketStatus,
} from '@/types/ticket'

/**
 * Data-access contract for tickets. Phase 1 is implemented against the
 * demonstration dataset; Phase 2 replaces the implementation with real HTTP
 * calls behind this same interface, so feature code should not change.
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
  /** Triage mutation: update ticket status. */
  updateStatus(id: string, status: TicketStatus, agent?: Agent): Promise<Ticket>
  /** Triage mutation: update ticket priority. */
  updatePriority(id: string, priority: TicketPriority, agent?: Agent): Promise<Ticket>
  /** Triage mutation: update ticket category. */
  updateCategory(id: string, category: TicketCategory, agent?: Agent): Promise<Ticket>
  /** Triage mutation: assign or unassign a ticket. */
  assignTicket(id: string, agentId: string | null, agent?: Agent): Promise<Ticket>
  /** Triage mutation: add an internal note to the ticket workspace. */
  addInternalNote(id: string, note: string, agent?: Agent): Promise<TicketActivity>
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
