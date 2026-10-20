import { describe, expect, it } from 'vitest'
import { DEMO_REPLIES, DEMO_TICKETS } from '@/data'
import { ACTIVE_STATUSES } from '@/lib/ticket-config'
import type { Agent, Ticket } from '@/types/ticket'
import { DemoTicketService } from '../demoTicketService'

/**
 * Analytics and activity-log domain tests. These validate the figures and the
 * privacy projection at the service boundary, where a future backend will
 * enforce the same rules.
 */

const AUTHOR: Agent = {
  id: 'AG-02',
  name: 'Hana Tesfaye',
  role: 'agent',
  team: 'billing_team',
  email: 'hana@ticketflow.demo',
}

const REVIEWER: Agent = {
  id: 'AG-01',
  name: 'Abebe Kebede',
  role: 'supervisor',
  team: 'customer_support',
  email: 'abebe@ticketflow.demo',
  isDemoUser: true,
}

function makeTicket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    id: 'TF-9100',
    subject: 'Analytics test ticket',
    description: 'Ticket used by analytics unit tests.',
    requesterName: 'Test Customer',
    requesterEmail: 'customer@example.demo',
    channel: 'web_form',
    category: 'billing',
    priority: 'normal',
    status: 'open',
    assignedTeam: 'billing_team',
    assignedAgentId: AUTHOR.id,
    createdAt: new Date(Date.now() - 2 * 86_400_000).toISOString(),
    updatedAt: new Date(Date.now() - 2 * 86_400_000).toISOString(),
    dueAt: null,
    suggestedCategory: null,
    suggestedPriority: null,
    reviewNote: null,
    ...overrides,
  }
}

describe('analytics service', () => {
  it('derives summary counts from the demo fixtures without inventing data', async () => {
    const service = new DemoTicketService()
    const stats = await service.getAnalytics('all')

    const active = DEMO_TICKETS.filter((t) => ACTIVE_STATUSES.includes(t.status))
    expect(stats.totalTickets).toBe(DEMO_TICKETS.length)
    expect(stats.activeTickets).toBe(active.length)
    expect(stats.unassignedTickets).toBe(
      active.filter((t) => t.assignedAgentId === null).length,
    )
    expect(stats.urgentHighTickets).toBe(
      active.filter((t) => t.priority === 'urgent' || t.priority === 'high').length,
    )
    expect(stats.needsReviewTickets).toBe(
      DEMO_TICKETS.filter((t) => t.status === 'needs_review').length,
    )
    expect(stats.pendingReplyApprovals).toBe(
      DEMO_REPLIES.filter((r) => r.state === 'pending_approval').length,
    )
    expect(stats.totalReplies).toBe(DEMO_REPLIES.length)
    expect(stats.agentWorkload.reduce((sum, row) => sum + row.count, 0)).toBe(
      active.length,
    )
    expect(
      stats.replyStateDistribution.reduce((sum, row) => sum + row.count, 0),
    ).toBe(DEMO_REPLIES.length)
  })

  it('applies the selected window to creation and sent timestamps', async () => {
    const service = new DemoTicketService()
    const all = await service.getAnalytics('all')
    const week = await service.getAnalytics(7)

    expect(week.volumeTrend).toHaveLength(7)
    expect(week.ticketsCreatedInRange).toBeLessThanOrEqual(all.ticketsCreatedInRange)
    expect(week.repliesCreatedInRange).toBeLessThanOrEqual(all.repliesCreatedInRange)
    expect(week.sentRepliesInRange).toBeLessThanOrEqual(all.sentRepliesInRange)
    expect(new Date(week.rangeStart).getTime()).toBeGreaterThan(
      new Date(all.rangeStart).getTime(),
    )
  })

  it('handles an empty analysis window without fabricated values', async () => {
    const oldTicket = makeTicket({
      createdAt: new Date(Date.now() - 60 * 86_400_000).toISOString(),
      updatedAt: new Date(Date.now() - 60 * 86_400_000).toISOString(),
    })
    const service = new DemoTicketService([oldTicket], [], [])
    const stats = await service.getAnalytics(7)

    expect(stats.ticketsCreatedInRange).toBe(0)
    expect(stats.volumeTrend).toHaveLength(7)
    expect(stats.volumeTrend.every((point) => point.created === 0)).toBe(true)
    // Current-state distribution still reflects the ticket honestly.
    expect(stats.totalTickets).toBe(1)
  })

  it('reflects triage mutations in current-state analytics', async () => {
    const service = new DemoTicketService(
      [makeTicket({ status: 'open', assignedAgentId: null, priority: 'low' })],
      [],
      [],
    )
    const before = await service.getAnalytics('all')
    expect(before.unassignedTickets).toBe(1)
    expect(before.urgentHighTickets).toBe(0)

    await service.assignTicket('TF-9100', AUTHOR.id, REVIEWER)
    await service.updatePriority('TF-9100', 'urgent', REVIEWER)
    const after = await service.getAnalytics('all')

    expect(after.unassignedTickets).toBe(0)
    expect(after.urgentHighTickets).toBe(1)
    expect(after.activeTickets).toBe(1)
  })

  it('keeps the volume trend consistent with windowed creation totals', async () => {
    const service = new DemoTicketService()
    const week = await service.getAnalytics(7)

    const createdFromTrend = week.volumeTrend.reduce(
      (sum, point) => sum + point.created,
      0,
    )
    expect(createdFromTrend).toBe(week.ticketsCreatedInRange)
    expect(week.volumeTrend).toHaveLength(7)
  })

  it('reflects reply approval and demo-send transitions in analytics', async () => {
    const service = new DemoTicketService([makeTicket()], [], [])
    const draft = await service.saveReplyDraft('TF-9100', 'Hello customer.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)

    expect((await service.getAnalytics('all')).pendingReplyApprovals).toBe(1)

    await service.approveReply(draft.id, REVIEWER)
    const approved = await service.getAnalytics('all')
    expect(approved.pendingReplyApprovals).toBe(0)
    expect(approved.sentRepliesInRange).toBe(0)

    await service.markReplySent(draft.id, REVIEWER)
    const sent = await service.getAnalytics('all')
    expect(sent.sentRepliesInRange).toBe(1)
    expect(
      sent.replyStateDistribution.find((row) => row.state === 'sent')?.count,
    ).toBe(1)
  })

  it('keeps ticket-level review separate from reply approval', async () => {
    const service = new DemoTicketService(
      [makeTicket({ status: 'needs_review' })],
      [],
      [],
    )
    const draft = await service.saveReplyDraft('TF-9100', 'Hello customer.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)
    const stats = await service.getAnalytics('all')

    expect(stats.needsReviewTickets).toBe(1)
    expect(stats.activeTickets).toBe(0)
    expect(stats.pendingReplyApprovals).toBe(1)
  })
})

describe('activity log projection', () => {
  it('never exposes note bodies, drafts or reviewer feedback', async () => {
    const NOTE = 'CONFIDENTIAL internal note body'
    const FEEDBACK = 'Sensitive reviewer feedback text'
    const REPLY_BODY = 'Full customer-facing reply draft body'
    const service = new DemoTicketService([makeTicket()], [], [])

    await service.addInternalNote('TF-9100', NOTE, AUTHOR)
    const draft = await service.saveReplyDraft('TF-9100', REPLY_BODY, AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)
    await service.requestReplyChanges(draft.id, FEEDBACK, REVIEWER)

    const page = await service.listActivityLog({ page: 1, pageSize: 50 })
    const combined = page.items.map((entry) => entry.summary).join(' ')

    expect(page.total).toBeGreaterThan(0)
    expect(combined).not.toContain(NOTE)
    expect(combined).not.toContain(FEEDBACK)
    expect(combined).not.toContain(REPLY_BODY)
    expect(
      page.items.find((entry) => entry.action === 'note_added')?.summary,
    ).toBe('Internal note added to the ticket.')
    expect(
      page.items.find((entry) => entry.action === 'reply_changes_requested')?.summary,
    ).toBe('Changes requested on the customer reply draft.')
  })

  it('links reply events to their reply and supports ticket search', async () => {
    const service = new DemoTicketService([makeTicket()], [], [])
    const draft = await service.saveReplyDraft('TF-9100', 'Draft body.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)

    const page = await service.listActivityLog({
      search: 'TF-9100',
      page: 1,
      pageSize: 50,
    })
    const replyEvent = page.items.find((entry) => entry.action === 'reply_submitted')

    expect(page.items.every((entry) => entry.ticketId === 'TF-9100')).toBe(true)
    expect(replyEvent?.replyId).toBe(draft.id)
  })

  it('searches by human-readable action label', async () => {
    const service = new DemoTicketService([makeTicket()], [], [])
    await service.addInternalNote('TF-9100', 'Internal only.', AUTHOR)
    const draft = await service.saveReplyDraft('TF-9100', 'Draft body.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)

    const submitted = await service.listActivityLog({
      search: 'Reply submitted',
      page: 1,
      pageSize: 50,
    })
    expect(submitted.items).toHaveLength(1)
    expect(submitted.items[0]?.action).toBe('reply_submitted')

    const notes = await service.listActivityLog({
      search: 'Internal note added',
      page: 1,
      pageSize: 50,
    })
    expect(notes.items).toHaveLength(1)
    expect(notes.items[0]?.action).toBe('note_added')
    expect(notes.items[0]?.summary).toBe('Internal note added to the ticket.')
  })

  it('filters by action and actor, sorts and paginates', async () => {
    const service = new DemoTicketService([makeTicket()], [], [])
    await service.addInternalNote('TF-9100', 'Internal only.', AUTHOR)
    const draft = await service.saveReplyDraft('TF-9100', 'Draft body.', AUTHOR)
    await service.submitReplyForApproval(draft.id, AUTHOR)

    const actions = await service.listActivityLog({
      actions: ['reply_submitted'],
      page: 1,
      pageSize: 20,
    })
    expect(actions.items).toHaveLength(1)
    expect(actions.items[0]?.action).toBe('reply_submitted')

    const byActor = await service.listActivityLog({
      actorName: REVIEWER.name,
      page: 1,
      pageSize: 20,
    })
    expect(byActor.items.every((entry) => entry.actorName === REVIEWER.name)).toBe(
      true,
    )

    const asc = await service.listActivityLog({
      sortDir: 'asc',
      page: 1,
      pageSize: 20,
    })
    expect(asc.items.length).toBeGreaterThan(1)
    expect(new Date(asc.items[0]!.createdAt).getTime()).toBeLessThanOrEqual(
      new Date(asc.items[1]!.createdAt).getTime(),
    )

    const firstPage = await service.listActivityLog({ page: 1, pageSize: 2 })
    const secondPage = await service.listActivityLog({ page: 2, pageSize: 2 })
    expect(firstPage.items).toHaveLength(2)
    expect(firstPage.items[0]?.id).not.toBe(secondPage.items[0]?.id)
    expect(firstPage.pageCount).toBeGreaterThan(1)
  })

  it('reports actor and action facets from the same records', async () => {
    const service = new DemoTicketService()
    const facets = await service.getActivityLogFacets()

    expect(facets.actors.some((actor) => actor.name === 'Hana Tesfaye')).toBe(true)
    expect(
      facets.actions.some((entry) => entry.action === 'reply_approved'),
    ).toBe(true)
    expect(facets.actions.reduce((sum, entry) => sum + entry.count, 0)).toBeGreaterThan(
      0,
    )
  })
})
