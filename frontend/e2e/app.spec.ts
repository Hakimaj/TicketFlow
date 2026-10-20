import { expect, test, type Page } from '@playwright/test'

/**
 * Browser-level workflows against the demo frontend. Each test starts from a
 * fresh page load, which resets the in-memory demo service.
 */

const NAV_ITEMS: Array<{ label: string; path: string }> = [
  { label: 'Overview', path: '/' },
  { label: 'All Tickets', path: '/tickets' },
  { label: 'My Tickets', path: '/tickets/mine' },
  { label: 'Unassigned', path: '/tickets/unassigned' },
  { label: 'Needs Review', path: '/tickets/needs-review' },
  { label: 'Reply Approvals', path: '/approvals' },
  { label: 'Analytics', path: '/analytics' },
  { label: 'Activity Logs', path: '/activity' },
]

async function expectPath(page: Page, path: string) {
  await expect.poll(() => new URL(page.url()).pathname).toBe(path)
}

test('primary navigation resolves every destination and marks the active route', async ({
  page,
}) => {
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Main navigation' })

  for (const item of NAV_ITEMS) {
    await nav.getByRole('link', { name: item.label }).click()
    await expectPath(page, item.path)
    await expect(nav.getByRole('link', { name: item.label })).toHaveAttribute(
      'aria-current',
      'page',
    )
  }

  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await expectPath(page, '/settings')
  await expect(
    page.getByRole('heading', { name: 'Settings', level: 1 }).last(),
  ).toBeVisible()
})

test('analytics derives current metrics, updates the range and links to queues', async ({
  page,
}) => {
  await page.goto('/analytics')
  await expect(
    page.getByRole('heading', { name: 'Analytics', level: 1 }).last(),
  ).toBeVisible()

  // Seeded demo data contains exactly two replies awaiting approval.
  await expect(
    page.getByRole('group', { name: 'Replies awaiting approval · current: 2' }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: /Reply Approvals/ })).toContainText(
    '2',
  )

  const thirtyDayLabel = await page
    .getByRole('group', { name: /Tickets created · last 30 days/ })
    .getAttribute('aria-label')
  const thirtyDayCount = Number(thirtyDayLabel?.match(/: (\d+)$/)?.[1])
  expect(Number.isFinite(thirtyDayCount)).toBe(true)

  await page.getByRole('button', { name: '7 days', exact: true }).click()
  await expect(
    page.getByRole('group', { name: /Tickets created · last 7 days/ }),
  ).toBeVisible()
  const sevenDayLabel = await page
    .getByRole('group', { name: /Tickets created · last 7 days/ })
    .getAttribute('aria-label')
  const sevenDayCount = Number(sevenDayLabel?.match(/: (\d+)$/)?.[1])
  expect(sevenDayCount).toBeLessThanOrEqual(thirtyDayCount)

  // Chart definitions are present and no unsupported KPI is claimed.
  await expect(page.getByText('Ticket volume')).toBeVisible()
  await expect(page.getByText('Workload by assignee')).toBeVisible()
  await expect(page.getByText(/No invented KPIs/)).toBeVisible()

  await page.getByRole('link', { name: 'Filter', exact: true }).click()
  await expectPath(page, '/tickets')
  await expect(page).toHaveURL(/priority=urgent,high/)

  // The link must actually filter the queue, not just change the URL.
  const queue = page.getByRole('table').first()
  await expect(queue).toBeVisible()
  await expect(queue.getByText('Low', { exact: true })).toHaveCount(0)
  await expect(queue.getByText('Normal', { exact: true })).toHaveCount(0)
})

test('analytics and activity logs reflect triage changes made in another view', async ({
  page,
}) => {
  await page.goto('/analytics')
  const urgentHigh = page.getByRole('group', {
    name: /Urgent & high active · current/,
  })
  await expect(urgentHigh).toBeVisible()
  const before = Number(
    (await urgentHigh.getAttribute('aria-label'))?.match(/: (\d+)$/)?.[1],
  )
  expect(Number.isFinite(before)).toBe(true)

  const nav = page.getByRole('navigation', { name: 'Main navigation' })
  await nav.getByRole('link', { name: 'All Tickets' }).click()
  await page
    .getByRole('searchbox', { name: 'Search this queue' })
    .fill('TF-1046')
  const ticketRow = page.getByRole('row').filter({ hasText: 'TF-1046' }).first()
  await expect(ticketRow).toBeVisible()
  await ticketRow.click()
  await expectPath(page, '/tickets/TF-1046')

  // TF-1046 starts as High priority; moving it to Low must be reflected in the
  // current-state analytics rather than a cached first render.
  await page.locator('#priority-select').click()
  await page.getByRole('option', { name: 'Low', exact: true }).click()
  await expect(page.locator('#priority-select')).toContainText('Low')

  await nav.getByRole('link', { name: 'Analytics' }).click()
  await expect(
    page.getByRole('group', {
      name: `Urgent & high active · current: ${before - 1}`,
    }),
  ).toBeVisible()

  await nav.getByRole('link', { name: 'Activity Logs' }).click()
  const table = page.getByRole('table', { name: 'Activity log events' })
  await expect(
    page.getByText('Priority changed from High to Low.').first(),
  ).toBeVisible()

  // Searching by the human-readable action label filters the same records.
  await page
    .getByRole('textbox', {
      name: 'Search activity by ticket, actor or action',
    })
    .fill('Priority changed')
  await expect.poll(async () => table.getByRole('row').count()).toBe(2)
  await expect(
    table.getByText('Priority changed', { exact: true }).first(),
  ).toBeVisible()
})

test('activity logs search, filter, clear and never expose note content', async ({
  page,
}) => {
  await page.goto('/activity')
  const table = page.getByRole('table', { name: 'Activity log events' })
  await expect(table).toBeVisible()
  await expect(page.getByRole('cell', { name: 'TF-1051' }).first()).toBeVisible()

  const initialRows = await table.getByRole('row').count()
  const search = page.getByRole('textbox', {
    name: 'Search activity by ticket, actor or action',
  })
  await search.fill('TF-1051')
  await expect
    .poll(async () => table.getByRole('row').count())
    .toBeLessThan(initialRows)
  expect(await table.getByRole('cell', { name: 'TF-1051' }).count()).toBeGreaterThan(
    1,
  )

  await search.fill('no-such-event-xyz')
  await expect(page.getByText('No events match these filters')).toBeVisible()
  await page
    .getByRole('button', { name: 'Clear filters' })
    .first()
    .click()
  await expect(table).toBeVisible()

  // Sorting changes the visible order, not just the control value.
  const newestFirstRow = await table.getByRole('row').nth(1).innerText()
  await page.locator('#activity-sort').click()
  await page.getByRole('option', { name: 'Oldest first' }).click()
  await expect
    .poll(async () => table.getByRole('row').nth(1).innerText())
    .not.toBe(newestFirstRow)
  await page.locator('#activity-sort').click()
  await page.getByRole('option', { name: 'Newest first' }).click()
  await expect
    .poll(async () => table.getByRole('row').nth(1).innerText())
    .toBe(newestFirstRow)

  await page.locator('#activity-action').click()
  await page.getByRole('option', { name: /Reply approved/ }).click()
  await expect(
    page.getByText('Customer reply approved for demo sending.').first(),
  ).toBeVisible()

  // Add an internal note with a unique marker, then confirm the general log
  // neither displays nor searches that content.
  const marker = 'PRIVATE-NOTE-MARKER-8472'
  await page.goto('/tickets/TF-1046')
  await page.getByLabel('Add internal note').fill(marker)
  await page.getByRole('button', { name: 'Add internal note' }).click()
  await expect(page.getByText('Internal note added to activity timeline.')).toBeVisible()

  // SPA navigation preserves the in-memory service state.
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Activity Logs' })
    .click()
  const activitySearch = page.getByRole('textbox', {
    name: 'Search activity by ticket, actor or action',
  })
  await activitySearch.fill('TF-1046')
  await expect(
    page.getByText('Internal note added to the ticket.').first(),
  ).toBeVisible()
  await activitySearch.fill(marker)
  await expect(page.getByText('No events match these filters')).toBeVisible()
  await expect(page.getByText(marker)).toHaveCount(0)
})

test('settings preferences persist locally and change actual behaviour', async ({
  page,
}) => {
  await page.goto('/settings')
  await expect(page.getByText('Demo identity', { exact: true })).toBeVisible()
  await expect(page.getByText(/not an authenticated account/i)).toBeVisible()

  await page.getByRole('radio', { name: /Compact/ }).check()
  await expect(page.locator('html')).toHaveAttribute('data-density', 'compact')

  await page.reload()
  await expect(page.getByRole('radio', { name: /Compact/ })).toBeChecked()
  await expect(page.locator('html')).toHaveAttribute('data-density', 'compact')

  await page.locator('#default-landing').click()
  await page.getByRole('option', { name: 'All Tickets' }).click()
  await page.goto('/')
  await expectPath(page, '/tickets')

  await page.goto('/settings')
  await page.getByRole('button', { name: 'Reset preferences' }).click()
  await expect(page.getByRole('radio', { name: /Comfortable/ })).toBeChecked()
  await expect(page.locator('html')).toHaveAttribute('data-density', 'comfortable')
  await expect(
    page.getByRole('button', { name: /Save|Connect|Test Connection/i }),
  ).toHaveCount(0)
})

test('ticket triage, reply submission, approval and explicit demo send', async ({
  page,
}) => {
  await page.goto('/tickets/TF-1046')
  const replyBox = page.getByLabel('Reply Draft')
  await expect(replyBox).toBeVisible()

  await page.locator('#priority-select').click()
  await page.getByRole('option', { name: 'Urgent' }).click()
  await expect(page.locator('#priority-select')).toContainText('Urgent')

  await page.locator('#agent-select').click()
  await page.getByRole('option', { name: /Abebe Kebede/ }).click()
  await expect(page.locator('#agent-select')).toContainText('Abebe Kebede')

  const draft =
    'Dear Dagimawi,\n\nThank you for flagging the VAT line on invoice #INV-55103. We have corrected the calculation and will issue a revised invoice today.\n\nBest regards,\nAbebe Kebede'
  await replyBox.fill(draft)
  await page.getByRole('button', { name: 'Submit for Approval' }).click()
  await expect(
    page.getByText('Reply submitted for supervisor approval.'),
  ).toBeVisible()

  // The sidebar counter is derived from shared service state: two seeded
  // pending replies plus this newly submitted one.
  const nav = page.getByRole('navigation', { name: 'Main navigation' })
  await expect(nav.locator('[aria-label="3 Reply Approvals"]')).toBeVisible()

  // Navigate within the SPA so the in-memory demo service is not reset.
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Reply Approvals' })
    .click()
  await page
    .getByRole('textbox', { name: 'Search reply approvals' })
    .fill('TF-1046')
  const pendingCard = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'TF-1046' })
    .first()
  await expect(pendingCard).toBeVisible()
  await pendingCard.getByRole('button', { name: 'Review & Decide' }).click()

  const reviewDialog = page.getByRole('dialog')
  await expect(reviewDialog).toBeVisible()
  await reviewDialog.getByRole('button', { name: 'Approve Reply' }).click()
  await expect(
    page.getByText('Customer reply approved. Ready for sending.'),
  ).toBeVisible()
  await expect(nav.locator('[aria-label="2 Reply Approvals"]')).toBeVisible()

  await page.getByRole('button', { name: /^Approved \d+$/ }).click()
  const approvedCard = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'TF-1046' })
    .first()
  await expect(
    approvedCard.getByText('Approved · Ready to Send', { exact: true }),
  ).toBeVisible()
  // Approval did not send implicitly.
  await expect(
    approvedCard.getByText('Sent (Demo)', { exact: true }),
  ).toHaveCount(0)

  await approvedCard.getByRole('button', { name: 'Mark as Sent (Demo)' }).click()
  const sendDialog = page.getByRole('dialog')
  await expect(
    sendDialog.getByText(/No email is actually delivered/i),
  ).toBeVisible()
  await sendDialog
    .getByRole('button', { name: 'Mark as Sent (Demo)' })
    .click()
  await expect(
    page.getByText(/Customer reply marked as sent in demo mode/i),
  ).toBeVisible()

  await page.getByRole('button', { name: /^Sent \(Demo\) \d+$/ }).click()
  const sentCard = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'TF-1046' })
    .first()
  await expect(sentCard.getByText('Sent (Demo)', { exact: true })).toBeVisible()

  await page.goBack()
  await expectPath(page, '/tickets/TF-1046')
  await expect(page.getByLabel('Sent Message Content')).toHaveValue(/Dear Dagimawi/)
  await expect(page.getByText(/marked as sent in demo mode/i).first()).toBeVisible()
  await expect(page.locator('#priority-select')).toContainText('Urgent')
})

test('mobile navigation keeps primary destinations accessible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/tickets')

  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('link', { name: 'Analytics' }).click()
  await expectPath(page, '/analytics')
  await expect(
    page.getByRole('button', { name: '7 days', exact: true }),
  ).toBeVisible()

  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)

  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  await page
    .getByRole('dialog')
    .getByRole('link', { name: 'Settings', exact: true })
    .click()
  await expectPath(page, '/settings')
  await expect(page.getByRole('radio', { name: /Comfortable/ })).toBeVisible()
})
