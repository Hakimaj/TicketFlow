import type {
  Agent,
  DashboardStats,
  Ticket,
  TicketActivity,
  TicketPage,
  TicketQuery,
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
  /** Lookup helper for assignee display. */
  getAgent(id: string | null): Promise<Agent | null>
  /** Recent activity feed entries, newest first. */
  listActivity(limit?: number): Promise<TicketActivity[]>
  /** Everything the overview dashboard needs, derived from one dataset. */
  getDashboardStats(trendDays?: number): Promise<DashboardStats>
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
