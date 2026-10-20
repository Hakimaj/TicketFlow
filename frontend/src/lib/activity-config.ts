import type { ActivityAction } from '@/types/ticket'

/**
 * Human-readable labels for every activity action the service records.
 * Shared by the dashboard feed, the ticket timeline and the Activity Logs
 * page so the vocabulary cannot drift between surfaces.
 */
export const ACTIVITY_ACTION_LABELS: Record<ActivityAction, string> = {
  created: 'Ticket created',
  categorized: 'Category changed',
  assigned: 'Assignment changed',
  replied_draft: 'Reply draft saved',
  replied_sent: 'Reply sent (demo)',
  status_changed: 'Status changed',
  escalated: 'Escalated',
  review_flagged: 'Flagged for review',
  merged: 'Tickets merged',
  resolved: 'Resolved',
  priority_changed: 'Priority changed',
  note_added: 'Internal note added',
  reply_submitted: 'Reply submitted for approval',
  reply_approved: 'Reply approved',
  reply_changes_requested: 'Reply changes requested',
}
