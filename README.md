# TicketFlow

A support-ticket intake, triage and routing system for a simulated Ethiopian
e-commerce support team. This repository contains the capstone project being
built in phases.

**Status: Phase 1 (Frontend Foundation & Core Workspace) — implemented.**

## What runs today (Phase 1)

- React + TypeScript + Vite application shell (persistent sidebar, top header)
- Overview dashboard: open / unassigned / high-priority / needs-review metric
  cards, a 30-day volume trend, category distribution, recent tickets,
  priority summary and recent activity — all derived from one demonstration
  dataset
- All Tickets page with working search, status/category/priority filters,
  column sorting, pagination and clear-filters — plus My Tickets, Unassigned
  and Needs Review queues built on the same pipeline
- Loading, empty and error states (including a demo control that simulates a
  failed request)
- Explicit placeholder pages for Analytics, Activity Logs, Settings and full
  ticket details

Everything is backed by a typed, local demonstration dataset. There is **no
backend yet** — no authentication, no persistence, no external services, and
no API keys anywhere.

## Layout

```
frontend/   React + TypeScript + Vite application (Phase 1 deliverable)
backend/    reserved for a future Phase 2+ API
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
```

No API keys, paid services, accounts or configuration are required. See
`frontend/.env.example` for the one non-secret variable a future backend
integration will use.
