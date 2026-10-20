import { describe, expect, it } from 'vitest'
import { DEMO_REPLIES, DEMO_TICKETS } from '@/data'
import type { Agent, Ticket } from '@/types/ticket'
import { DemoTicketService } from '../demoTicketService'

/**
 * Reply-workflow domain tests.
 *
 * These exercise the shared service layer directly (not the UI) so the
 * approval gate and revision rules are verified where they are enforced.
 * They cover the bypass scenarios a user could attempt through UI controls
 * or direct service calls.
 */

const AUTHOR: Agent = {
  id: 'AG-02',
  name: 'Hana Tesfaye',
  role: 'agent',
  team: 'billing_team',
  email: 'hana.tesfaye@ticketflow.demo',
}

const REVIEWER: Agent = {
  id: 'AG-01',
  name: 'Abebe Kebede',
  role: 'supervisor',
  team: 'customer_support',
  email: 'abebe.kebede@ticketflow.demo',
  isDemoUser: true,
}

function makeTicket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    id: 'TF-9001',
    subject: 'Test ticket for reply workflow',
    description: 'Customer needs help with a billing issue.',
    requesterName: 'Marta Alemu',
    requesterEmail: 'marta@example.demo',
    channel: 'web_form',
    category: 'billing',
    priority: 'high',
    status: 'open',
    assignedTeam: 'billing_team',
    assignedAgentId: AUTHOR.id,
    createdAt: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    updatedAt: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    dueAt: null,
    suggestedCategory: null,
    suggestedPriority: null,
    reviewNote: null,
    ...overrides,
  }
}

function makeService() {
  return new DemoTicketService([makeTicket()], [], [])
}

/** Save → submit → approve. Returns the approved reply ID. */
async function approvedReply(service: DemoTicketService, body = 'Hello customer.') {
  const draft = await service.saveReplyDraft('TF-9001', body, AUTHOR)
  await service.submitReplyForApproval(draft.id, AUTHOR)
  await service.approveReply(draft.id, REVIEWER)
  return draft.id
}

describe('reply lifecycle', () => {
  it('saves a draft without submitting it', async () => {
    const service = makeService()
    const reply = await service.saveReplyDraft('TF-9001', 'Hello there.', AUTHOR)

    expect(reply.state).toBe('draft')
    expect(reply.version).toBe(1)
    expect(reply.submittedAt).toBeNull()
    expect(reply.reviewerId).toBeNull()
    expect(reply.sentAt).toBeNull()
  })

  it('submits for approval without approving or sending', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Hello there.', AUTHOR)
    const submitted = await service.submitReplyForApproval(draft.id, AUTHOR)

    expect(submitted.state).toBe('pending_approval')
    expect(submitted.submittedAt).not.toBeNull()
    expect(submitted.reviewerId).toBeNull()
    expect(submitted.sentAt).toBeNull()
  })

  it('approves without sending', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Hello there.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)
    const approved = await service.approveReply(draft.id, REVIEWER)

    expect(approved.state).toBe('approved')
    expect(approved.reviewerId).toBe(REVIEWER.id)
    expect(approved.reviewerName).toBe(REVIEWER.name)
    expect(approved.reviewedAt).not.toBeNull()
    expect(approved.sentAt).toBeNull()
  })

  it('marks an approved reply as sent and records actor, time and ticket status', async () => {
    const service = makeService()
    const replyId = await approvedReply(service)
    const sent = await service.markReplySent(replyId, REVIEWER)

    expect(sent.state).toBe('sent')
    expect(sent.sentAt).not.toBeNull()
    expect(sent.sentByActorName).toBe(REVIEWER.name)

    const ticket = await service.getTicket('TF-9001')
    expect(ticket?.status).toBe('pending')
  })

  it('runs the complete draft → submit → approve → send path', async () => {
    const service = makeService()
    const replyId = await approvedReply(service, 'Dear Marta, your refund is on its way.')

    const activities = await service.getTicketActivities('TF-9001')
    const actions = activities.map((activity) => activity.action)

    expect(actions).toContain('replied_draft')
    expect(actions).toContain('reply_submitted')
    expect(actions).toContain('reply_approved')

    const sent = await service.markReplySent(replyId, REVIEWER)
    const after = await service.getTicketActivities('TF-9001')
    expect(after.map((a) => a.action)).toContain('replied_sent')
    expect(sent.state).toBe('sent')
  })
})

describe('approval gate enforcement', () => {
  it('rejects sending a draft', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Not approved yet.', AUTHOR)

    await expect(service.markReplySent(draft.id, REVIEWER)).rejects.toThrow(
      /Approval gate rejected/,
    )
    expect((await service.getReply(draft.id))?.state).toBe('draft')
  })

  it('rejects sending a reply that is only pending approval', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Waiting for review.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)

    await expect(service.markReplySent(draft.id, REVIEWER)).rejects.toThrow(
      /Approval gate rejected/,
    )
    expect((await service.getReply(draft.id))?.sentAt).toBeNull()
  })

  it('rejects sending a reply with changes requested', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Needs revision.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)
    await service.requestReplyChanges(draft.id, 'Please add the refund timeline.', REVIEWER)

    await expect(service.markReplySent(draft.id, REVIEWER)).rejects.toThrow(
      /Approval gate rejected/,
    )
  })

  it('rejects duplicate sending', async () => {
    const service = makeService()
    const replyId = await approvedReply(service)
    await service.markReplySent(replyId, REVIEWER)

    await expect(service.markReplySent(replyId, REVIEWER)).rejects.toThrow(
      /already been sent/,
    )
  })

  it('rejects approving a reply that is not pending', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Still a draft.', AUTHOR)

    await expect(service.approveReply(draft.id, REVIEWER)).rejects.toThrow(
      /Only replies awaiting approval/,
    )

    await service.submitReplyForApproval(draft.id, AUTHOR)
    await service.approveReply(draft.id, REVIEWER)
    await expect(service.approveReply(draft.id, REVIEWER)).rejects.toThrow(
      /Only replies awaiting approval/,
    )
  })

  it('rejects duplicate submission', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Submit me once.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)

    await expect(service.submitReplyForApproval(draft.id, AUTHOR)).rejects.toThrow(
      /already awaiting approval/,
    )
  })

  it('rejects resubmitting an already-approved reply without a revision', async () => {
    const service = makeService()
    const replyId = await approvedReply(service)

    await expect(service.submitReplyForApproval(replyId, AUTHOR)).rejects.toThrow(
      /already approved/,
    )
  })
})

describe('revisions and stale approvals', () => {
  it('requires internal feedback when requesting changes', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Please review.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)

    await expect(
      service.requestReplyChanges(draft.id, '   ', REVIEWER),
    ).rejects.toThrow(/feedback|comments/i)

    // The reply must remain pending, not silently move states.
    expect((await service.getReply(draft.id))?.state).toBe('pending_approval')
  })

  it('records reviewer feedback on changes requested', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Please review.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)
    const revised = await service.requestReplyChanges(
      draft.id,
      'Mention the 24–48 hour reversal window.',
      REVIEWER,
    )

    expect(revised.state).toBe('changes_requested')
    expect(revised.reviewerFeedback).toContain('24–48')

    const activities = await service.getTicketActivities('TF-9001')
    const changes = activities.find((a) => a.action === 'reply_changes_requested')
    expect(changes?.detail).toContain('24–48')
  })

  it('bumps the version and reopens the draft when revising after feedback', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Initial draft.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)
    await service.requestReplyChanges(draft.id, 'Add the order number.', REVIEWER)

    const revised = await service.saveReplyDraft(
      'TF-9001',
      'Initial draft, now with order #ET-1.',
      AUTHOR,
    )

    expect(revised.state).toBe('draft')
    expect(revised.version).toBe(2)
    expect(revised.reviewerFeedback).toBeNull()
    expect(revised.submittedAt).toBeNull()
  })

  it('invalidates approval when an approved reply is edited', async () => {
    const service = makeService()
    const replyId = await approvedReply(service, 'Approved wording.')

    const revised = await service.saveReplyDraft('TF-9001', 'Changed wording.', AUTHOR)
    expect(revised.id).toBe(replyId)
    expect(revised.state).toBe('draft')
    expect(revised.version).toBe(2)
    expect(revised.reviewerId).toBeNull()
    expect(revised.reviewerName).toBeNull()

    // The stale approval cannot be used to send.
    await expect(service.markReplySent(replyId, REVIEWER)).rejects.toThrow(
      /Approval gate rejected/,
    )

    // Reapproval of the new version unlocks sending.
    await service.submitReplyForApproval(replyId, AUTHOR)
    const reapproved = await service.approveReply(replyId, REVIEWER)
    expect(reapproved.version).toBe(2)
    const sent = await service.markReplySent(replyId, REVIEWER)
    expect(sent.state).toBe('sent')
  })

  it('keeps approval when saving identical text', async () => {
    const service = makeService()
    const replyId = await approvedReply(service, 'No changes here.')

    const saved = await service.saveReplyDraft('TF-9001', 'No changes here.', AUTHOR)
    expect(saved.state).toBe('approved')
    expect(saved.version).toBe(1)

    const sent = await service.markReplySent(replyId, REVIEWER)
    expect(sent.state).toBe('sent')
  })

  it('withdraws a pending reply when it is edited', async () => {
    const service = makeService()
    const draft = await service.saveReplyDraft('TF-9001', 'Pending text.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)

    const edited = await service.saveReplyDraft('TF-9001', 'Edited after submission.', AUTHOR)
    expect(edited.state).toBe('draft')
    expect(edited.version).toBe(2)
    expect(edited.submittedAt).toBeNull()
  })
})

describe('shared state, counters and privacy', () => {
  it('updates the dashboard pending-approval count', async () => {
    const service = makeService()
    expect((await service.getDashboardStats()).pendingApprovals).toBe(0)

    const draft = await service.saveReplyDraft('TF-9001', 'Preview.', AUTHOR)
    expect((await service.getDashboardStats()).pendingApprovals).toBe(0)

    await service.submitReplyForApproval(draft.id, AUTHOR)
    expect((await service.getDashboardStats()).pendingApprovals).toBe(1)

    await service.approveReply(draft.id, REVIEWER)
    expect((await service.getDashboardStats()).pendingApprovals).toBe(0)
  })

  it('notifies subscribers on every workflow mutation', async () => {
    const service = makeService()
    let notifications = 0
    const unsubscribe = service.subscribe(() => {
      notifications += 1
    })

    const draft = await service.saveReplyDraft('TF-9001', 'Notify me.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)
    await service.approveReply(draft.id, REVIEWER)
    await service.markReplySent(draft.id, REVIEWER)
    unsubscribe()

    expect(notifications).toBe(4)
  })

  it('keeps customer replies and internal notes as separate records', async () => {
    const service = makeService()
    await service.saveReplyDraft('TF-9001', 'Customer-facing words.', AUTHOR)
    const note = await service.addInternalNote(
      'TF-9001',
      'Internal only: verify the refund reference before approving.',
      REVIEWER,
    )

    expect(note.isInternalNote).toBe(true)
    expect(note.action).toBe('note_added')

    const replies = await service.getReplies('TF-9001')
    expect(replies).toHaveLength(1)
    expect(replies[0].body).toBe('Customer-facing words.')
    expect(replies[0].body).not.toContain('Internal only')

    const activities = await service.getTicketActivities('TF-9001')
    expect(activities.some((a) => a.isInternalNote && a.id === note.id)).toBe(true)
  })

  it('keeps one active reply per ticket and starts a new draft after sending', async () => {
    const service = makeService()
    await service.saveReplyDraft('TF-9001', 'First version.', AUTHOR)
    await service.saveReplyDraft('TF-9001', 'First version, edited.', AUTHOR)

    expect(await service.getReplies('TF-9001')).toHaveLength(1)

    const replyId = await approvedReply(service, 'First version, final.')
    await service.markReplySent(replyId, REVIEWER)

    const next = await service.saveReplyDraft('TF-9001', 'Follow-up reply.', AUTHOR)
    expect(next.id).not.toBe(replyId)
    expect(next.state).toBe('draft')

    const all = await service.getReplies('TF-9001')
    expect(all).toHaveLength(2)
    expect(all.filter((r) => r.state === 'sent')).toHaveLength(1)
  })
})

describe('seeded demonstration data', () => {
  it('links every demo reply to a real ticket and greets that requester', () => {
    for (const reply of DEMO_REPLIES) {
      const ticket = DEMO_TICKETS.find((candidate) => candidate.id === reply.ticketId)
      expect(ticket, `missing ticket ${reply.ticketId}`).toBeDefined()
      const firstName = ticket?.requesterName.split(' ')[0] ?? ''
      expect(reply.body).toContain(firstName)
    }
  })

  it('derives the pending-approval counter from the seeded replies', async () => {
    const service = new DemoTicketService()
    const pending = await service.listPendingReplies()
    const stats = await service.getDashboardStats()

    expect(pending.length).toBeGreaterThan(0)
    expect(stats.pendingApprovals).toBe(pending.length)
  })
})
