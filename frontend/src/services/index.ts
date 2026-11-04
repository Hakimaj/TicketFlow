/**
 * Service layer barrel.
 *
 * Feature code resolves `ticketService` (the typed TicketService interface)
 * and never touches fixtures or endpoints directly.
 *
 * API mode is the default. The in-memory demonstration service is used only
 * when `VITE_DATA_MODE=demo` is set explicitly; the application shell then
 * shows a visible demo indicator. An unset or partial API configuration never
 * silently substitutes fixture data.
 */
import { isDemoMode } from '@/config/app-mode'
import { DemoTicketService } from './demoTicketService'
import { HttpTicketService } from './httpTicketService'
import type { TicketService } from './ticketService'

export { TicketServiceError } from './ticketService'
export {
  API_BASE_URL,
  DATA_MODE,
  DEV_API_BASE_URL,
  isDemoMode,
  resolveApiBaseUrl,
  resolveDataMode,
} from '@/config/app-mode'
export type { DataMode } from '@/config/app-mode'
export type {
  NewTicketInput,
  TicketMutationOptions,
  TicketService,
} from './ticketService'
export {
  createAccount,
  listAccounts,
  updateAccount,
} from './accountService'
export type {
  AccountQuery,
  CreateAccountInput,
} from './accountService'
export { DemoTicketService } from './demoTicketService'
export { HttpTicketService } from './httpTicketService'

/** The single instance feature code imports. */
export const ticketService: TicketService = isDemoMode
  ? new DemoTicketService()
  : new HttpTicketService()
