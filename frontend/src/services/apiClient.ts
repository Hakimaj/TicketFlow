/**
 * Typed HTTP client for the TicketFlow API.
 *
 * - `VITE_API_BASE_URL` configures the backend origin (no secrets); API mode is
 *   the default, see `@/config/app-mode`.
 * - The short-lived access token lives in **memory only**; the refresh token
 *   is an HttpOnly cookie the browser sends to `/api/v1/auth` automatically.
 * - On `401` the client performs **at most one** refresh retry per failed
 *   request, with a single shared refresh call so concurrent failures cannot
 *   storm the endpoint.
 * - API errors arrive as `{error: {code, message, details?}}` and are mapped
 *   to `ApiClientError` so the UI can render a stable, useful message.
 */
import { API_BASE_URL } from '@/config/app-mode'

export { API_BASE_URL }

/** Response codes that map to explicit, human-readable guidance. */
const CODE_MESSAGES: Record<string, string> = {
  ticket_not_found: 'That ticket no longer exists or is unavailable.',
  reply_not_found: 'That reply no longer exists or is unavailable.',
  reply_empty: 'A reply draft cannot be empty.',
  reply_already_exists: 'This ticket already has an active reply.',
  reply_immutable: 'A sent reply can no longer be edited.',
  reply_already_sent: 'This reply was already marked as sent.',
  reply_already_pending: 'This reply is already awaiting approval.',
  reply_already_approved: 'This reply is already approved as-is.',
  reply_not_pending: 'This reply is no longer awaiting approval.',
  reply_version_conflict: 'Someone updated this reply first. Reload and retry.',
  ticket_version_conflict:
    'Someone updated this ticket first. Your change was not applied — reload to see the latest version.',
  ticket_conflict: 'A concurrent change prevented this. Please try again.',
  missing_ticket_version:
    'The ticket version is unknown. Reload the ticket before changing it.',
  account_exists: 'An account with that email already exists.',
  account_not_found: 'That account no longer exists.',
  agent_already_linked:
    'That support agent is already linked to another account.',
  empty_update: 'Choose at least one field to change.',
  self_management_forbidden:
    'You cannot change your own role or activation state. Ask another administrator.',
  last_admin:
    'At least one active administrator is required. Promote another administrator first.',
  invalid_current_password: 'The current password is incorrect.',
  password_unchanged: 'Choose a password different from the current one.',
  password_change_required:
    'Set a new password before using the workspace.',
  approval_required: 'This reply must be approved before it can be sent.',
  invalid_agent: 'The selected assignee no longer exists.',
  invalid_query: 'The requested filters are not valid together.',
  not_authenticated: 'Your session has expired. Please sign in again.',
  invalid_token: 'Your session has expired. Please sign in again.',
  refresh_invalid: 'Your session has expired. Please sign in again.',
  invalid_credentials: 'Invalid email or password.',
  forbidden: 'You do not have permission to perform this action.',
  self_approval_forbidden:
    'You cannot review or approve a reply you wrote. Ask another reviewer.',
  agent_profile_required:
    'This account is not linked to a support agent yet. Ask an administrator.',
  csrf_rejected: 'The request could not be verified. Refresh and try again.',
  origin_rejected: 'The request origin is not allowed.',
  too_many_attempts:
    'Too many sign-in attempts. Wait a moment and try again later.',
  rate_limited:
    'Too many sign-in attempts. Wait a moment and try again later.',
  database_unavailable:
    'The TicketFlow database is unreachable. Please try again shortly.',
  internal_error: 'Something went wrong on the server. Please try again.',
}

/** Thrown from every failed API call; consumed by ErrorState UIs. */
export class ApiClientError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: Record<string, unknown>

  constructor(
    message: string,
    options: { status: number; code: string; details?: Record<string, unknown> },
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.status = options.status
    this.code = options.code
    this.details = options.details
  }
}

/** Stable error codes the auth layer reacts to. */
export const AUTH_ERROR_CODES = new Set([
  'not_authenticated',
  'invalid_token',
  'csrf_rejected',
  'origin_rejected',
])

/* ------------------------------------------------------------------ */
/* In-memory access token store                                        */
/* ------------------------------------------------------------------ */

let accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

/* ------------------------------------------------------------------ */
/* Session-refresh plumbing                                            */
/* ------------------------------------------------------------------ */

type RefreshFn = () => Promise<unknown>

let refreshImpl: RefreshFn | null = null
let inflightRefresh: Promise<void> | null = null

/** Registers the session-restoring callback used on unexpected `401`s. */
export function setRefreshHandler(refresh: RefreshFn | null): void {
  refreshImpl = refresh
}

/**
 * Runs one shared refresh: concurrent 401s await the same in-flight attempt
 * instead of stampeding the refresh endpoint.
 */
async function runSharedRefresh(): Promise<void> {
  if (!inflightRefresh) {
    if (refreshImpl === null) {
      throw new ApiClientError('Your session has expired. Please sign in again.', {
        status: 401,
        code: 'not_authenticated',
      })
    }
    inflightRefresh = Promise.resolve(refreshImpl())
      .then(() => undefined)
      .finally(() => {
        inflightRefresh = null
      })
  }
  await inflightRefresh
}

/** Invoked when a request is finally rejected as unauthenticated. */
let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

function notifyUnauthorized(): void {
  unauthorizedHandler?.()
}

/* ------------------------------------------------------------------ */
// Request plumbing
/* ------------------------------------------------------------------ */

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Send cookies (needed for the refresh-cookie auth endpoints). */
  withCredentials?: boolean
  /** Skip the automatic refresh/retry cycle (used by login/refresh itself). */
  skipAuthRetry?: boolean
  signal?: AbortSignal
}

function buildUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

function toApiClientError(response: Response, body: unknown): ApiClientError {
  const status = response.status
  let code = 'internal_error'
  let message = 'Something went wrong on the server. Please try again.'
  let details: Record<string, unknown> | undefined

  const error = body as
    | { error?: { code?: string; message?: string; details?: Record<string, unknown> } }
    | null
  if (error?.error?.code) {
    code = error.error.code
    message = error.error.message ?? CODE_MESSAGES[code] ?? message
    details = error.error.details
  } else if (status === 401) {
    code = 'not_authenticated'
    message = 'Your session has expired. Please sign in again.'
  } else if (status === 429) {
    code = 'rate_limited'
    message = CODE_MESSAGES.rate_limited
  }

  return new ApiClientError(CODE_MESSAGES[code] ?? message, {
    status,
    code,
    details,
  })
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

async function requestOnce<T>(path: string, options: RequestOptions): Promise<T> {
  const headers = new Headers({ Accept: 'application/json' })
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  // CSRF/marker header required by every cookie-authenticated POST.
  headers.set('X-Requested-With', 'ticketflow')
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const response = await fetch(buildUrl(path), {
    method: options.method ?? 'GET',
    headers,
    credentials: options.withCredentials ? 'include' : 'same-origin',
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })

  const payload = await parseBody(response)
  if (!response.ok) {
    throw toApiClientError(response, payload)
  }
  return payload as T
}

/**
 * Perform one API call, with at most one refresh/retry cycle on `401`.
 * Mutating methods are retried only after a successful refresh: they are not
 * retried on their own lifecycle failures (no automatic double-submitting).
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    return await requestOnce<T>(path, options)
  } catch (error) {
    if (
      error instanceof ApiClientError &&
      error.status === 401 &&
      !options.skipAuthRetry
    ) {
      try {
        await runSharedRefresh()
      } catch (refreshError) {
        // The refresh session is gone: drop the in-memory session and let the
        // auth layer return the user to the login page.
        setAccessToken(null)
        notifyUnauthorized()
        throw refreshError instanceof Error ? refreshError : error
      }
      // Refresh produced a token; retry the original request exactly once.
      return requestOnce<T>(path, { ...options, skipAuthRetry: true })
    }
    throw error
  }
}

export function unauthorizedRedirect(): void {
  notifyUnauthorized()
}

/** Convenience wrappers used by the service layer. */
export const api = {
  get: <T>(path: string, signal?: AbortSignal) =>
    request<T>(path, { method: 'GET', signal }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body, withCredentials: true }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body }),
}
