/**
 * Service layer barrel.
 *
 * Feature code resolves `ticketService` (the typed TicketService interface)
 * and never touches fixtures or future HTTP endpoints directly.
 */
import { DemoTicketService } from './demoTicketService'
import type { TicketService } from './ticketService'

export { TicketServiceError } from './ticketService'
export { apiFetch, API_BASE_URL, isBackendConfigured } from './apiClient'
export type { TicketService } from './ticketService'
export { DemoTicketService } from './demoTicketService'

/** The single instance feature code imports. Phase 2 swaps the constructor. */
export const ticketService: TicketService = new DemoTicketService()
