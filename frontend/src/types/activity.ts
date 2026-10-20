import type { ActivityAction, ActivityActorType } from './ticket'

/** Window length in days, or `'all'` for the full in-memory audit trail. */
export type ActivityRange = 7 | 30 | 'all'

/**
 * A sanitized operation log row. Unlike `TicketActivity` (which powers the
 * ticket workspace and may contain internal note text), this projection never
 * carries customer message bodies, reply drafts or reviewer comments.
 */
export interface ActivityLogEntry {
  id: string
  ticketId: string
  /** Present for reply-workflow events recorded after Phase 3. */
  replyId: string | null
  actorName: string
  actorType: ActivityActorType
  action: ActivityAction
  summary: string
  createdAt: string
}

export interface ActivityLogQuery {
  /** Matches ticket ID, actor name or the sanitized summary — never raw content. */
  search?: string | null
  actions?: ActivityAction[] | null
  actorName?: string | null
  range?: ActivityRange
  sortDir?: 'asc' | 'desc'
  page: number
  pageSize: number
}

export interface ActivityLogPage {
  items: ActivityLogEntry[]
  total: number
  page: number
  pageSize: number
  pageCount: number
}

export interface ActivityLogFacets {
  /** Actors present in the trail, with event counts, most active first. */
  actors: Array<{ name: string; count: number }>
  /** Action types present in the trail, with event counts. */
  actions: Array<{ action: ActivityAction; count: number }>
}
