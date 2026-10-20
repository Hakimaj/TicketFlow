/**
 * Types and domain models for Customer Reply drafting, approval workflow, and demo sending.
 */

export type ReplyState =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'changes_requested'
  | 'sent'

export interface CustomerReply {
  id: string
  ticketId: string
  authorId: string
  authorName: string
  body: string
  state: ReplyState
  version: number
  createdAt: string
  updatedAt: string
  submittedAt: string | null
  reviewedAt: string | null
  reviewerId: string | null
  reviewerName: string | null
  reviewerFeedback: string | null
  sentAt: string | null
  sentByActorName: string | null
}

export const REPLY_STATE_LABELS: Record<ReplyState, string> = {
  draft: 'Draft',
  pending_approval: 'Pending Approval',
  approved: 'Approved',
  changes_requested: 'Changes Requested',
  sent: 'Sent (Demo)',
}

