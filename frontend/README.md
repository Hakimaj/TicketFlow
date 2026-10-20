# TicketFlow frontend (Phase 4)

Support-ticket workspace built with React 19, TypeScript (strict), Vite 7,
Tailwind CSS 4, shadcn/ui-style components (Radix primitives + CVA),
React Router 7, Lucide icons and Recharts 3.

## Run locally

```bash
npm install
npm run dev       # http://localhost:5173
```

Quality gates (all passing):

```bash
npm run lint
npm run typecheck
npm test          # Vitest domain tests (workflow, analytics, activity, preferences)
npm run build
npm run test:e2e  # Playwright browser tests (uses locally installed Google Chrome)
npm run preview   # serve dist/ at http://localhost:4173
```

The Playwright config starts Vite on port `4173` and uses the installed Chrome
channel, so no browser binary download is required. Set
`PLAYWRIGHT_BROWSERS_PATH` or adjust `playwright.config.ts` if Chrome is not
installed locally.

## Architecture

```
src/
  app/                  App wiring, router, preferences provider, start page
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
    settings/           Demo profile, local preferences, workflow reference
  types/                Domain models (Ticket, Agent, TicketActivity,
                        CustomerReply, queries, analytics, activity log)
  data/                 Demonstration fixtures (separate from UI/services),
                        including demo replies in `demo-replies.ts`
  services/             TicketService interface + DemoTicketService
                        implementation + reserved HTTP client placeholder
  lib/                  cn(), formatting, ticket/activity config maps, shared
                        chart colors, reply templates, preference validation
e2e/                    Playwright browser workflows
```

Key rules enforced by this structure:

- Feature code only ever calls the `TicketService` interface
  (`src/services/index.ts` resolves a `DemoTicketService` today; a later phase
  swaps the implementation for HTTP calls behind the same interface).
- Mock data lives exclusively in `src/data/`; no component carries ticket or
  reply fixtures. Assignee names come from `listAgents()`.
- Dashboard numbers, analytics, activity facets and the pending-approval
  counters are derived inside the service — never hardcoded in UI and never
  read from fixture arrays in components.
- Status and priority are separate typed unions; badges always pair an icon
  with text so color is never the only signal.
- The demo user (`Abebe Kebede`) is labelled as a demo user in the UI. No
  authentication or role-in-localStorage exists in this phase.
- The reply approval gate is enforced in `DemoTicketService`, not just by
  hiding buttons. `markReplySent` rejects any reply that is not currently
  approved.

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

`/settings` shows the demo profile and explicitly states that it is not an
authenticated account. Two preferences are genuinely applied and stored only in
this browser under `ticketflow.preferences.v1`:

- table density (`comfortable` / `compact`) via `data-density` on `<html>`;
- default landing page, applied when the app starts at `/` in a new tab/reload.

Values are validated on read; unknown values fall back to defaults, and **Reset
preferences** restores them. The workflow reference is derived from the domain
maps in `src/lib/ticket-config.ts` and `src/types/reply.ts`. The integration
status section is read-only and honest: there are no dead Save, Connect or Test
buttons.

## Demonstration dataset

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
- `src/lib/__tests__/preferences.test.ts` verifies preference validation and
  safe fallbacks.
- `e2e/app.spec.ts` runs seven real browser workflows: navigation/active
  state, analytics range/metric links, analytics + activity propagation after
  a triage edit, activity search/filter/privacy, settings persistence and start
  page, the full ticket → reply → approve → demo-send flow (including live
  sidebar counters), and mobile navigation/overflow.

```bash
npm test
npm run test:e2e
```

## Demo controls

The flask icon in the ticket toolbar toggles "Simulate request error", which
exercises the exact error/retry UI a failing API call will produce. It is a
demo affordance, clearly labelled as one.

## Honest limitations

- No backend: data lives in memory and resets on reload. There is no
  persistence, authentication, email delivery or external messaging.
- "Mark as Sent (Demo)" only records local state; no customer receives a
  message. Client-side restrictions are workflow guards, not production
  security.
- Approval actions use the single demo supervisor identity. Distinct reviewer
  accounts and role-based permissions arrive with a real backend.
- Ticket creation (New Ticket) remains an explicitly labelled preview dialog.
- Analytics and activity calculations run in the browser against demo records;
  there are no stored historical snapshots.
- Verification includes type-check, lint, 39 Vitest tests, a production build
  and 7 Playwright tests in Google Chrome. Visual regression testing is not
  included.

See `../docs/frontend-backend-integration.md` for the existing service contract,
state rules and clearly labelled proposals for future backend work.
