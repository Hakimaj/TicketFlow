import {
  BarChart3,
  BellRing,
  Inbox,
  LayoutDashboard,
  ScrollText,
  ShieldCheck,
  Ticket,
  UserRound,
  UsersRound,
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
  | 'accounts'
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
  /** Permission required to see the destination (server enforces it too). */
  permission?: string
  /** Feature that needs the API; hidden in explicit demo mode. */
  apiOnly?: boolean
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
    description: 'Assigned to your agent profile',
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
    permission: 'replies:review',
    description: 'Review and approve customer replies',
  },
  {
    key: 'analytics',
    label: 'Analytics',
    path: '/analytics',
    icon: BarChart3,
    description: 'Current workload, volume and reply states',
  },
  {
    key: 'activity',
    label: 'Activity Logs',
    path: '/activity',
    icon: ScrollText,
    description: 'System and agent audit trail',
  },
  {
    key: 'accounts',
    label: 'Accounts',
    path: '/accounts',
    icon: UsersRound,
    permission: 'accounts:manage',
    // Account provisioning exists only in the persistent API; demo mode has
    // no backend to manage, so the entry is omitted instead of erroring.
    apiOnly: true,
    description: 'Provision staff accounts and manage access',
  },
]
