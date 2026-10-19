import type {
  Agent,
  DashboardStats,
  Ticket,
  TicketActivity,
  TicketPage,
  TicketQuery,
} from '@/types/ticket'
import {
  ACTIVE_STATUSES,
  CATEGORY_LABELS,
  PRIORITY_RANK,
  TICKET_STATUSES,
} from '@/lib/ticket-config'
import { dayKey } from '@/lib/format'
import { DEMO_ACTIVITY, DEMO_AGENTS_BY_ID, DEMO_TICKETS } from '@/data'
import { TicketServiceError, type TicketService } from './ticketService'

/**
 * Phase 1 data source: the demonstration dataset, held in memory.
 *
 * Simulates a small amount of network latency so loading and error states
 * are exercised the way they will be against a real API. No data is ever
 * persisted and nothing pretends to be a live backend.
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

  constructor(tickets: Ticket[] = DEMO_TICKETS) {
    // Sorted newest-first; ordering guarantees stable pagination later.
    this.tickets = [...tickets].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    )
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
    return this.tickets.find((t) => t.id === id) ?? null
  }

  async getAgent(id: string | null): Promise<Agent | null> {
    if (!id) return null
    return DEMO_AGENTS_BY_ID.get(id) ?? null
  }

  async listActivity(limit?: number): Promise<TicketActivity[]> {
    await delay(SIMULATED_LATENCY_MS)
    const sorted = [...DEMO_ACTIVITY].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    )
    return typeof limit === 'number' ? sorted.slice(0, limit) : sorted
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
      statusCounts,
      receivedTrend,
      categoryDistribution,
      prioritySummary,
      recentTickets: all.slice(0, 7),
      recentActivity: [...DEMO_ACTIVITY]
        .sort(
          (a, b) =>
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
        )
        .slice(0, 6),
    }
  }
}
