/**
 * Core domain models for TicketFlow.
 *
 * These types are shared by the demonstration data layer today and by the
 * real API layer in a later phase. They intentionally model one ticket at a
 * time and avoid UI concerns.
 */

export type TicketStatus =
  | 'new'
  | 'open'
  | 'pending'
  | 'needs_review'
  | 'resolved'
  | 'closed'

export type TicketPriority = 'urgent' | 'high' | 'normal' | 'low'

export type TicketCategory =
  | 'billing'
  | 'delivery'
  | 'technical'
  | 'returns'
  | 'general'

export type TicketChannel = 'web_form' | 'email' | 'phone' | 'chat'

/** Teams that own whole ticket categories during triage. */
export type SupportTeam =
  | 'customer_support'
  | 'billing_team'
  | 'logistics_team'
  | 'technical_support'
  | 'returns_team'

/** Status and priority are kept as separate typed concepts on purpose. */
export interface Ticket {
  /** Human-readable ticket number, e.g. "TF-1042". */
  id: string
  subject: string
  description: string
  requesterName: string
  requesterEmail: string
  channel: TicketChannel
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  assignedTeam: SupportTeam | null
  assignedAgentId: string | null
  /** ISO 8601 timestamps. */
  createdAt: string
  updatedAt: string
  /** Internal SLA target; informational in Phase 1. */
  dueAt: string | null
  /**
   * Automation/AI assistance fields. Values here are simulated offline
   * suggestions from the future classification step; nothing calls an AI
   * service yet.
   */
  suggestedCategory: TicketCategory | null
  suggestedPriority: TicketPriority | null
  /** Set when triage could not confidently classify the ticket. */
  reviewNote: string | null
}

export type AgentRole = 'admin' | 'supervisor' | 'agent'

export interface Agent {
  id: string
  name: string
  role: AgentRole
  team: SupportTeam | null
  email: string
  /** True for the explicitly-labelled demo identity used in Phase 1. */
  isDemoUser?: boolean
}

export type ActivityAction =
  | 'created'
  | 'categorized'
  | 'assigned'
  | 'replied_draft'
  | 'replied_sent'
  | 'status_changed'
  | 'escalated'
  | 'review_flagged'
  | 'merged'
  | 'resolved'
  | 'priority_changed'
  | 'note_added'
  | 'reply_submitted'
  | 'reply_approved'
  | 'reply_changes_requested'

export type ActivityActorType = 'agent' | 'system' | 'automation'

export interface TicketActivity {
  id: string
  ticketId: string
  actorName: string
  actorType: ActivityActorType
  action: ActivityAction
  detail: string | null
  createdAt: string
  isInternalNote?: boolean
}

/* ------------------------------------------------------------------ */
/* Query / result contracts used by the service interface              */
/* ------------------------------------------------------------------ */

export type TicketSortField =
  | 'createdAt'
  | 'updatedAt'
  | 'priority'
  | 'status'
  | 'subject'
  | 'category'

export type SortDirection = 'asc' | 'desc'

export interface TicketQuery {
  /** Full-text match against ticket number, subject, requester or email. */
  search?: string | null
  statuses?: TicketStatus[] | null
  categories?: TicketCategory[] | null
  priorities?: TicketPriority[] | null
  assignedTeam?: SupportTeam | null
  /** "mine" → demo user, "unassigned" → no assignee; null → everything. */
  assignmentScope?: 'mine' | 'unassigned' | null
  sortBy?: TicketSortField
  sortDir?: SortDirection
  page: number
  pageSize: number
}

export interface TicketPage {
  items: Ticket[]
  total: number
  page: number
  pageSize: number
  pageCount: number
}

/** Aggregated numbers shown on the overview dashboard — always derived. */
export interface DashboardStats {
  openTickets: number
  unassignedTickets: number
  highPriorityOpen: number
  needsReviewTickets: number
  pendingApprovals: number
  /** One entry per status, for compact summaries. */
  statusCounts: Record<TicketStatus, number>
  /** Received per day over a trailing window, plus resolved per day. */
  receivedTrend: Array<{ date: string; received: number; resolved: number }>
  categoryDistribution: Array<{
    category: TicketCategory
    count: number
  }>
  /** Open tickets per priority for the compact summary table. */
  prioritySummary: Array<{
    priority: TicketPriority
    open: number
    pending: number
    needsReview: number
    total: number
  }>
  recentTickets: Ticket[]
  recentActivity: TicketActivity[]
}

export * from './reply'
