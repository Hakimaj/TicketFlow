import {
  BarChart3,
  BellRing,
  Inbox,
  LayoutDashboard,
  ScrollText,
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
  | 'analytics'
  | 'activity'
  | 'settings'
  | 'ticket_detail'

/** Optional sidebar badge counters (unassigned / needs review). */
export type NavCounts = {
  unassigned?: number
  needs_review?: number
}

export interface NavItem {
  key: NavScope
  label: string
  path: string
  icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }>
  /** Primary items never show a counter; these two do when > 0. */
  counter?: 'unassigned' | 'needs_review'
  description: string
}

/**
 * Left sidebar navigation. Routes not implemented in Phase 1 still resolve
 * to placeholder pages so no entry is ever broken.
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
