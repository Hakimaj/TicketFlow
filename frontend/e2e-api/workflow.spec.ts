import {
  expect,
  request as apiRequest,
  test,
  type Page,
} from '@playwright/test'

/**
 * End-to-end workflow against the real FastAPI backend and an isolated,
 * freshly seeded PostgreSQL database.
 *
 * Two separate accounts are used: an author agent and a reviewer. Nothing is
 * mocked — every step below is persisted through the API and re-read after a
 * full page reload.
 */

const PASSWORD = process.env.E2E_ACCOUNT_PASSWORD ?? 'E2eTicketflow!123'
const API_PORT = process.env.E2E_API_PORT ?? '8010'
const API_ORIGIN =
  process.env.E2E_API_ORIGIN ?? `http://127.0.0.1:${API_PORT}`
const API = `${API_ORIGIN}/api/v1`

const AGENT_EMAIL = 'e2e-agent@ticketflow.test'
const REVIEWER_EMAIL = 'e2e-reviewer@ticketflow.test'
const ADMIN_EMAIL = 'e2e-admin@ticketflow.test'

const CSRF_HEADERS = { 'X-Requested-With': 'ticketflow' }

async function loginApi(email: string, password = PASSWORD) {
  const context = await apiRequest.newContext()
  const response = await context.post(`${API}/auth/login`, {
    data: { email, password },
    headers: CSRF_HEADERS,
  })
  if (response.status() !== 200) {
    await context.dispose()
    throw new Error(`API login failed for ${email}: ${response.status()}`)
  }
  const body = (await response.json()) as { access_token: string }
  return { context, token: body.access_token }
}

function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

async function errorCode(response: {
  json: () => Promise<unknown>
}): Promise<string> {
  const body = (await response.json()) as {
    error?: { code?: string }
  }
  return body.error?.code ?? ''
}

const NOTE_MARKER = 'E2E private note marker 55103'
const REPLY_BODY =
  'Dear Dagimawi,\n\nThe VAT line on invoice #INV-55103 has been corrected and a revised invoice will be issued today.\n\nBest regards,\nDawit Mengistu'

async function signIn(page: Page, email: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(PASSWORD)
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

test('authenticated agent → review by another account → explicit demo send → persisted state', async ({
  page,
}) => {
  /* 1. Protected routes require a real session. */
  await page.goto('/tickets')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()

  await signIn(page, AGENT_EMAIL)
  // Sign-in returns to the page that required the session.
  await expect(page.getByRole('heading', { name: 'All Tickets' }).first()).toBeVisible()
  // API mode never shows the demo-data indicator.
  await expect(page.getByText(/Demo mode — in-memory sample data/)).toHaveCount(0)
  await expect(page.getByText(/Connected to the TicketFlow API/)).toBeVisible()

  /* 2. Agent updates a ticket and adds an internal note. */
  await page.goto('/tickets/TF-1046')
  await expect(page.locator('#priority-select')).toBeVisible()
  await page.locator('#priority-select').click()
  await page.getByRole('option', { name: 'Urgent' }).click()
  await expect(page.locator('#priority-select')).toContainText('Urgent')

  await page.getByLabel('Add internal note').fill(NOTE_MARKER)
  await page.getByRole('button', { name: 'Add internal note' }).click()
  await expect(
    page.getByText('Internal note added to activity timeline.'),
  ).toBeVisible()
  await expect(page.getByText(NOTE_MARKER)).toBeVisible()

  /* 3. Agent drafts and submits a reply. */
  await page.getByLabel('Reply Draft').fill(REPLY_BODY)
  await page.getByRole('button', { name: 'Submit for Approval' }).click()
  await expect(
    page.getByText('Reply submitted for supervisor approval.'),
  ).toBeVisible()

  /* 4. The author cannot approve their own reply. */
  await expect(page.getByRole('button', { name: 'Approve Reply' })).toHaveCount(0)
  await page.goto('/approvals')
  await expect(
    page.getByRole('heading', { name: 'Not available for your role' }),
  ).toBeVisible()

  await signOut(page)

  /* 5. A different, authorized reviewer approves the exact submitted version. */
  await signIn(page, REVIEWER_EMAIL)
  await page.goto('/approvals')
  await page
    .getByRole('textbox', { name: 'Search reply approvals' })
    .fill('TF-1046')
  const pendingCard = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'TF-1046' })
    .first()
  await expect(pendingCard).toBeVisible()
  await pendingCard.getByRole('button', { name: 'Review & Decide' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Approve Reply' }).click()
  await expect(
    page.getByText('Customer reply approved. Ready for sending.'),
  ).toBeVisible()

  /* 6. Approval does not send the reply implicitly. */
  await page.getByRole('button', { name: /^Approved \d+$/ }).click()
  const approvedCard = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'TF-1046' })
    .first()
  await expect(
    approvedCard.getByText('Approved · Ready to Send', { exact: true }),
  ).toBeVisible()
  await expect(approvedCard.getByText('Sent (Demo)', { exact: true })).toHaveCount(0)

  await signOut(page)

  /* 7. An explicit demo-send action persists the simulated send. */
  await signIn(page, AGENT_EMAIL)
  await page.goto('/tickets/TF-1046')
  await expect(page.getByText(/Reply Approved \(v\d+\)/)).toBeVisible()
  await page.getByRole('button', { name: 'Mark as Sent (Demo)' }).first().click()
  const sendDialog = page.getByRole('dialog')
  await expect(sendDialog.getByText(/No email is actually delivered/i)).toBeVisible()
  await sendDialog.getByRole('button', { name: 'Mark as Sent (Demo)' }).click()
  await expect(
    page.getByText(/marked as sent in demo mode/i).first(),
  ).toBeVisible()

  /* 8. A full reload restores the session and re-reads the persisted state. */
  await page.reload()
  await expect(page.locator('#priority-select')).toContainText('Urgent')
  await expect(page.getByText(NOTE_MARKER)).toBeVisible()
  await expect(page.getByLabel('Sent Message Content')).toHaveValue(
    /invoice #INV-55103/,
  )
  await expect(page.getByText(/marked as sent in demo mode/i).first()).toBeVisible()

  /* 9. Logout invalidates the session; protected API calls are rejected. */
  await signOut(page)
  const unauthenticated = await page.request.get(`${API_ORIGIN}/api/v1/tickets`)
  expect(unauthenticated.status()).toBe(401)

  await page.goto('/tickets')
  await expect(page).toHaveURL(/\/login$/)
})

test('API rejects bad auth and enforces role permissions', async () => {
  const anon = await apiRequest.newContext()
  try {
    const noCsrf = await anon.post(`${API}/auth/login`, {
      data: { email: AGENT_EMAIL, password: PASSWORD },
    })
    expect(noCsrf.status()).toBe(403)
    expect(await errorCode(noCsrf)).toBe('csrf_rejected')

    const badOrigin = await anon.post(`${API}/auth/login`, {
      data: { email: AGENT_EMAIL, password: PASSWORD },
      headers: { ...CSRF_HEADERS, Origin: 'https://evil.example.test' },
    })
    expect(badOrigin.status()).toBe(403)
    expect(await errorCode(badOrigin)).toBe('origin_rejected')

    const wrongPassword = await anon.post(`${API}/auth/login`, {
      data: { email: AGENT_EMAIL, password: 'definitely-not-the-password' },
      headers: CSRF_HEADERS,
    })
    expect(wrongPassword.status()).toBe(401)
    expect(await errorCode(wrongPassword)).toBe('invalid_credentials')
    const wrongBody = await wrongPassword.text()

    const unknownAccount = await anon.post(`${API}/auth/login`, {
      data: {
        email: 'nobody-e2e@ticketflow.test',
        password: 'definitely-not-the-password',
      },
      headers: CSRF_HEADERS,
    })
    expect(unknownAccount.status()).toBe(401)
    expect(await unknownAccount.text()).toBe(wrongBody)

    const anonymous = await anon.get(`${API}/tickets`)
    expect(anonymous.status()).toBe(401)
    expect(await errorCode(anonymous)).toBe('not_authenticated')

    const malformed = await anon.get(`${API}/tickets`, {
      headers: bearer('not-a-signed-jwt'),
    })
    expect(malformed.status()).toBe(401)
    expect(await errorCode(malformed)).toBe('invalid_token')
  } finally {
    await anon.dispose()
  }

  const agent = await loginApi(AGENT_EMAIL)
  try {
    const me = await agent.context.get(`${API}/auth/me`, {
      headers: bearer(agent.token),
    })
    expect(me.status()).toBe(200)
    expect((await me.json()).role).toBe('agent')
    expect(
      (
        await agent.context.get(`${API}/accounts`, {
          headers: bearer(agent.token),
        })
      ).status(),
    ).toBe(403)
  } finally {
    await agent.context.dispose()
  }

  const reviewer = await loginApi(REVIEWER_EMAIL)
  try {
    expect(
      (
        await reviewer.context.get(`${API}/accounts`, {
          headers: bearer(reviewer.token),
        })
      ).status(),
    ).toBe(403)
  } finally {
    await reviewer.context.dispose()
  }

  const admin = await loginApi(ADMIN_EMAIL)
  try {
    const accounts = await admin.context.get(`${API}/accounts`, {
      headers: bearer(admin.token),
    })
    expect(accounts.status()).toBe(200)
  } finally {
    await admin.context.dispose()
  }
})

test('even a reviewer cannot self-approve; approval does not send', async () => {
  const reviewer = await loginApi(REVIEWER_EMAIL)
  try {
    const created = await reviewer.context.post(
      `${API}/tickets/TF-1049/replies`,
      {
        data: { body: 'API E2E draft for the self-approval boundary.' },
        headers: bearer(reviewer.token),
      },
    )
    expect(created.status()).toBe(201)
    const draft = await created.json()
    expect(draft.state).toBe('draft')

    const submitted = await reviewer.context.post(
      `${API}/replies/${draft.id}/submit`,
      { data: {}, headers: bearer(reviewer.token) },
    )
    expect(submitted.status()).toBe(200)

    // The reviewer has replies:review, so this reaches the authorship rule
    // rather than being stopped by a generic role permission.
    const ownApproval = await reviewer.context.post(
      `${API}/replies/${draft.id}/approve`,
      { data: { version: 1 }, headers: bearer(reviewer.token) },
    )
    expect(ownApproval.status()).toBe(403)
    expect(await errorCode(ownApproval)).toBe('self_approval_forbidden')

    // A different authorized account may approve it.
    const admin = await loginApi(ADMIN_EMAIL)
    try {
      const approved = await admin.context.post(
        `${API}/replies/${draft.id}/approve`,
        { data: { version: 1 }, headers: bearer(admin.token) },
      )
      expect(approved.status()).toBe(200)
      const approvedBody = await approved.json()
      expect(approvedBody.state).toBe('approved')
      expect(approvedBody.sent_at).toBeNull()

      // A human approval is not a send: the reply is still approved, not sent.
      const afterApproval = await reviewer.context.get(
        `${API}/replies/${draft.id}`,
        { headers: bearer(reviewer.token) },
      )
      expect(afterApproval.status()).toBe(200)
      const stored = await afterApproval.json()
      expect(stored.state).toBe('approved')
      expect(stored.sent_at).toBeNull()
    } finally {
      await admin.context.dispose()
    }
  } finally {
    await reviewer.context.dispose()
  }
})

test('logout revokes both the access token and refresh session', async () => {
  const reviewer = await loginApi(REVIEWER_EMAIL)
  try {
    const state = await reviewer.context.storageState()
    const refreshCookie = state.cookies.find((cookie) =>
      cookie.name.includes('refresh'),
    )
    expect(refreshCookie).toBeTruthy()

    const logout = await reviewer.context.post(`${API}/auth/logout`, {
      headers: { ...CSRF_HEADERS, ...bearer(reviewer.token) },
    })
    expect(logout.status()).toBe(200)

    // The access token is session-bound and is rejected immediately.
    const protectedAfterLogout = await reviewer.context.get(
      `${API}/tickets`,
      { headers: bearer(reviewer.token) },
    )
    expect(protectedAfterLogout.status()).toBe(401)
    expect(await errorCode(protectedAfterLogout)).toBe('invalid_token')

    // Replaying the deleted refresh cookie cannot mint a new session.
    const refreshAfterLogout = await reviewer.context.post(
      `${API}/auth/refresh`,
      {
        headers: {
          ...CSRF_HEADERS,
          Cookie: `${refreshCookie!.name}=${refreshCookie!.value}`,
        },
      },
    )
    expect(refreshAfterLogout.status()).toBe(401)
    expect(await errorCode(refreshAfterLogout)).toBe('refresh_invalid')
  } finally {
    await reviewer.context.dispose()
  }
})

test('API failures surface a retryable error state', async ({ page }) => {
  await signIn(page, AGENT_EMAIL)
  const ticketList = /\/api\/v1\/tickets\?/
  await page.route(ticketList, (route) => route.abort('failed'))
  try {
    await page.goto('/tickets')
    await expect(page.getByText('Tickets could not be loaded')).toBeVisible()
  } finally {
    await page.unroute(ticketList)
  }
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(
    page.getByRole('heading', { name: 'All Tickets' }).first(),
  ).toBeVisible()
})
