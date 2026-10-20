import {
  BarChart3,
  BellRing,
  Inbox,
  LayoutDashboard,
  ScrollText,
  ShieldCheck,
  Ticket,
  UserRound,
} from 'lucide-react'
import type { ComponentType } from 'react'

export type NavScope =
  | 'overview'
  | 'all'
  | 'mine'
  | 'unassigned'
  | 'needs_review'
  | 'reply_approvals'
  | 'analytics'
  | 'activity'
  | 'settings'
  | 'ticket_detail'

/** Optional sidebar badge counters (unassigned / needs review / pending approvals). */
export type NavCounts = {
  unassigned?: number
  needs_review?: number
  pending_approvals?: number
}

export interface NavItem {
  key: NavScope
  label: string
  path: string
  icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }>
  /** Items with counters render a badge when count > 0. */
  counter?: 'unassigned' | 'needs_review' | 'pending_approvals'
  description: string
}

/**
 * Left sidebar navigation.
 */
export const NAV_ITEMS: NavItem[] = [
  {
    key: 'overview',
    label: 'Overview',
    path: '/',
    icon: LayoutDashboard,
    description: 'Support operations dashboard',
  },
  {
    key: 'all',
    label: 'All Tickets',
    path: '/tickets',
    icon: Ticket,
    description: 'Every ticket in the queue',
  },
  {
    key: 'mine',
    label: 'My Tickets',
    path: '/tickets/mine',
    icon: UserRound,
    description: 'Assigned to the demo user',
  },
  {
    key: 'unassigned',
    label: 'Unassigned',
    path: '/tickets/unassigned',
    icon: Inbox,
    counter: 'unassigned',
    description: 'Waiting for an owner',
  },
  {
    key: 'needs_review',
    label: 'Needs Review',
    path: '/tickets/needs-review',
    icon: BellRing,
    counter: 'needs_review',
    description: 'Flagged for human triage',
  },
  {
    key: 'reply_approvals',
    label: 'Reply Approvals',
    path: '/approvals',
    icon: ShieldCheck,
    counter: 'pending_approvals',
    description: 'Review and approve customer replies',
  },
  {
    key: 'analytics',
    label: 'Analytics',
    path: '/analytics',
    icon: BarChart3,
    description: 'Trends and team performance',
  },
  {
    key: 'activity',
    label: 'Activity Logs',
    path: '/activity',
    icon: ScrollText,
    description: 'System and agent audit trail',
  },
]
