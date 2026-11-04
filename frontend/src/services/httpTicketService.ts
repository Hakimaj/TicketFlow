/**
 * HTTP implementation of the `TicketService` contract, backed by the
 * TicketFlow API. Field names arrive in snake_case and are mapped to the
 * camelCase frontend types so feature code never changes.
 *
 * The acting user, reviewer and send actor always come from the verified
 * access token server-side; caller-supplied agents stay display-only.
 * Every accepted mutation notifies `subscribe` listeners so sibling views in
 * the same SPA session refresh reactively, mirroring the demo service.
 */
import type {
  ActivityAction,
  ActivityActorType,
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
import type { CustomerReply } from '@/types/reply'
import { REPLY_STATES } from '@/types/reply'
import type {
  ActivityLogEntry,
  ActivityLogFacets,
  ActivityLogPage,
  ActivityLogQuery,
} from '@/types/activity'
import type { AnalyticsRange, AnalyticsStats } from '@/types/analytics'
import { ACTIVITY_ACTION_LABELS } from '@/lib/activity-config'
import { api, ApiClientError } from './apiClient'
import type {
  NewTicketInput,
  TicketMutationOptions,
  TicketService,
} from './ticketService'

/* ------------------------------------------------------------------ */
/* Raw API shapes (snake_case)                                         */
/* ------------------------------------------------------------------ */

interface RawPageMeta {
  page: number
  page_size: number
  total: number
  page_count: number
}

interface RawTicketSummary {
  id: string
  subject: string
  requester_name: string
  channel: string
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  assigned_team: string | null
  assigned_agent_id: string | null
  assigned_agent_name: string | null
  version: number
  created_at: string
  updated_at: string
}

interface RawTicketDetail extends RawTicketSummary {
  description: string
  requester: { id: string; name: string; email: string }
  due_at: string | null
  suggested_category: TicketCategory | null
  suggested_priority: TicketPriority | null
  review_note: string | null
}

interface RawTicketListResponse {
  items: RawTicketSummary[]
  pagination: RawPageMeta
}

interface RawAgent {
  id: string
  name: string
  role: string
  team: string | null
}

interface RawNoteResponse {
  id: string
  ticket_id: string
  content: string
  author: { id: string; name: string }
  created_at: string
  updated_at: string
}

interface RawNoteListResponse {
  items: RawNoteResponse[]
  pagination: RawPageMeta
}

interface RawActivity {
  id: string
  ticket_id: string
  reply_id: string | null
  reply_version: number | null
  note_id: string | null
  actor_id: string | null
  actor_name: string | null
  actor_type: ActivityActorType
  action: ActivityAction
  summary: string
  is_internal_note: boolean
  created_at: string
}

interface RawActivityListResponse {
  items: RawActivity[]
  pagination: RawPageMeta
}

interface RawReplySummary {
  id: string
  ticket_id: string
  author: { id: string; name: string }
  recipient: { name: string; email: string }
  body: string
  state: CustomerReply['state']
  version: number
  submitted_at: string | null
  reviewed_at: string | null
  reviewer_id: string | null
  reviewer_name: string | null
  reviewer_feedback: string | null
  sent_at: string | null
  sent_by_actor_name: string | null
  created_at: string
  updated_at: string
}

interface RawReplyListResponse {
  items: RawReplySummary[]
  pagination: RawPageMeta
}

interface RawReplyWithTicket {
  reply: RawReplySummary
  ticket: {
    id: string
    subject: string
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    requester_name: string
    created_at: string
  }
}

interface RawReplyDetail extends RawReplySummary {
  revisions: Array<{ version: number }>
  reviews: Array<Record<string, unknown>>
}

interface RawDashboardSummary {
  generated_at: string
  total_tickets: number
  active_tickets: number
  unassigned_tickets: number
  urgent_high_tickets: number
  needs_review_tickets: number
  pending_reply_approvals: number
  status_counts: Array<{ status: TicketStatus; count: number }>
  category_counts: Array<{ category: TicketCategory; count: number }>
  priority_counts: Array<{ priority: TicketPriority; count: number }>
  received_trend?:
    | Array<{ date: string; received: number; resolved: number }>
    | null
  priority_summary?:
    | Array<{
        priority: TicketPriority
        open: number
        pending: number
        needs_review: number
        total: number
      }>
    | null
  agent_workload?:
    | Array<{ agent_id: string | null; agent_name: string | null; count: number }>
    | null
}

interface RawAccountProfile {
  agent_id: string | null
}

/**
 * The server rejects a triage mutation without the version the caller read.
 * Failing here (instead of sending no precondition) keeps the guarantee: two
 * operators can never silently overwrite each other.
 */
function expectedVersion(
  operation: string,
  options?: TicketMutationOptions,
): number {
  const version = options?.expectedVersion
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) {
    throw new ApiClientError(
      `${operation} needs the ticket version you last read. Reload the ticket and try again.`,
      { status: 409, code: 'missing_ticket_version' },
    )
  }
  return version
}

/** Domain order used by the demo service for priority summaries. */
const PRIORITY_ORDER: TicketPriority[] = ['urgent', 'high', 'normal', 'low']
const TICKET_STATUS_ORDER: TicketStatus[] = [
  'new',
  'open',
  'pending',
  'needs_review',
  'resolved',
  'closed',
]
const ACTIVE_STATUSES: TicketStatus[] = ['new', 'open', 'pending']
const DAY_MS = 24 * 60 * 60 * 1000
/** Safety cap so a runaway page-walk cannot loop forever. */
const MAX_PAGES = 100

/* ------------------------------------------------------------------ */
/* Mapping helpers                                                     */
/* ------------------------------------------------------------------ */

function mapTicketSummary(raw: RawTicketSummary): Ticket {
  return {
    id: raw.id,
    subject: raw.subject,
    // Detail-only fields are absent from list rows; null-ish values keep the
    // UI's optional rendering paths intact without extra requests.
    description: '',
    requesterName: raw.requester_name,
    requesterEmail: '',
    channel: raw.channel as Ticket['channel'],
    category: raw.category,
    priority: raw.priority,
    status: raw.status,
    assignedTeam: raw.assigned_team as Ticket['assignedTeam'],
    assignedAgentId: raw.assigned_agent_id,
    // Concurrency token required by every triage mutation.
    version: raw.version,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    dueAt: null,
    suggestedCategory: null,
    suggestedPriority: null,
    reviewNote: null,
  }
}

function mapTicketDetail(raw: RawTicketDetail): Ticket {
  return {
    ...mapTicketSummary(raw),
    description: raw.description,
    requesterEmail: raw.requester?.email ?? '',
    dueAt: raw.due_at ?? null,
    suggestedCategory: raw.suggested_category ?? null,
    suggestedPriority: raw.suggested_priority ?? null,
    reviewNote: raw.review_note ?? null,
  }
}

/**
 * Compact parent-ticket view shipped with cross-resource reply listings. It
 * carries no channel/detail fields; the approvals UI only renders the fields
 * present here, and unavailable ones stay neutral.
 */
function mapReplyTicketRef(
  raw: RawReplyWithTicket['ticket'],
  recipientEmail: string | null | undefined,
): Ticket {
  return {
    ...mapTicketSummary(raw as unknown as RawTicketSummary),
    // The compact ref deliberately omits detail fields. Keep unavailable
    // values empty so the UI can omit them instead of rendering placeholders.
    requesterEmail: recipientEmail ?? '',
    channel: 'web_form',
  }
}

function mapAgent(raw: RawAgent): Agent {
  return {
    id: raw.id,
    name: raw.name,
    role: raw.role as Agent['role'],
    team: raw.team as Agent['team'],
    email: '',
  }
}

function mapActivity(raw: RawActivity): TicketActivity {
  return {
    id: raw.id,
    ticketId: raw.ticket_id,
    replyId: raw.reply_id,
    actorName: raw.actor_name ?? 'System',
    actorType: raw.actor_type,
    action: raw.action,
    detail: raw.summary || null,
    createdAt: raw.created_at,
    isInternalNote: raw.is_internal_note,
  }
}

function mapReply(raw: RawReplySummary): CustomerReply {
  return {
    id: raw.id,
    ticketId: raw.ticket_id,
    authorId: raw.author?.id ?? '',
    authorName: raw.author?.name ?? 'Unknown',
    body: raw.body,
    state: raw.state,
    version: raw.version,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    submittedAt: raw.submitted_at,
    reviewedAt: raw.reviewed_at,
    reviewerId: raw.reviewer_id,
    reviewerName: raw.reviewer_name,
    reviewerFeedback: raw.reviewer_feedback,
    sentAt: raw.sent_at,
    sentByActorName: raw.sent_by_actor_name,
  }
}

interface QueryParams {
  [key: string]:
    | string
    | string[]
    | number
    | boolean
    | null
    | undefined
}

function toQuery(params: QueryParams): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, item)
    } else {
      search.append(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

const SORT_FIELD_MAP: Record<
  NonNullable<TicketQuery['sortBy']>,
  string
> = {
  createdAt: 'created_at',
  updatedAt: 'updated_at',
  priority: 'priority',
  status: 'status',
  subject: 'subject',
  category: 'category',
}

function rethrowServiceError(method: string, error: unknown): never {
  if (error instanceof ApiClientError) {
    throw error
  }
  throw new ApiClientError(`${method} failed.`, {
    status: 0,
    code: 'internal_error',
  })
}

function startOfDayUTC(date: Date): Date {
  return new Date(
    Date.UTC(
      date.getUTCFullYear(),
      date.getUTCMonth(),
      date.getUTCDate(),
    ),
  )
}

/**
 * Inclusive local-midnight start for an activity window, matching the demo
 * service. `'all'` has no lower bound.
 */
function activityRangeStart(
  range: ActivityLogQuery['range'],
): string | undefined {
  const value = range ?? 'all'
  if (value === 'all') return undefined
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  start.setDate(start.getDate() - (value - 1))
  return start.toISOString()
}

/* ------------------------------------------------------------------ */
/* Service                                                             */
/* ------------------------------------------------------------------ */

export class HttpTicketService implements TicketService {
  private agentCache: Agent[] | null = null
  private currentAgentIdCache: string | null | undefined = undefined

  private listeners = new Set<() => void>()

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  private notify(): void {
    for (const listener of this.listeners) listener()
  }

  /* ------------------------- tickets ------------------------- */

  async listTickets(query: TicketQuery): Promise<TicketPage> {
    try {
      const params: QueryParams = {
        page: Math.max(1, query.page),
        page_size: Math.min(100, Math.max(1, query.pageSize)),
      }
      if (query.search) params.search = query.search
      if (query.statuses && query.statuses.length > 0) {
        params.status = query.statuses
      }
      if (query.categories && query.categories.length > 0) {
        params.category = query.categories
      }
      if (query.priorities && query.priorities.length > 0) {
        params.priority = query.priorities
      }
      if (query.assignmentScope === 'unassigned') {
        params.unassigned = true
      } else if (query.assignmentScope === 'mine') {
        const agentId = await this.currentAgentId()
        if (!agentId) {
          throw new ApiClientError(
            'Sign in with a linked agent account to use the "mine" filter.',
            { status: 403, code: 'forbidden' },
          )
        }
        params.assigned_agent_id = agentId
      }
      params.sort_by = query.sortBy
        ? SORT_FIELD_MAP[query.sortBy]
        : 'created_at'
      params.sort_dir = query.sortDir ?? 'desc'

      const response = await api.get<RawTicketListResponse>(
        `/tickets${toQuery(params)}`,
      )
      return {
        items: response.items.map(mapTicketSummary),
        total: response.pagination.total,
        page: response.pagination.page,
        pageSize: response.pagination.page_size,
        pageCount: Math.max(1, response.pagination.page_count),
      }
    } catch (error) {
      rethrowServiceError('Listing tickets', error)
    }
  }

  async getTicket(id: string): Promise<Ticket | null> {
    try {
      const raw = await api.get<RawTicketDetail>(
        `/tickets/${encodeURIComponent(id)}`,
      )
      return mapTicketDetail(raw)
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 404) {
        return null
      }
      rethrowServiceError('Loading the ticket', error)
    }
  }

  async getAdjacentTicketIds(
    id: string,
  ): Promise<{ prevId: string | null; nextId: string | null }> {
    try {
      // Walk the full ordered queue; the demo implementation had the whole
      // in-memory queue, the API exposes the same order via pagination.
      const ids: string[] = []
      let page = 1
      for (;;) {
        const response = await api.get<RawTicketListResponse>(
          `/tickets?page=${page}&page_size=100&sort_by=created_at&sort_dir=asc`,
        )
        for (const item of response.items) ids.push(item.id)
        const pageCount = Math.max(1, response.pagination.page_count)
        if (page >= pageCount || page >= MAX_PAGES) break
        page += 1
      }
      const index = ids.indexOf(id)
      if (index === -1) return { prevId: null, nextId: null }
      return {
        prevId: index > 0 ? ids[index - 1] : null,
        nextId: index < ids.length - 1 ? ids[index + 1] : null,
      }
    } catch (error) {
      rethrowServiceError('Loading queue neighbors', error)
    }
  }

  /* ------------------------- agents ------------------------- */

  async getAgent(id: string | null): Promise<Agent | null> {
    if (!id) return null
    const roster = await this.listAgents()
    return roster.find((agent) => agent.id === id) ?? null
  }

  async listAgents(): Promise<Agent[]> {
    if (this.agentCache) return this.agentCache
    try {
      const response = await api.get<{ items: RawAgent[] }>(
        '/agents?page_size=100',
      )
      this.agentCache = response.items.map(mapAgent)
      return this.agentCache
    } catch (error) {
      rethrowServiceError('Loading the agent roster', error)
    }
  }

  /* ------------------------- activity ------------------------- */

  async listActivity(limit?: number): Promise<TicketActivity[]> {
    try {
      const pageSize =
        typeof limit === 'number' ? Math.min(100, Math.max(1, limit)) : 50
      const response = await api.get<RawActivityListResponse>(
        `/activities?page_size=${pageSize}&sort_dir=desc`,
      )
      return response.items.map(mapActivity)
    } catch (error) {
      rethrowServiceError('Loading recent activity', error)
    }
  }

  async getTicketActivities(ticketId: string): Promise<TicketActivity[]> {
    try {
      // Ticket-scoped activity is returned as a plain chronological list (the
      // global audit log is the paginated endpoint). Internal note bodies live
      // on the staff-only notes resource, never in the audit summary, so they
      // are joined back for the timeline card.
      const [items, notes] = await Promise.all([
        api.get<RawActivity[]>(
          `/tickets/${encodeURIComponent(ticketId)}/activities`,
        ),
        api.get<RawNoteListResponse>(
          `/tickets/${encodeURIComponent(ticketId)}/notes?page_size=100`,
        ),
      ])
      const notesById = new Map(notes.items.map((note) => [note.id, note]))
      return items
        .map((raw) => {
          const activity = mapActivity(raw)
          const note = raw.note_id ? notesById.get(raw.note_id) : undefined
          if (note) {
            activity.detail = note.content
            activity.actorName = note.author.name
            activity.createdAt = note.created_at
          }
          return activity
        })
        .sort(
          (a, b) =>
            new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
        )
    } catch (error) {
      rethrowServiceError('Loading the ticket timeline', error)
    }
  }

  /* ------------------------- dashboard ------------------------- */

  async getDashboardStats(trendDays = 30): Promise<DashboardStats> {
    if (trendDays < 1) {
      throw new ApiClientError('Trend window must be at least one day.', {
        status: 400,
        code: 'invalid_query',
      })
    }
    try {
      const [summary, activeTickets, recentTickets, recentActivity] =
        await Promise.all([
          api.get<RawDashboardSummary>(
            `/dashboard/summary?trend_days=${trendDays}`,
          ),
          this.fetchActiveTickets(),
          api.get<RawTicketListResponse>(
            `/tickets?page_size=7&sort_by=created_at&sort_dir=desc`,
          ),
          api.get<RawActivityListResponse>(
            `/activities?page_size=6&sort_dir=desc`,
          ),
        ])

      const statusCounts = Object.fromEntries(
        TICKET_STATUS_ORDER.map((status) => [
          status,
          summary.status_counts.find((row) => row.status === status)?.count ??
            0,
        ]),
      ) as DashboardStats['statusCounts']

      const categoryCounts = new Map<TicketCategory, number>()
      for (const ticket of activeTickets) {
        categoryCounts.set(
          ticket.category,
          (categoryCounts.get(ticket.category) ?? 0) + 1,
        )
      }
      const categoryDistribution = [...categoryCounts.entries()]
        .map(([category, count]) => ({ category, count }))
        .sort((a, b) => b.count - a.count)

      const prioritySummary = PRIORITY_ORDER.map((priority) => {
        const row = summary.priority_summary?.find(
          (candidate) => candidate.priority === priority,
        )
        return {
          priority,
          open: row?.open ?? 0,
          pending: row?.pending ?? 0,
          needsReview: row?.needs_review ?? 0,
          total: row?.total ?? 0,
        }
      })

      return {
        openTickets: summary.active_tickets,
        unassignedTickets: summary.unassigned_tickets,
        highPriorityOpen: summary.urgent_high_tickets,
        needsReviewTickets: summary.needs_review_tickets,
        pendingApprovals: summary.pending_reply_approvals,
        statusCounts,
        receivedTrend: (summary.received_trend ?? []).map((point) => ({
          date: point.date,
          received: point.received,
          resolved: point.resolved,
        })),
        categoryDistribution,
        prioritySummary,
        recentTickets: recentTickets.items.map(mapTicketSummary),
        recentActivity: recentActivity.items.map(mapActivity),
      }
    } catch (error) {
      rethrowServiceError('Loading dashboard statistics', error)
    }
  }

  /* ------------------------- analytics ------------------------- */

  async getAnalytics(range: AnalyticsRange = 30): Promise<AnalyticsStats> {
    if (range !== 7 && range !== 30 && range !== 'all') {
      throw new ApiClientError(
        `Unsupported analytics range: ${String(range)}.`,
        { status: 400, code: 'invalid_query' },
      )
    }
    const trendDays = range === 'all' ? 3650 : range
    try {
      const [summary, activeTickets, replies] = await Promise.all([
        api.get<RawDashboardSummary>(
          `/dashboard/summary?trend_days=${trendDays}`,
        ),
        this.fetchActiveTickets(),
        this.fetchAllReplies(),
      ])

      const generatedAt =
        summary.generated_at ?? new Date().toISOString()
      const rangeStart =
        range === 'all'
          ? (summary.received_trend?.[0]?.date ??
            generatedAt.slice(0, 10))
          : startOfDayUTC(
              new Date(Date.now() - (range - 1) * DAY_MS),
            ).toISOString()

      const startMs = new Date(rangeStart).getTime()
      const inWindow = (iso: string | null | undefined): boolean =>
        typeof iso === 'string' &&
        iso.length > 0 &&
        new Date(iso).getTime() >= startMs

      /* ---------------- reply aggregates ---------------- */
      const repliesCreatedInRange = replies.filter((reply) =>
        inWindow(reply.created_at),
      ).length
      const sentRepliesInRange = replies.filter(
        (reply) => reply.state === 'sent' && inWindow(reply.sent_at),
      ).length
      const replyStateDistribution = (
        REPLY_STATES as ReadonlyArray<CustomerReply['state']>
      ).map((state) => ({
        state,
        count: replies.filter((reply) => reply.state === state).length,
      }))

      /* ---------------- active distributions ---------------- */
      const categoryCounts = new Map<TicketCategory, number>()
      for (const ticket of activeTickets) {
        categoryCounts.set(
          ticket.category,
          (categoryCounts.get(ticket.category) ?? 0) + 1,
        )
      }
      const categoryDistribution = [...categoryCounts.entries()]
        .map(([category, count]) => ({ category, count }))
        .sort((a, b) => b.count - a.count)

      const statusDistribution = summary.status_counts.map((row) => ({
        status: row.status,
        count: row.count,
      }))

      const priorityDistribution = PRIORITY_ORDER.map((priority) => {
        const row = summary.priority_summary?.find(
          (candidate) => candidate.priority === priority,
        )
        return {
          priority,
          count:
            (row?.open ?? 0) + (row?.pending ?? 0) + (row?.needs_review ?? 0),
        }
      })

      const agentWorkload = (summary.agent_workload ?? []).map((row) => ({
        agentId: row.agent_id,
        agentName: row.agent_name ?? 'Unassigned',
        count: row.count,
      }))

      const volumeTrend = (summary.received_trend ?? []).map((point) => ({
        date: point.date,
        created: point.received,
        resolved: point.resolved,
      }))

      return {
        range,
        rangeStart,
        generatedAt,
        totalTickets: summary.total_tickets,
        ticketsCreatedInRange: volumeTrend.reduce(
          (sum, point) => sum + point.created,
          0,
        ),
        activeTickets: summary.active_tickets,
        unassignedTickets: summary.unassigned_tickets,
        urgentHighTickets: summary.urgent_high_tickets,
        needsReviewTickets: summary.needs_review_tickets,
        pendingReplyApprovals: summary.pending_reply_approvals,
        repliesCreatedInRange,
        sentRepliesInRange,
        totalReplies: replies.length,
        statusDistribution,
        categoryDistribution,
        priorityDistribution,
        agentWorkload,
        replyStateDistribution,
        volumeTrend,
      }
    } catch (error) {
      rethrowServiceError('Loading analytics', error)
    }
  }

  /* ------------------------- audit log ------------------------- */

  async listActivityLog(query: ActivityLogQuery): Promise<ActivityLogPage> {
    try {
      // The API supports search/action filters server-side; actor-name and
      // combined search narrowing run client-side over exhaustively fetched
      // pages so pagination matches the demo semantics exactly.
      const bothFilters = Boolean(query.search && query.actorName)
      const rangeStart = activityRangeStart(query.range)
      const params: QueryParams = {
        page_size: 100,
        sort_dir: query.sortDir ?? 'desc',
      }
      if (!bothFilters) {
        if (query.search) params.search = query.search
        else if (query.actorName) params.search = query.actorName
      }
      if (query.actions && query.actions.length > 0) {
        params.action = query.actions
      }
      if (rangeStart) params.start = rangeStart

      const fetched: RawActivity[] = []
      let requestPage = 1
      for (;;) {
        params.page = requestPage
        const response = await api.get<RawActivityListResponse>(
          `/activities${toQuery(params)}`,
        )
        fetched.push(...response.items)
        const pageCount = Math.max(1, response.pagination.page_count)
        if (requestPage >= pageCount || requestPage >= MAX_PAGES) break
        requestPage += 1
      }

      let entries: ActivityLogEntry[] = fetched.map((raw) => ({
        id: raw.id,
        ticketId: raw.ticket_id,
        replyId: raw.reply_id ?? null,
        actorName: raw.actor_name ?? 'System',
        actorType: raw.actor_type,
        action: raw.action,
        summary: raw.summary,
        createdAt: raw.created_at,
      }))

      if (bothFilters || query.actorName) {
        entries = entries.filter(
          (entry) => entry.actorName === query.actorName,
        )
      }
      if (query.search) {
        const needle = query.search.trim().toLowerCase()
        entries = entries.filter((entry) =>
          [
            entry.ticketId,
            entry.actorName,
            ACTIVITY_ACTION_LABELS[entry.action],
            entry.summary,
          ]
            .join(' ')
            .toLowerCase()
            .includes(needle),
        )
      }
      if (query.actions && query.actions.length > 0) {
        const allowed = new Set(query.actions)
        entries = entries.filter((entry) => allowed.has(entry.action))
      }
      if (rangeStart) {
        const startMs = new Date(rangeStart).getTime()
        entries = entries.filter(
          (entry) => new Date(entry.createdAt).getTime() >= startMs,
        )
      }

      const pageSize = Math.min(100, Math.max(1, query.pageSize))
      const total = entries.length
      const pageCount = Math.max(1, Math.ceil(total / pageSize))
      const clampedPage = Math.min(Math.max(1, query.page), pageCount)
      const items = entries.slice(
        (clampedPage - 1) * pageSize,
        clampedPage * pageSize,
      )
      return {
        items,
        total,
        page: clampedPage,
        pageSize,
        pageCount,
      }
    } catch (error) {
      rethrowServiceError('Loading the audit log', error)
    }
  }

  async getActivityLogFacets(): Promise<ActivityLogFacets> {
    try {
      // Facets describe the whole trail, so walk every page rather than the
      // first batch of events.
      const raws: RawActivity[] = []
      let requestPage = 1
      for (;;) {
        const response = await api.get<RawActivityListResponse>(
          `/activities?page_size=100&page=${requestPage}&sort_dir=desc`,
        )
        raws.push(...response.items)
        const pageCount = Math.max(1, response.pagination.page_count)
        if (requestPage >= pageCount || requestPage >= MAX_PAGES) break
        requestPage += 1
      }

      const actorCounts = new Map<string, number>()
      const actionCounts = new Map<ActivityAction, number>()
      for (const raw of raws) {
        const actor = raw.actor_name ?? 'System'
        actorCounts.set(actor, (actorCounts.get(actor) ?? 0) + 1)
        actionCounts.set(
          raw.action,
          (actionCounts.get(raw.action) ?? 0) + 1,
        )
      }

      return {
        actors: [...actorCounts.entries()]
          .map(([name, count]) => ({ name, count }))
          .sort(
            (a, b) => b.count - a.count || a.name.localeCompare(b.name),
          ),
        actions: [...actionCounts.entries()]
          .map(([action, count]) => ({ action, count }))
          .sort(
            (a, b) =>
              b.count - a.count ||
              ACTIVITY_ACTION_LABELS[a.action].localeCompare(
                ACTIVITY_ACTION_LABELS[b.action],
              ),
          ),
      }
    } catch (error) {
      rethrowServiceError('Loading audit facets', error)
    }
  }

  /* ------------------------- intake ------------------------- */

  async createTicket(input: NewTicketInput): Promise<Ticket> {
    try {
      const created = await api.post<RawTicketDetail>('/tickets', {
        subject: input.subject,
        description: input.description,
        category: input.category,
        priority: input.priority,
        channel: input.channel,
        requester_name: input.requesterName,
        requester_email: input.requesterEmail,
      })
      // Sibling views (queue, dashboard counts, sidebar badges) refetch.
      this.notify()
      return mapTicketDetail(created)
    } catch (error) {
      rethrowServiceError('Creating the ticket', error)
    }
  }

  /* ------------------------- triage ------------------------- */

  async updateStatus(
    id: string,
    status: TicketStatus,
    _agent?: Agent,
    options?: TicketMutationOptions,
  ): Promise<Ticket> {
    try {
      const updated = await api.patch<RawTicketDetail>(
        `/tickets/${encodeURIComponent(id)}/status`,
        { status, expected_version: expectedVersion('Updating the status', options) },
      )
      this.notify()
      return mapTicketDetail(updated)
    } catch (error) {
      rethrowServiceError('Updating the status', error)
    }
  }

  async updatePriority(
    id: string,
    priority: TicketPriority,
    _agent?: Agent,
    options?: TicketMutationOptions,
  ): Promise<Ticket> {
    try {
      const updated = await api.patch<RawTicketDetail>(
        `/tickets/${encodeURIComponent(id)}/priority`,
        {
          priority,
          expected_version: expectedVersion('Updating the priority', options),
        },
      )
      this.notify()
      return mapTicketDetail(updated)
    } catch (error) {
      rethrowServiceError('Updating the priority', error)
    }
  }

  async updateCategory(
    id: string,
    category: TicketCategory,
    _agent?: Agent,
    options?: TicketMutationOptions,
  ): Promise<Ticket> {
    try {
      const updated = await api.patch<RawTicketDetail>(
        `/tickets/${encodeURIComponent(id)}/category`,
        {
          category,
          expected_version: expectedVersion('Updating the category', options),
        },
      )
      this.notify()
      return mapTicketDetail(updated)
    } catch (error) {
      rethrowServiceError('Updating the category', error)
    }
  }

  async assignTicket(
    id: string,
    agentId: string | null,
    _agent?: Agent,
    options?: TicketMutationOptions,
  ): Promise<Ticket> {
    try {
      const updated = await api.patch<RawTicketDetail>(
        `/tickets/${encodeURIComponent(id)}/assignment`,
        {
          agent_id: agentId,
          expected_version: expectedVersion('Updating the assignment', options),
        },
      )
      this.notify()
      return mapTicketDetail(updated)
    } catch (error) {
      rethrowServiceError('Updating the assignment', error)
    }
  }

  async addInternalNote(id: string, note: string): Promise<TicketActivity> {
    try {
      const raw = await api.post<RawNoteResponse>(
        `/tickets/${encodeURIComponent(id)}/notes`,
        { content: note },
      )
      this.notify()
      // Notes are a dedicated staff-only resource; the timeline activity is
      // derived so callers keep rendering the workspace exactly as before.
      return {
        id: `note-${raw.id}`,
        ticketId: raw.ticket_id,
        replyId: null,
        actorName: raw.author.name,
        actorType: 'agent',
        action: 'note_added',
        detail: raw.content,
        createdAt: raw.created_at,
        isInternalNote: true,
      }
    } catch (error) {
      rethrowServiceError('Adding the internal note', error)
    }
  }

  /* ------------------------- replies ------------------------- */

  async getReplies(ticketId: string): Promise<CustomerReply[]> {
    try {
      const response = await api.get<RawReplyListResponse>(
        `/tickets/${encodeURIComponent(ticketId)}/replies?page_size=100`,
      )
      return response.items.map(mapReply)
    } catch (error) {
      rethrowServiceError('Loading replies', error)
    }
  }

  async getReply(replyId: string): Promise<CustomerReply | null> {
    try {
      const raw = await api.get<RawReplyDetail>(
        `/replies/${encodeURIComponent(replyId)}`,
      )
      return mapReply(raw)
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 404) {
        return null
      }
      rethrowServiceError('Loading the reply', error)
    }
  }

  async listPendingReplies(): Promise<CustomerReply[]> {
    try {
      const all = await this.fetchAllReplies()
      return all
        .filter((raw) => raw.state === 'pending_approval')
        .map(mapReply)
    } catch (error) {
      rethrowServiceError('Loading pending replies', error)
    }
  }

  async listAllReplies(): Promise<
    Array<{ reply: CustomerReply; ticket: Ticket }>
  > {
    try {
      const all = await this.fetchAllWithTickets()
      return all.map((item) => ({
        reply: mapReply(item.reply),
        ticket: mapReplyTicketRef(item.ticket, item.reply.recipient?.email),
      }))
    } catch (error) {
      rethrowServiceError('Loading the approvals queue', error)
    }
  }

  async saveReplyDraft(
    ticketId: string,
    body: string,
  ): Promise<CustomerReply> {
    try {
      const raw = await api.post<RawReplyDetail>(
        `/tickets/${encodeURIComponent(ticketId)}/replies`,
        { body },
      )
      this.notify()
      return mapReply(raw)
    } catch (error) {
      if (
        error instanceof ApiClientError &&
        error.code === 'reply_already_exists'
      ) {
        // One active (non-sent) reply exists: edit it instead of failing.
        const replies = await this.getReplies(ticketId)
        const active = replies.find((reply) => reply.state !== 'sent')
        if (active) {
          const raw = await api.patch<RawReplyDetail>(
            `/replies/${encodeURIComponent(active.id)}`,
            { body },
          )
          this.notify()
          return mapReply(raw)
        }
      }
      rethrowServiceError('Saving the reply draft', error)
    }
  }

  async submitReplyForApproval(replyId: string): Promise<CustomerReply> {
    try {
      const raw = await api.post<RawReplyDetail>(
        `/replies/${encodeURIComponent(replyId)}/submit`,
        {},
      )
      this.notify()
      return mapReply(raw)
    } catch (error) {
      rethrowServiceError('Submitting the reply for approval', error)
    }
  }

  async approveReply(replyId: string): Promise<CustomerReply> {
    try {
      const { version } = await this.getCurrentVersion(replyId)
      const raw = await api.post<RawReplyDetail>(
        `/replies/${encodeURIComponent(replyId)}/approve`,
        { version },
      )
      this.notify()
      return mapReply(raw)
    } catch (error) {
      rethrowServiceError('Approving the reply', error)
    }
  }

  async requestReplyChanges(
    replyId: string,
    feedback: string,
  ): Promise<CustomerReply> {
    try {
      const { version } = await this.getCurrentVersion(replyId)
      const raw = await api.post<RawReplyDetail>(
        `/replies/${encodeURIComponent(replyId)}/request-changes`,
        { version, comment: feedback },
      )
      this.notify()
      return mapReply(raw)
    } catch (error) {
      rethrowServiceError('Requesting reply changes', error)
    }
  }

  async markReplySent(replyId: string): Promise<CustomerReply> {
    try {
      const result = await api.post<{ reply: RawReplyDetail }>(
        `/replies/${encodeURIComponent(replyId)}/send-demo`,
        {},
      )
      this.notify()
      return mapReply(result.reply)
    } catch (error) {
      rethrowServiceError('Marking the reply as sent', error)
    }
  }

  /* ------------------------- internals ------------------------- */

  private async getCurrentVersion(
    replyId: string,
  ): Promise<{ version: number }> {
    const raw = await api.get<RawReplyDetail>(
      `/replies/${encodeURIComponent(replyId)}`,
    )
    return { version: raw.version }
  }

  private async fetchActiveTickets(): Promise<Ticket[]> {
    const items: Ticket[] = []
    let page = 1
    for (;;) {
      const response = await api.get<RawTicketListResponse>(
        `/tickets?page=${page}&page_size=100&sort_by=created_at&sort_dir=asc` +
          `&status=${ACTIVE_STATUSES.join('&status=')}`,
      )
      for (const raw of response.items) items.push(mapTicketSummary(raw))
      const pageCount = Math.max(1, response.pagination.page_count)
      if (page >= pageCount || page >= MAX_PAGES) break
      page += 1
    }
    return items
  }

  private async fetchAllReplies(): Promise<RawReplySummary[]> {
    // `GET /replies` returns reply+ticket pairs (`ReplyAllListResponse`), not
    // bare reply summaries. Reuse the same traversal so pending-reply and
    // analytics consumers see persisted records instead of `undefined`.
    const pairs = await this.fetchAllWithTickets()
    return pairs.map((item) => item.reply)
  }

  private async fetchAllWithTickets(): Promise<RawReplyWithTicket[]> {
    const raws: RawReplyWithTicket[] = []
    let page = 1
    for (;;) {
      const response = await api.get<{
        items: RawReplyWithTicket[]
        pagination: RawPageMeta
      }>(`/replies?page=${page}&page_size=100`)
      raws.push(...response.items)
      const pageCount = Math.max(1, response.pagination.page_count)
      if (page >= pageCount || page >= MAX_PAGES) break
      page += 1
    }
    return raws
  }

  private async currentAgentId(): Promise<string | null> {
    if (this.currentAgentIdCache !== undefined) {
      return this.currentAgentIdCache
    }
    try {
      const profile = await api.get<RawAccountProfile>('/auth/me')
      this.currentAgentIdCache = profile.agent_id ?? null
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 401) {
        throw new ApiClientError(
          'Sign in with a linked agent account to use the "mine" filter.',
          { status: 403, code: 'forbidden' },
        )
      }
      rethrowServiceError('Resolving the signed-in agent', error)
    }
    return this.currentAgentIdCache
  }
}
