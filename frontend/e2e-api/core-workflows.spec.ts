import { expect, test, type Page } from '@playwright/test'

/**
 * API-mode end-to-end coverage for the Phase 10 capabilities: staff ticket
 * intake, administrator account management (including the forced password
 * change) and optimistic concurrency on ticket triage.
 *
 * Nothing is mocked: every assertion is backed by the real FastAPI backend and
 * the disposable, freshly migrated/seeded `*_e2e` PostgreSQL database prepared
 * by `backend/scripts/e2e_prepare.py`.
 */

const PASSWORD = process.env.E2E_ACCOUNT_PASSWORD ?? 'E2eTicketflow!123'

const AGENT_EMAIL = 'e2e-agent@ticketflow.test'
const REVIEWER_EMAIL = 'e2e-reviewer@ticketflow.test'
const ADMIN_EMAIL = 'e2e-admin@ticketflow.test'

const INTAKE_SUBJECT = 'E2E intake ticket 77411 — refund not received'
const INTAKE_DESCRIPTION =
  'The returned parcel was collected two weeks ago and the refund has not appeared on the card.'
const NEW_ACCOUNT_EMAIL = 'e2e.provisioned@ticketflow.test'
const NEW_ACCOUNT_PASSWORD = 'Provisioned!Passw0rd-2026'
const REPLACED_PASSWORD = 'Replaced!Passw0rd-2027'

async function signIn(page: Page, email: string, password = PASSWORD) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).not.toHaveURL(/\/login$/)
}

async function signOut(page: Page) {
  await page
    .locator('button[aria-label="Account menu"]:visible')
    .first()
    .click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
}

test('staff intake → queue, dashboard count, audit event and reload persistence', async ({
  page,
}) => {
  await signIn(page, AGENT_EMAIL)

  /* Baseline dashboard count before the ticket exists. */
  await page.goto('/')
  const openBefore = await page
    .getByRole('group', { name: /^Total open tickets: \d+$/ })
    .getAttribute('aria-label')
  expect(openBefore).toMatch(/^Total open tickets: (\d+)$/)
  const beforeCount = Number(openBefore!.split(': ')[1])

  /* The header action opens the real intake form (no preview dialog). */
  await page.getByRole('button', { name: 'New Ticket' }).first().click()
  await expect(page).toHaveURL(/\/tickets\/new$/)
  await expect(page.getByRole('heading', { name: 'New Ticket' })).toBeVisible()

  /* Client validation blocks an empty submit and keeps the form open. */
  await page.getByRole('button', { name: 'Create ticket' }).click()
  await expect(
    page.getByText('Enter the customer name (at least 2 characters).'),
  ).toBeVisible()
  await expect(
    page.getByText('Enter a subject of at least 3 characters.'),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/tickets\/new$/)

  /* A valid submission is persisted before the app navigates. */
  await page.getByLabel('Customer name').fill('E2E Intake Customer')
  await page.getByLabel('Customer email').fill('e2e.intake@example.test')
  await page.getByLabel('Subject').fill(INTAKE_SUBJECT)
  await page.getByLabel('Description').fill(INTAKE_DESCRIPTION)
  await page.getByLabel('Category').selectOption('billing')
  await page.getByLabel('Priority').selectOption('high')
  await page.getByLabel('Channel').selectOption('email')
  await page.getByRole('button', { name: 'Create ticket' }).click()

  /* API-confirmed creation opens the new ticket. */
  await expect(page).toHaveURL(/\/tickets\/TF-\d+$/)
  await expect(page.getByText(/created and added to the queue/)).toBeVisible()
  const ticketId = page.url().split('/').pop()!
  expect(ticketId).toMatch(/^TF-\d+$/)

  /* The created ticket carries the submitted values and the audit event. */
  await expect(page.getByText(INTAKE_SUBJECT).first()).toBeVisible()
  await expect(page.getByText('E2E Intake Customer').first()).toBeVisible()
  await expect(page.getByText('e2e.intake@example.test').first()).toBeVisible()
  await expect(
    page.getByText('Ticket created via email intake.'),
  ).toBeVisible()

  /* It appears in the queue it belongs to (new + unassigned). */
  await page.goto('/tickets/unassigned')
  await page.getByLabel('Search this queue').fill('E2E intake ticket 77411')
  await expect(
    page.getByRole('cell', { name: /E2E intake ticket 77411/ }),
  ).toBeVisible()
  await expect(
    page.getByRole('cell', { name: ticketId, exact: true }),
  ).toBeVisible()

  /* The dashboard count moved by exactly one. */
  await page.goto('/')
  const openAfter = await page
    .getByRole('group', { name: /^Total open tickets: \d+$/ })
    .getAttribute('aria-label')
  expect(Number(openAfter!.split(': ')[1])).toBe(beforeCount + 1)

  /* A full reload re-reads the persisted ticket and its audit trail, and the
     one-time success message does not reappear. */
  await page.goto(`/tickets/${ticketId}`)
  // Wait for the restored session and the rendered ticket before reloading;
  // reloading mid-refresh would legitimately look like token replay.
  await expect(
    page.getByRole('heading', { name: INTAKE_SUBJECT }),
  ).toBeVisible()
  await page.reload()
  await expect(
    page.getByRole('heading', { name: INTAKE_SUBJECT }),
  ).toBeVisible()
  await expect(
    page.getByText('Ticket created via email intake.'),
  ).toBeVisible()
  await expect(page.getByText(/created and added to the queue/)).toHaveCount(0)
})

test('a stale triage update is rejected instead of overwriting another operator', async ({
  browser,
}) => {
  const contextA = await browser.newContext()
  const contextB = await browser.newContext()
  const pageA = await contextA.newPage()
  const pageB = await contextB.newPage()

  try {
    /* Two independent operators open the same ticket at the same version. */
    await signIn(pageA, AGENT_EMAIL)
    await signIn(pageB, REVIEWER_EMAIL)
    await pageA.goto('/tickets/TF-1043')
    await pageB.goto('/tickets/TF-1043')
    await expect(pageA.locator('#priority-select')).toContainText('Low')
    await expect(pageB.locator('#priority-select')).toContainText('Low')

    /* Operator A saves first. */
    await pageA.locator('#priority-select').click()
    await pageA.getByRole('option', { name: 'Urgent', exact: true }).click()
    await expect(
      pageA.getByText('Ticket priority updated to Urgent.'),
    ).toBeVisible()

    /* Operator B still holds the old version: the server refuses the write. */
    await pageB.locator('#priority-select').click()
    await pageB.getByRole('option', { name: 'High', exact: true }).click()
    await expect(
      pageB.getByText(/Someone else changed this ticket first/),
    ).toBeVisible()

    /* B is shown the latest state (A's value) rather than a silent overwrite. */
    await expect(pageB.locator('#priority-select')).toContainText('Urgent')

    /* A's committed change survives B's rejected attempt. */
    await pageA.reload()
    await expect(pageA.locator('#priority-select')).toContainText('Urgent')
  } finally {
    await contextA.close()
    await contextB.close()
  }
})

test('administrator provisions, deactivates and reactivates an account, then the new user sets a password', async ({
  page,
}) => {
  await signIn(page, ADMIN_EMAIL)

  /* The Accounts section is only offered to administrators. */
  await page.getByRole('link', { name: 'Accounts' }).click()
  await expect(page).toHaveURL(/\/accounts$/)
  await expect(
    page.getByRole('main').getByRole('heading', { name: 'Accounts' }),
  ).toBeVisible()

  await page.getByRole('button', { name: 'New account' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Display name').fill('E2E Provisioned Agent')
  await dialog.getByLabel('Email').fill(NEW_ACCOUNT_EMAIL)
  await dialog.getByLabel('Role').selectOption('agent')
  await dialog.getByLabel('Linked support agent').selectOption('AG-05')
  await dialog.getByLabel('Initial password').fill(NEW_ACCOUNT_PASSWORD)
  await dialog.getByRole('button', { name: 'Create account' }).click()

  await expect(page.getByText(`${NEW_ACCOUNT_EMAIL} was provisioned.`)).toBeVisible()

  const row = page.getByRole('row').filter({ hasText: NEW_ACCOUNT_EMAIL })
  await expect(row.getByText('Active')).toBeVisible()
  await expect(row.getByText('Password change pending')).toBeVisible()

  /* Deactivation revokes the session and blocks sign-in. */
  await row.getByRole('button', { name: 'Deactivate' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Deactivate' }).click()
  await expect(
    page.getByText(`${NEW_ACCOUNT_EMAIL} was deactivated and its sessions were revoked.`),
  ).toBeVisible()
  await expect(row.getByText('Inactive')).toBeVisible()

  await signOut(page)
  await page.goto('/login')
  await page.getByLabel('Email').fill(NEW_ACCOUNT_EMAIL)
  await page.getByLabel('Password').fill(NEW_ACCOUNT_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByText('Invalid email or password.')).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)

  /* Reactivate, then the provisioned account must replace its password. */
  await signIn(page, ADMIN_EMAIL)
  await page.goto('/accounts')
  const inactiveRow = page.getByRole('row').filter({ hasText: NEW_ACCOUNT_EMAIL })
  await inactiveRow.getByRole('button', { name: 'Activate' }).click()
  await expect(
    page.getByText(`${NEW_ACCOUNT_EMAIL} can sign in again.`),
  ).toBeVisible()
  await signOut(page)

  await signIn(page, NEW_ACCOUNT_EMAIL, NEW_ACCOUNT_PASSWORD)
  await expect(page).toHaveURL(/\/change-password$/)
  await expect(
    page.getByRole('heading', { name: 'Set a new password' }),
  ).toBeVisible()

  await page.getByLabel('Current password').fill(NEW_ACCOUNT_PASSWORD)
  await page.getByLabel('New password', { exact: true }).fill(REPLACED_PASSWORD)
  await page.getByLabel('Confirm new password').fill(REPLACED_PASSWORD)
  await page.getByRole('button', { name: 'Save new password' }).click()

  /* The workspace now opens, and the new password survives a reload. */
  await expect(page).not.toHaveURL(/\/change-password$/)
  await expect(
    page.getByRole('main').getByRole('heading', { name: 'Overview' }),
  ).toBeVisible()
  await page.reload()
  await expect(page).toHaveURL(/\/($|\?)/)
  await expect(
    page.getByRole('main').getByRole('heading', { name: 'Overview' }),
  ).toBeVisible()
})

test('an agent cannot manage accounts', async ({ page }) => {
  await signIn(page, AGENT_EMAIL)

  /* No navigation entry is offered to a non-administrator. */
  await expect(page.getByRole('link', { name: 'Accounts' })).toHaveCount(0)

  /* Direct navigation renders the explicit forbidden state; the API also
     rejects the operation with `403` (covered by the backend test suite). */
  await page.goto('/accounts')
  await expect(
    page.getByRole('heading', { name: 'Not available for your role' }),
  ).toBeVisible()

  /* Demo fixtures are never substituted when the API denies access. */
  await page.goto('/tickets')
  await expect(page.getByText(/Connected to the TicketFlow API/)).toBeVisible()
  await expect(page.getByText(/Demo mode — in-memory sample data/)).toHaveCount(0)
})
