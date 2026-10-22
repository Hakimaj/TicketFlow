# TicketFlow

A support-ticket intake, triage and routing system for a simulated Ethiopian
e-commerce support team. This repository contains the capstone project being
built in phases.

**Status: Phase 6 (persistent ticket operations, notes & activity APIs) — implemented.**

The frontend is complete through Phase 4 and still runs on its in-memory demo
service. The FastAPI backend is not wired into the UI yet; it persists tickets,
replies, internal notes and audit events in PostgreSQL and exposes ticket
operations, activity history, agent lookup and dashboard metrics.

## What runs today

### Frontend

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
- Analytics at `/analytics`: service-derived 7/30/all metrics, ticket volume,
  status/priority/category mix, reply-workflow states and agent workload —
  clearly separated into windowed and current-state figures
- Activity Logs at `/activity`: sanitized audit records with search, action /
  actor / date filters, sorting, pagination, clear-filters and ticket links;
  internal note bodies, drafts and reviewer feedback are never exposed
- Settings at `/settings`: demo profile, honest integration status, workflow
  reference, and genuinely working local-only table-density and start-page
  preferences
- Loading, empty, error and validation states (including a demo control that
  simulates a failed ticket request)
- Responsive layout, accessible navigation and mobile drawer; no placeholder
  routes remain

The UI is still backed by a typed, local demonstration dataset. Reply sending
is simulated and no real message is delivered.

### Backend (Phase 6)

- FastAPI service under `/api/v1` with explicit Pydantic schemas
- PostgreSQL 16 persistence via SQLAlchemy 2.x and two additive Alembic
  migrations (`0001_initial`, `0002_ticket_operations`)
- Normalized models for agents, requesters, tickets, customer replies (with
  approval/send metadata), internal notes and structured activity events
- Idempotent demo seeding that mirrors the frontend fixtures
- Liveness and database-readiness probes with sanitized failure responses
- `GET /api/v1/tickets` with server-side search, status/priority/category/
  agent/unassigned filters, allow-listed sorting and pagination
- `GET /api/v1/tickets/{ticket_id}` with requester summary and triage data
- Persistent `PATCH` mutations for status, priority, category and assignment;
  each commits with its required audit event or rolls both back
- `POST/GET` internal notes backed by a dedicated notes table; note bodies never
  enter general activity summaries
- Ticket-specific and global activity queries with action/actor/date filters,
  deterministic ordering and pagination
- Agent roster and SQL-derived ticket dashboard summary
- No reply-workflow API, analytics API or authentication yet — those are later
  phases; write endpoints are local-development only

## Layout

```
frontend/   React + TypeScript + Vite application
backend/    FastAPI + SQLAlchemy + Alembic service and tests
docs/       architecture, API contract and frontend→backend integration notes
scripts/    reserved for automation
```

## Quick start

Frontend:

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173
```

Backend (requires Python 3.11+ and Docker):

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate     # macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
docker compose up -d db
docker compose ps                 # wait for "healthy"
python -m alembic upgrade head
python -m scripts.seed
python -m uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
```

See `backend/README.md` for environment variables, migration/seed commands,
backend tests and limitations, and `docs/backend-api-contract.md` for the
endpoint contract and frontend mapping.

Other commands:

```bash
npm run build     # type-check + production build (dist/)
npm run preview   # serve the production build locally
npm run lint      # eslint
npm run typecheck # tsc -b --noEmit
npm test          # Vitest domain tests (workflow, analytics, activity, preferences)
npm run test:e2e  # Playwright browser tests (installed Google Chrome)
```

Backend verification:

```bash
cd backend
python -m pytest -q              # requires the Docker database to be running
```

Real browser verification uses the locally installed Chrome channel via
Playwright; no paid service or browser binary download is required in this
environment. See `docs/frontend-backend-integration.md` for the frontend's typed
service contract and state rules, and `docs/backend-api-contract.md` for the
implemented API.

No API keys, paid services or external accounts are required. `backend/.env`
holds local database placeholders and is git-ignored; `frontend/.env.example`
reserves the API base URL for the later integration.
