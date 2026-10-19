import type {
  AgentRole,
  SortDirection,
  TicketCategory,
  TicketChannel,
  TicketPriority,
  TicketSortField,
  TicketStatus,
  SupportTeam,
} from '@/types/ticket'

/* ------------------------------------------------------------------ */
/* Status                                                              */
/* ------------------------------------------------------------------ */

export const TICKET_STATUSES: TicketStatus[] = [
  'new',
  'open',
  'pending',
  'needs_review',
  'resolved',
  'closed',
]

export const STATUS_LABELS: Record<TicketStatus, string> = {
  new: 'New',
  open: 'Open',
  pending: 'Pending',
  needs_review: 'Needs Review',
  resolved: 'Resolved',
  closed: 'Closed',
}

/**
 * Statuses that count as "active work" (i.e. not terminal). Used to derive
 * "open tickets" metrics from the dataset.
 */
export const ACTIVE_STATUSES: TicketStatus[] = ['new', 'open', 'pending']

/* ------------------------------------------------------------------ */
/* Priority                                                            */
/* ------------------------------------------------------------------ */

export const TICKET_PRIORITIES: TicketPriority[] = [
  'urgent',
  'high',
  'normal',
  'low',
]

export const PRIORITY_LABELS: Record<TicketPriority, string> = {
  urgent: 'Urgent',
  high: 'High',
  normal: 'Normal',
  low: 'Low',
}

/** Used for sorting priority columns (lower = more urgent). */
export const PRIORITY_RANK: Record<TicketPriority, number> = {
  urgent: 0,
  high: 1,
  normal: 2,
  low: 3,
}

/* ------------------------------------------------------------------ */
/* Categories / teams / channels                                       */
/* ------------------------------------------------------------------ */

export const TICKET_CATEGORIES: TicketCategory[] = [
  'billing',
  'delivery',
  'technical',
  'returns',
  'general',
]

export const CATEGORY_LABELS: Record<TicketCategory, string> = {
  billing: 'Billing',
  delivery: 'Delivery',
  technical: 'Technical',
  returns: 'Returns',
  general: 'General',
}

/** Team that owns each category during automated triage. */
export const CATEGORY_TEAM: Record<TicketCategory, SupportTeam> = {
  billing: 'billing_team',
  delivery: 'logistics_team',
  technical: 'technical_support',
  returns: 'returns_team',
  general: 'customer_support',
}

export const TEAM_LABELS: Record<SupportTeam, string> = {
  customer_support: 'Customer Support',
  billing_team: 'Billing Team',
  logistics_team: 'Logistics Team',
  technical_support: 'Technical Support',
  returns_team: 'Returns Team',
}

export const CHANNEL_LABELS: Record<TicketChannel, string> = {
  web_form: 'Web form',
  email: 'Email',
  phone: 'Phone',
  chat: 'Chat',
}

export const AGENT_ROLE_LABELS: Record<AgentRole, string> = {
  admin: 'Administrator',
  supervisor: 'Supervisor',
  agent: 'Support Agent',
}

/* ------------------------------------------------------------------ */
/* Sorting / facets                                                    */
/* ------------------------------------------------------------------ */

export const TICKET_SORT_FIELDS: TicketSortField[] = [
  'createdAt',
  'updatedAt',
  'priority',
  'status',
  'subject',
  'category',
]

export const SORT_FIELD_LABELS: Record<TicketSortField, string> = {
  createdAt: 'Date received',
  updatedAt: 'Last updated',
  priority: 'Priority',
  status: 'Status',
  subject: 'Subject',
  category: 'Category',
}

export const SORT_DIRECTION_LABELS: Record<SortDirection, string> = {
  asc: 'Ascending',
  desc: 'Descending',
}
