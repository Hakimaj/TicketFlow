# TicketFlow

A support-ticket intake, triage and routing system for a simulated Ethiopian
e-commerce support team. This repository contains the capstone project being
built in phases.

**Status: Phase 3 (Ticket Workspace, Internal Notes & Reply Approval) — implemented.**

## What runs today

- React + TypeScript + Vite application shell (persistent sidebar, top header,
  responsive mobile drawer)
- Overview dashboard: open / unassigned / high-priority / needs-review metric
  cards, a 30-day volume trend, category distribution, recent tickets,
  priority summary and recent activity — all derived from one demonstration
  dataset, plus a pending-approval banner
- All Tickets page with working search, status/category/priority filters,
  column sorting, pagination and clear-filters — plus My Tickets, Unassigned
  and Needs Review queues built on the same pipeline
- Interactive ticket detail: triage (status, priority, category), assignment,
  internal notes, activity timeline and previous/next navigation
- Customer reply workspace: editable templates, save draft, submit for
  approval, supervisor approve/request-changes with mandatory feedback,
  revision/version tracking, stale-approval invalidation, and explicit
  demo-only sending after approval
- Reply Approvals queue at `/approvals` with filters, search, review dialog and
  live pending-count badges in the sidebar and dashboard
- Loading, empty, error and validation states (including a demo control that
  simulates a failed ticket request)
- Explicit placeholder pages for Analytics, Activity Logs and Settings

Everything is backed by a typed, local demonstration dataset. There is **no
backend yet** — no authentication, no persistence, no external services, and
no API keys anywhere. Reply sending is simulated and no real message is
delivered.

## Layout

```
frontend/   React + TypeScript + Vite application
backend/    reserved for a future API phase
docs/       architecture notes (testing, deployment)
scripts/    reserved for automation
```

## Quick start

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173
```

Other commands:

```bash
npm run build     # type-check + production build (dist/)
npm run preview   # serve the production build locally
npm run lint      # eslint
npm run typecheck # tsc -b --noEmit
npm test          # Vitest reply-workflow domain tests
```

No API keys, paid services, accounts or configuration are required. See
`frontend/.env.example` for the one non-secret variable a future backend
integration will use.
