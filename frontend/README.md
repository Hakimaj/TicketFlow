# TicketFlow frontend (Phase 9: release readiness)

Support-ticket workspace built with React 19, TypeScript (strict), Vite 7,
Tailwind CSS 4, shadcn/ui-style components (Radix primitives + CVA),
React Router 7, Lucide icons and Recharts 3. It talks to the TicketFlow API by
default and signs users in against `/api/v1/auth`.

Phase 9 adds the containerised production build (`Dockerfile` + `nginx.conf`,
serving the SPA and proxying `/api/` on one origin) and runs these gates in CI
on every push and pull request.

## Run locally

```bash
npm install

# API mode (default): start the backend first
#   cd ../backend && python -m uvicorn app.main:app --reload --port 8000
npm run dev       # http://localhost:5173

# Explicit in-memory demo mode (no backend, visible demo banner)
VITE_DATA_MODE=demo npm run dev
```

Data-source configuration lives in `src/config/app-mode.ts`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `VITE_DATA_MODE` | `api` | Only the exact value `demo` selects the in-memory fixtures. Anything else (including unset) uses the API. |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` in dev, `/api/v1` in production | API origin. No credentials belong in frontend env files. |

Quality gates (all passing):

```bash
npm run lint
npm run typecheck
npm test          # Vitest domain, contract, mode-selection and session tests
npm run build
npm run test:e2e      # Playwright demo-mode browser tests (installed Chrome)
npm run test:e2e:api  # Playwright workflow against a real backend + disposable *_e2e DB
npm run preview   # serve dist/ at http://localhost:4173
```

The Playwright config starts Vite on port `4173` and uses the installed Chrome
channel, so no browser binary download is required. Set
`PLAYWRIGHT_BROWSERS_PATH` or adjust `playwright.config.ts` if Chrome is not
installed locally.

The API-backed config (`playwright.api.config.ts`) launches the backend with the
repository virtualenv interpreter by default; override it with
`E2E_PYTHON=python` (as CI does) on any other layout. It recreates an isolated
`*_e2e` database through `backend/scripts/e2e_prepare.py` and never touches the
development database.

## Architecture

```
src/
  app/                  App wiring, router (session guard), preferences, start page
  auth/                 AuthProvider, useAuth, route guard, permission mirror
  config/               Data-mode + API base URL resolution
  features/auth/        Sign-in page
  components/
    layout/             Sidebar, top header, app shell, nav config
    shared/             Cross-feature building blocks: badges, metric card,
                        page header, states (loading/empty/error), pagination,
                        confirm dialog
    ui/                 Design-system primitives (shadcn/ui conventions:
                        Radix + CVA + Tailwind tokens)
  features/
    dashboard/          Overview page, charts, panels, data hook
    tickets/            Ticket queues (all/mine/unassigned/needs-review),
                        table, filters hook, interactive ticket detail,
                        internal notes, reply composer
    approvals/          Reply Approvals supervisor review queue
    analytics/          Derived analytics page, charts, range-aware hook
    activity/           Sanitized activity log, filters, facets, hook
    settings/           Signed-in account, local preferences, workflow reference
  types/                Domain models (Ticket, Agent, TicketActivity,
                        CustomerReply, AccountProfile, queries, analytics,
                        activity log)
  data/                 Demonstration fixtures, used only in demo mode
  services/             TicketService interface, HttpTicketService (default),
                        DemoTicketService, apiClient, authService
  lib/                  cn(), formatting, ticket/activity config maps, shared
                        chart colors, reply templates, preference validation
e2e/                    Playwright demo-mode browser workflows
e2e-api/                Playwright workflows against the real backend
```

Key rules enforced by this structure:

- Feature code only ever calls the `TicketService` interface.
  `src/services/index.ts` resolves `HttpTicketService` by default and
  `DemoTicketService` only in explicit demo mode.
- Mock data lives exclusively in `src/data/`; no component carries ticket or
  reply fixtures. Assignee names come from `listAgents()`.
- Dashboard numbers, analytics, activity facets and the pending-approval
  counters are derived inside the service — never hardcoded in UI and never
  read from fixture arrays in components.
- Status and priority are separate typed unions; badges always pair an icon
  with text so color is never the only signal.
- Identity comes from the API session, never from the browser. The access
  token lives in module memory only; no ticket, reply or credential is written
  to `localStorage` (only the two presentation preferences are).
- Role-based UI (hidden navigation, hidden review actions) mirrors the server
  policy, which re-checks every endpoint. The reply approval gate and
  self-approval prevention are enforced server-side, not by hiding buttons.

## Reply drafting and approval workflow

The customer-reply flow is deliberately separate from ticket status and from
internal notes:

1. An agent edits a customer-facing draft in the ticket workspace and can
   insert an editable template. **Save Draft** stores it without submitting.
2. **Submit for Approval** moves the reply to `pending_approval`. It does not
   approve or send anything.
3. The supervisor queue at `/approvals` lists pending replies. The reviewer
   can **Approve**, or **Request Changes** with mandatory internal feedback.
4. Requested changes return the reply to its author (`changes_requested`).
   The next saved edit bumps the version, clears the decision and returns the
   reply to `draft`; it must be resubmitted and reapproved.
5. Editing an already-approved reply likewise invalidates that approval and
   bumps the version.
6. **Mark as Sent (Demo)** is only accepted by the service when the current
   reply version is approved. It records the actor and timestamp, writes an
   audit event and moves a new/open ticket to `pending`. No email or messaging
   service is contacted.

Reply lifecycle: `draft → pending_approval → approved → sent`, with
`pending_approval → changes_requested → draft` for revisions. Invalid
transitions (double submit, approving a draft, sending twice, requesting
changes without feedback) throw `TicketServiceError`.

State changes publish through `TicketService.subscribe`, so the sidebar badge,
dashboard banner, approvals queue, analytics and activity log refresh without a
page reload.

## Analytics

`/analytics` reads `ticketService.getAnalytics(range)` for 7 days, 30 days or
all data. It does not import fixtures or invent KPIs.

- Windowed metrics: tickets created, replies created, demo-sent replies.
- Current-state metrics: active workload, unassigned active, urgent/high
  active, ticket-level Needs Review, replies awaiting approval.
- Charts: daily ticket volume (created vs resolved/closed), status, priority,
  category, reply approval state and agent workload.
- Timestamp semantics: `Ticket.createdAt` for creation, `Reply.createdAt` for
  reply creation, `Reply.sentAt` for demo sends, and terminal-ticket
  `updatedAt` as an explicitly labelled resolution-time proxy.
- No SLA, resolution-duration, CSAT, revenue or historical snapshot data
  exists in the demo, so none is displayed.
- Ticket-level Needs Review is kept separate from reply approval everywhere.

## Activity Logs

`/activity` reads the sanitized `ActivityLogEntry` projection from
`listActivityLog(query)` and `getActivityLogFacets()`.

- Search matches ticket ID, actor, action label or the safe summary only.
- Filters: action, actor, date range; sort newest/oldest; pagination; clear.
- Ticket IDs link to the existing ticket detail page and return to the log.
- Reply events include the reply ID.
- Internal note bodies, customer-facing drafts, reviewer feedback and customer
  email addresses never appear in the general log. The same records still power
  the ticket timeline, where internal context belongs.

## Settings

`/settings` shows the signed-in account (or the labelled demo account in demo
mode), the role and the session state. Two preferences are genuinely applied
and stored only in this browser under `ticketflow.preferences.v1`:

- table density (`comfortable` / `compact`) via `data-density` on `<html>`;
- default landing page, applied when the app starts at `/` in a new tab/reload.

Values are validated on read; unknown values fall back to defaults, and **Reset
preferences** restores them. The workflow reference is derived from the domain
maps in `src/lib/ticket-config.ts` and `src/types/reply.ts`. The integration
status section is read-only and honest: there are no dead Save, Connect or Test
buttons.

## Demonstration dataset (demo mode only)

`src/data/demo-tickets.ts` contains ~24 hand-written tickets plus ~56 older
tickets from a seeded generator (fixed PRNG), so trend charts span 30 days
while staying deterministic. `src/data/demo-replies.ts` seeds replies in
pending, approved, changes-requested and sent states so the approval queue is
not empty on first load. `src/data/demo-activity.ts` contains matching audit
events, including reply-linked submitted/approved/changes-requested/sent
records. Timestamps are generated relative to app start so relative dates remain
sensible; nothing refreshes fake-live.

## Tests

- `src/services/__tests__/reply-workflow.test.ts` covers the happy path, every
  invalid transition, approval-gate bypass attempts, revision/version bumps,
  stale-approval invalidation, dashboard counts, subscriber notifications and
  separation of customer replies from internal notes.
- `src/services/__tests__/analytics-activity.test.ts` verifies analytics
  derivations, window semantics, current-state distinction, activity privacy,
  filtering, sorting, pagination and facets.
- `src/services/__tests__/http-service-contract.test.ts` asserts the exact
  backend paths and bodies (status/priority/category/assignment endpoints,
  notes, ticket-scoped activity plus note join, dashboard status counts, reply
  version checks, the draft-upsert fallback and demo-send mapping) using a
  stubbed `fetch`.
- `src/services/__tests__/app-mode.test.ts` proves API mode is the default and
  demo mode requires an explicit setting.
- `src/auth/__tests__/auth-session.test.ts` covers sign-in, refresh restore,
  logout clearing the in-memory token, one-shot refresh-and-retry on `401`, and
  the unauthorized callback when refresh fails.
- `src/lib/__tests__/preferences.test.ts` verifies preference validation and
  safe fallbacks.
- `e2e/app.spec.ts` runs seven demo-mode browser workflows: navigation/active
  state, analytics range/metric links, analytics + activity propagation after
  a triage edit, activity search/filter/privacy, settings persistence and start
  page, the full ticket → reply → approve → demo-send flow (including live
  sidebar counters), and mobile navigation/overflow.
- `e2e-api/workflow.spec.ts` runs the authenticated workflow against a real
  backend and a freshly migrated/seeded disposable database: agent sign-in,
  triage + internal note, reply submission, no self-approval, reviewer
  approval that does not send, explicit demo send, reload persistence, logout
  and `401` on protected endpoints.

```bash
npm test
npm run test:e2e      # demo mode
npm run test:e2e:api  # real backend + isolated e2e database
```

## Demo controls

The flask icon in the ticket toolbar toggles "Simulate request error", which
exercises the exact error/retry UI a failing API call will produce. It is a
demo affordance, clearly labelled as one.

## Honest limitations

- Demo mode is the only in-memory mode and must be enabled explicitly; it shows
  a persistent banner and resets on reload.
- "Mark as Sent (Demo)" records a simulated application action; no customer
  receives a message. No email/SMS/chat provider is integrated.
- Reply approval, revision history and self-approval prevention are enforced by
  the API; client-side hiding is only a usability aid.
- Ticket creation (New Ticket) remains an explicitly labelled preview dialog.
- Analytics and activity figures are composed in the browser from paged API
  data because there is no dedicated analytics/facet endpoint yet.
- Sign-in throttling is server-side but per process; a multi-instance deployment
  needs a shared limiter and TLS in front of the API.
- Verification includes type-check, lint, 61 Vitest tests, a production build,
  7 demo-mode Playwright tests and 1 API-mode Playwright workflow in Google
  Chrome. Visual regression testing is not included.
- The container serves plain HTTP and expects a TLS-terminating proxy in front
  of it; see `../docs/architecture/deployment.md`.

See `../docs/frontend-backend-integration.md` for the service contract, session
flow and the remaining backend gaps.
