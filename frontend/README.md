# TicketFlow frontend (Phase 1)

Support-ticket workspace built with React 19, TypeScript (strict), Vite 7,
Tailwind CSS 4, shadcn/ui-style components (Radix primitives + CVA),
React Router 7, Lucide icons and Recharts 3.

## Run locally

```bash
npm install
npm run dev       # http://localhost:5173
```

Quality gates (all passing in Phase 1):

```bash
npm run lint
npm run typecheck
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
                        table, filters hook, detail placeholder
    placeholders/       Announced future areas (analytics, activity, settings)
  types/                Domain models (Ticket, Agent, TicketActivity, queries)
  data/                 Demonstration fixtures (separate from UI/services)
  services/             TicketService interface + DemoTicketService
                        implementation + reserved HTTP client placeholder
  lib/                  cn(), formatting, ticket config maps
```

Key rules enforced by this structure:

- Feature code only ever calls the `TicketService` interface
  (`src/services/index.ts` resolves a `DemoTicketService` today; Phase 2
  swaps the implementation for HTTP calls behind the same interface).
- Mock data lives exclusively in `src/data/`; no component carries ticket
  fixtures or aggregation logic.
- "Open", "unassigned", "high/urgent" and "needs review" dashboard numbers
  are derived from the dataset inside the service — never hardcoded in UI.
- Status and priority are separate typed unions; badges always pair an icon
  with text so color is never the only signal.
- The demo user (`Abebe Kebede`) is labelled as a demo user in the UI. No
  authentication or role-in-localStorage exists in this phase.

## Demonstration dataset

`src/data/demo-tickets.ts` contains ~24 hand-written tickets plus ~56 older
tickets from a seeded generator (fixed PRNG), so trend charts span 30 days
while staying deterministic. Timestamps are generated relative to app start
so relative dates remain sensible; nothing refreshes fake-live.

## Demo controls

The flask icon in the ticket toolbar toggles "Simulate request error", which
exercises the exact error/retry UI that a failing API call will produce in
Phase 2. It is a demo affordance, clearly labelled as one.

## Honest limitations (Phase 1)

- No backend: data resets on reload; ticket creation (New Ticket) is an
  explicitly labelled Phase 2 preview dialog.
- Ticket detail is a read-only summary; conversation/reply/approval flows
  arrive in Phase 2.
- Analytics, Activity Logs and Settings pages are placeholders that state
  their delivery phase.
- Browser-based visual testing was not run in this phase; verification used
  type-check, lint, production build and HTTP checks of the dev and preview
  servers.
