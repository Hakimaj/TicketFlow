# TicketFlow frontend (Phase 3)

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
npm test          # Vitest domain tests for the reply approval workflow
npm run build
npm run preview   # serve dist/ at http://localhost:4173
```

## Architecture

```
src/
  app/                  App wiring (router)
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
    placeholders/       Announced future areas (analytics, activity, settings)
  types/                Domain models (Ticket, Agent, TicketActivity,
                        CustomerReply, queries)
  data/                 Demonstration fixtures (separate from UI/services),
                        including demo replies in `demo-replies.ts`
  services/             TicketService interface + DemoTicketService
                        implementation + reserved HTTP client placeholder
  lib/                  cn(), formatting, ticket config maps, reply templates
```

Key rules enforced by this structure:

- Feature code only ever calls the `TicketService` interface
  (`src/services/index.ts` resolves a `DemoTicketService` today; a later phase
  swaps the implementation for HTTP calls behind the same interface).
- Mock data lives exclusively in `src/data/`; no component carries ticket or
  reply fixtures.
- Dashboard numbers, including the pending-approval counter, are derived from
  the dataset inside the service — never hardcoded in UI.
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
dashboard banner and approvals queue refresh without a page reload.

## Demonstration dataset

`src/data/demo-tickets.ts` contains ~24 hand-written tickets plus ~56 older
tickets from a seeded generator (fixed PRNG), so trend charts span 30 days
while staying deterministic. `src/data/demo-replies.ts` seeds replies in
pending, approved, changes-requested and sent states so the approval queue is
not empty on first load. Timestamps are generated relative to app start so
relative dates remain sensible; nothing refreshes fake-live.

## Tests

`src/services/__tests__/reply-workflow.test.ts` exercises the domain service
directly: the happy path, every invalid transition, approval-gate bypass
attempts, revision/version bumps, stale-approval invalidation, dashboard
counts, subscriber notifications and separation of customer replies from
internal notes.

```bash
npm test
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
- Analytics, Activity Logs and Settings pages are placeholders that state
  their delivery phase.
- Verification used type-check, lint, Vitest, a production build and HTTP
  smoke checks of the preview server. Browser-based visual and interaction
  testing was not available in this environment.
