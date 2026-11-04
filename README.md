# TicketFlow

A support-ticket intake, triage and routing system for a simulated Ethiopian
e-commerce support team. This repository contains the capstone project being
built in phases.

**Status: Phase 10 (core product completeness & workflow hardening) — verified locally.**

The React workspace talks to the FastAPI backend by default: accounts sign in
against the API, every operational request carries a short-lived access token,
and tickets, replies, internal notes, approvals and audit events persist in
PostgreSQL. The in-memory demonstration dataset remains available only with an
explicit `VITE_DATA_MODE=demo` and is visibly labelled.

Phase 9 added the continuous-integration workflow, production-shaped containers,
fail-fast configuration guards and the release checklist. Phase 10 closes the
remaining product gaps: **staff ticket intake** (`POST /api/v1/tickets` plus a
New Ticket page), **administrator account management** (provision, re-role,
link/unlink an agent, activate/deactivate, forced password change) and
**optimistic concurrency on ticket triage** (`version` + `expected_version`,
`409` instead of a silent overwrite). Customer-message delivery remains
simulated.

## What runs today

### Frontend

- React + TypeScript + Vite application shell (persistent sidebar, top header,
  responsive mobile drawer)
- Overview dashboard: open / unassigned / high-priority / needs-review metric
  cards, a 30-day volume trend, category distribution, recent tickets,
  priority summary and recent activity — all derived from the API (or the
  explicit demo dataset), plus a pending-approval banner
- All Tickets page with working search, status/category/priority filters,
  column sorting, pagination and clear-filters — plus My Tickets, Unassigned
  and Needs Review queues built on the same pipeline
- New Ticket intake at `/tickets/new`: validated form (customer, subject,
  description, category, priority, channel), duplicate-submit guard, API errors
  surfaced verbatim, then navigation to the persisted ticket
- Interactive ticket detail: triage (status, priority, category), assignment,
  internal notes, activity timeline and previous/next navigation; a stale
  version shows the conflict message and reloads the latest state instead of
  overwriting another operator's change
- Accounts administration at `/accounts` (admin only): account list with
  activation state and pending password changes, provisioning dialog, role and
  agent-link controls, activate/deactivate with confirmation
- Forced password change at `/change-password` for accounts provisioned with an
  initial password; the workspace stays locked until it is replaced
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
- Sign-in at `/login` with protected routes, session restore via the rotating
  HttpOnly refresh cookie, sign-out, and role-gated navigation/actions
- Settings at `/settings`: signed-in account and role, honest integration
  status, workflow reference, and genuinely working local-only table-density
  and start-page preferences
- Loading, empty, error and validation states (including a demo control that
  simulates a failed ticket request)
- Responsive layout, accessible navigation and mobile drawer; no placeholder
  routes remain

Reply approval and sending are enforced server-side; approval never sends, and
sending is an explicit simulated demo action — no real message is delivered.

### Backend (Phase 10)

- FastAPI service under `/api/v1` with explicit Pydantic schemas
- PostgreSQL 16 persistence via SQLAlchemy 2.x and five additive Alembic
  migrations (`0001_initial`, `0002_ticket_operations`,
  `0003_reply_workflow`, `0004_auth`, `0005_intake_accounts`)
- Normalized models for agents, requesters, tickets, customer replies (with
  approval/send metadata), internal notes and structured activity events
- Idempotent demo seeding that mirrors the frontend fixtures
- Liveness and database-readiness probes with sanitized failure responses
- `GET /api/v1/tickets` with server-side search, status/priority/category/
  agent/unassigned filters, allow-listed sorting and pagination
- `GET /api/v1/tickets/{ticket_id}` with requester summary and triage data
- `POST /api/v1/tickets` staff intake: validated payload, creator from the
  access token, category-derived team, SLA target and initial `created` audit
  event in one transaction; sequential `TF-####` numbers under an advisory lock
- Persistent `PATCH` mutations for status, priority, category and assignment;
  each requires `expected_version`, takes a row lock and commits with its
  required audit event or rolls both back; a stale version returns `409` with
  the current version and timestamp
- `POST/GET` internal notes backed by a dedicated notes table; note bodies never
  enter general activity summaries
- Ticket-specific and global activity queries with action/actor/date filters,
  deterministic ordering and pagination
- Persistent, versioned reply workflow: drafts, immutable revisions, submit,
  approve / request changes, searchable approval queue and a transactional
  demo-send gate
- Accounts with Argon2id password hashes, short-lived JWT access tokens,
  rotating HttpOnly refresh sessions and logout revocation
- Server-side role/permission matrix (`agent`, `reviewer`, `admin`) with trusted
  actor/reviewer attribution and self-approval prevention (including admins)
- Administrator-only account API (`GET/POST /accounts`, `PATCH
  /accounts/{id}`) with Argon2id provisioning, unique email and agent links,
  self-privilege-change prevention and immediate session revocation on
  deactivation; plus `POST /auth/password` for the forced change
- Every operational endpoint requires authentication; only health and auth are
  public. No dedicated analytics or activity-facet endpoints yet

## Layout

```
frontend/           React + TypeScript + Vite application
backend/            FastAPI + SQLAlchemy + Alembic service and tests
docker-compose.yml  full-stack stack (PostgreSQL + API + nginx-served web)
docs/               architecture, deployment, release checklist and API contract
.github/workflows/  CI: backend tests, frontend checks, API-backed browser run
scripts/            reserved for automation
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
# Provide JWT_SECRET (>= 32 chars) in .env, then create accounts explicitly:
python -m scripts.bootstrap   # BOOTSTRAP_ADMIN_* or DEMO_ACCOUNTS_ENABLED=true
python -m uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
```

Windows PowerShell equivalents (no activation required):

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m pip install -e ".[dev]"
docker compose up -d db
.\\.venv\\Scripts\\python.exe -m alembic upgrade head
.\\.venv\\Scripts\\python.exe -m scripts.seed
.\\.venv\\Scripts\\python.exe -m scripts.bootstrap
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --reload --port 8000
.\\.venv\\Scripts\\python.exe -m pytest -q
```

If port 4173/4174 is refused on Windows (Hyper-V/WSL can reserve a dynamic port
range), run the browser suites with `E2E_WEB_PORT=5178` / `E2E_WEB_PORT=5179`.

The frontend then runs in API mode by default and shows `/login`. For the
in-memory walkthrough use `VITE_DATA_MODE=demo npm run dev`.

See `backend/README.md` for environment variables, migration/seed commands,
backend tests and limitations, and `docs/backend-api-contract.md` for the
endpoint contract and frontend mapping.

Full stack with Docker (PostgreSQL + API + web on one origin):

```bash
cp .env.example .env             # set JWT_SECRET and POSTGRES_PASSWORD
docker compose up -d --build     # http://localhost:8080
```

Step-by-step instructions for both paths, the configuration reference, the
production checklist and the operational limitations are in
`docs/architecture/deployment.md`. Release status, verification commands and
remaining risks are in `docs/release-checklist.md`.

Other commands:

```bash
npm run build     # type-check + production build (dist/)
npm run preview   # serve the production build locally
npm run lint      # eslint
npm run typecheck # tsc -b --noEmit
npm test              # Vitest domain/contract/session tests
npm run test:e2e      # Playwright demo-mode browser tests (installed Chrome)
npm run test:e2e:api  # Playwright workflow against a real backend + e2e DB
```

Backend verification:

```bash
cd backend
python -m pytest -q              # requires the Docker database to be running
```

CI runs the same commands on every push and pull request, plus a PostgreSQL
service, a downgrade/upgrade round-trip and the API-backed browser workflow.

Real browser verification uses the locally installed Chrome channel via
Playwright; no paid service or browser binary download is required in this
environment. See `docs/frontend-backend-integration.md` for the frontend contract, adapter
behavior and session flow, and `docs/backend-api-contract.md` for the
implemented API.

No API keys, paid services or external accounts are required. `backend/.env`
holds local database and JWT settings and is git-ignored; no bootstrap password
is committed. `frontend/.env.example` documents API mode (default) and the
explicit `VITE_DATA_MODE=demo` switch.
