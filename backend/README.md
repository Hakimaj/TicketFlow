# TicketFlow backend (Phase 10: intake, accounts, concurrency)

Runnable FastAPI service backed by PostgreSQL. Phase 8 added persistent user
accounts, Argon2id password hashing, short-lived JWT access tokens, rotating
HttpOnly refresh sessions, server-side role/permission enforcement and
trusted actor attribution on top of the Phase 5/6 ticket, note, activity,
agent and dashboard APIs and the Phase 7 reply workflow. Phase 9 added fail-fast
production configuration guards, a non-root container image and a documented
deployment path (`../docs/architecture/deployment.md`). Phase 10 adds staff
ticket intake (`POST /api/v1/tickets`), administrator account management
(`/api/v1/accounts`, forced password change), and optimistic concurrency on
ticket triage (`version` / `expected_version` → `409`), migration
`0005_intake_accounts`.

> The frontend talks to this API by default (`VITE_DATA_MODE=api`). Demo mode
> (`VITE_DATA_MODE=demo`) is an explicit, visibly labelled in-memory mode.
> Every operational endpoint requires a Bearer access token; only the health
> probes and `/api/v1/auth/*` are public. Sign-in throttling is in-process, so
> a multi-instance deployment still needs an edge/shared limiter and TLS.

## Stack

| Concern | Choice |
| --- | --- |
| Language | Python 3.11+ (developed and tested on 3.13.7) |
| HTTP | FastAPI 0.157 + Uvicorn |
| ORM | SQLAlchemy 2.0 (synchronous) |
| Database | PostgreSQL 16 |
| Migrations | Alembic 1.20 |
| Validation / settings | Pydantic 2.14 + pydantic-settings |
| Driver | psycopg 3 (`psycopg[binary]`) |
| Tests | pytest 8 + FastAPI TestClient (httpx) |

Versions are compatible ranges in `pyproject.toml`.

## Layout

```
backend/
  app/
    main.py            # app factory, lifespan, CORS, router wiring
    core/
      config.py        # typed settings, startup validation
      errors.py        # ApiError primitives
      labels.py        # domain labels + category→team mapping
    db/                # declarative base, engine/session factory
    models/            # agents, requesters, tickets, replies, notes, activity, accounts
    schemas/           # Pydantic API contracts (never ORM objects)
    repositories/      # SQL queries, filters, allow-listed sorting, aggregates
    services/          # orchestration, transactions, ORM → API mapping
    authorization.py   # single role → permission matrix used by routes
    core/security.py   # Argon2id, JWT access tokens, refresh-token hashing
    api/
      deps.py          # request-scoped DB session + Bearer authentication
      errors.py        # one JSON error envelope for every failure
      params.py        # shared validated ticket path parameter
      routes/          # health, auth, accounts, tickets, notes, replies,
                       # activities, agents, dashboard
    seed.py            # idempotent demo fixtures mirrored from the frontend
  alembic/versions/
    20261021_0001_initial_schema.py
    20261021_0002_ticket_operations.py
    20261022_0003_reply_workflow.py
    20261023_0004_auth.py
    20261025_0005_intake_accounts.py
  scripts/seed.py      # CLI: python -m scripts.seed
  scripts/bootstrap.py # CLI: create the first admin / development accounts
  scripts/e2e_prepare.py # isolated `*_e2e` database for Playwright
  tests/               # pytest suite against a real PostgreSQL test DB
  alembic.ini
  docker-compose.yml   # local PostgreSQL only
  .env.example
  pyproject.toml
```

Routing, business logic, transactions, data access, ORM models and API schemas
are separate modules. `main.py` only wires them together.

## Local setup

Requirements: Python 3.11+, Docker with Compose.

```bash
cd backend
python -m venv .venv

# Windows (Git Bash)
source .venv/Scripts/activate
# macOS / Linux
# source .venv/bin/activate

python -m pip install -e ".[dev]"

cp .env.example .env          # local-only placeholder values
docker compose up -d db
docker compose ps             # wait for "healthy"
```

`docker compose up` reads `backend/.env`. `.env` is git-ignored — only
`.env.example` is committed.

### Environment variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | API, Alembic, tests | Full PostgreSQL URL (`postgresql+psycopg://user:password@host:port/dbname`) |
| `POSTGRES_DB` | Docker Compose | Container database name |
| `POSTGRES_USER` | Docker Compose | Container role |
| `POSTGRES_PASSWORD` | Docker Compose | Container password (local placeholder only) |
| `POSTGRES_PORT` | Docker Compose | Host port mapped to 5432 (default `5432`) |
| `APP_ENV` | API | `development` / `test` / `production`; production blocks the seeder |
| `CORS_ORIGINS` | API | Comma-separated explicit browser origins; `*` is rejected |
| `DATABASE_ECHO` | API | `true` echoes SQL (development only) |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | API | Connection timeout for probes (default `5`) |
| `JWT_SECRET` | API | **Required** signing secret, at least 32 characters; tests use a fixed test-only value |
| `ACCESS_TOKEN_TTL_MINUTES` | API | Access-token lifetime (default `15`, max `120`) |
| `REFRESH_TOKEN_TTL_DAYS` | API | Refresh-session lifetime (default `14`) |
| `COOKIE_SECURE` / `COOKIE_SAMESITE` | API | Refresh-cookie flags. `COOKIE_SAMESITE=none` requires `COOKIE_SECURE=true` |
| `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` | bootstrap CLI | First administrator; password ≥ 12 characters, never committed |
| `DEMO_ACCOUNTS_ENABLED` / `DEMO_ACCOUNT_PASSWORD` | bootstrap CLI | Development-only role accounts linked to seeded agents |

Host, port, database name, role and password are configurable through
`DATABASE_URL` or the individual `POSTGRES_*` values used by Compose. Settings
are validated at startup.

### Stop / remove the database

```bash
docker compose stop db        # keep data
docker compose down           # keep the named volume
docker compose down -v        # delete data (explicit reset only)
```

## Migrations

```bash
python -m alembic upgrade head      # apply all migrations
python -m alembic current           # show applied revision
python -m alembic check             # fail if models drift from migrations
python -m alembic downgrade base    # destructive: drop schema objects
python -m alembic history           # show revision chain
```

- `0001_initial` (Phase 5) creates the enum types and five core tables.
- `0002_ticket_operations` is additive: it adds `ticket_notes` and the
  `ticket_activities.note_id` link. Neither earlier migration is edited.
- `0003_reply_workflow` is additive: it creates `reply_revisions` and
  `reply_reviews`, adds `submitted_version`/`approved_version` to
  `customer_replies`, adds `ticket_activities.reply_version`, backfills one
  revision per existing reply, and adds the approval-gate CHECK constraints.
  It is superseded by `0004_auth`.
- `0004_auth` is additive: it creates `user_accounts` and
  `refresh_sessions` and adds nullable `*_account_id` attribution columns to
  activities, notes, replies, revisions and reviews. Historical rows keep their
  agent attribution with a NULL account reference. It is the current head.
- No table is created at API startup; `create_all()` is never used.

## Demo data

```bash
python -m scripts.seed
```

- Inserts 8 agents, 24 requesters, 24 tickets, 5 historical replies with their
  revision snapshots, 3 historical review decisions and 19 historical activity
  records — the same IDs, categories, priorities, statuses, assignments and
  reply↔ticket pairings as the frontend fixtures.
- Idempotent: rows are matched by stable ID/email/reply version and existing
  rows are never updated or deleted, so reruns report `0 created` and preserve
  local edits. Reply revisions and review decisions are backfilled by the
  migration for pre-existing replies.
- No notes are seeded; note records are created only through the API.
- Never runs automatically when the API starts.
- Refuses to run with `APP_ENV=production` unless `ALLOW_DEMO_SEED=true`.
- The frontend's 56 randomly generated filler tickets are not ported.

## Run the API

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --reload --port 8000
```

- Swagger UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/api/v1/openapi.json>

Health checks:

```bash
curl -s http://localhost:8000/api/v1/health/live
curl -s -w '\n%{http_code}\n' http://localhost:8000/api/v1/health/ready
```

With PostgreSQL stopped, `/health/live` still returns `200`, while
`/health/ready` and data endpoints return `503` with a generic message — no
driver text, host, SQL or credentials are exposed.

## Implemented endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health/live` | Liveness |
| GET | `/api/v1/health/ready` | Database readiness |
| GET | `/api/v1/tickets` | Filtered/sorted/paginated queue |
| GET | `/api/v1/tickets/{ticket_id}` | Ticket detail + requester |
| PATCH | `/api/v1/tickets/{ticket_id}/status` | Change status |
| PATCH | `/api/v1/tickets/{ticket_id}/priority` | Change priority |
| PATCH | `/api/v1/tickets/{ticket_id}/category` | Change category + re-route team |
| PATCH | `/api/v1/tickets/{ticket_id}/assignment` | Assign / reassign / unassign |
| POST | `/api/v1/tickets/{ticket_id}/notes` | Add an internal note |
| GET | `/api/v1/tickets/{ticket_id}/notes` | List notes (paginated) |
| GET | `/api/v1/tickets/{ticket_id}/activities` | Ticket audit timeline |
| GET | `/api/v1/activities` | Global filtered/sorted/paginated audit log |
| GET | `/api/v1/agents` | Agent roster for assignment controls |
| POST | `/api/v1/tickets/{ticket_id}/replies` | Create the ticket's reply draft |
| GET | `/api/v1/tickets/{ticket_id}/replies` | List the ticket's replies |
| GET | `/api/v1/replies/approvals` | Pending-approval queue (search/filter/paginate) |
| GET | `/api/v1/replies/{reply_id}` | Reply detail + revision/review history |
| PATCH | `/api/v1/replies/{reply_id}` | Edit draft / create a revision |
| POST | `/api/v1/replies/{reply_id}/submit` | Submit current revision for approval |
| POST | `/api/v1/replies/{reply_id}/approve` | Approve the exact submitted version |
| POST | `/api/v1/replies/{reply_id}/request-changes` | Request changes with internal feedback |
| POST | `/api/v1/replies/{reply_id}/send-demo` | Mark approved reply sent (demo only) |
| GET | `/api/v1/dashboard/summary` | SQL-derived ticket + reply metrics |

Full request/response examples and filters are in
[`../docs/backend-api-contract.md`](../docs/backend-api-contract.md).

### Mutation rules

| Mutation | Behaviour |
| --- | --- |
| Status | Persists status, touches `updated_at`; `resolved`/`closed` clear `due_at`; event action is `resolved`, `review_flagged` (needs review) or `status_changed` |
| Priority | Persists priority; active `urgent`/`high` gets an 8-hour target from now, other priorities clear it; terminal tickets keep their existing `due_at` |
| Category | Sets `category` and re-routes `assigned_team` from the authoritative mapping; **preserves** any assigned agent |
| Assignment | Assigns any existing agent, reassigns, or unassigns with explicit `"agent_id": null`; does **not** rewrite the category-derived team |
| No-ops | Repeating the current value returns the ticket with no audit event and no `updated_at` change |
| Transaction | Ticket change + audit event commit together; any failure rolls both back |

Category → team mapping:

| Category | Team |
| --- | --- |
| billing | billing_team |
| delivery | logistics_team |
| technical | technical_support |
| returns | returns_team |
| general | customer_support |

Notes are stored in `ticket_notes`. The corresponding `note_added` activity
stores the fixed summary “Internal note added.” plus `note_id`, never the note
body. Notes are staff-only and are not customer replies.

Dashboard definitions:

- `total_tickets`: all tickets.
- `active_tickets`: status `new`, `open` or `pending`.
- `unassigned_tickets`: active tickets with no assigned agent.
- `urgent_high_tickets`: active tickets with priority `urgent` or `high`.
- `needs_review_tickets`: all tickets whose ticket-level status is
  `needs_review` (not reply approvals).
- `pending_reply_approvals` / `draft_replies` /
  `approved_replies_awaiting_send` / `sent_replies_demo`: logical replies per
  workflow state (never per revision). `sent_replies_demo` counts simulated
  demo sends, not customer deliveries.
- `status_counts` / `category_counts` / `priority_counts`: all tickets, in
  domain order, with zero-count values included.

No SLA, CSAT, revenue or real delivery metrics are claimed.

## Reply workflow

- Logical reply (`customer_replies`) + immutable `reply_revisions` (unique
  `reply_id`+`version`) + append-only `reply_reviews` (decision tied to an exact
  revision, with internal comment).
- Transitions: save → submit → approve **or** request changes → revise/
  resubmit → explicit demo send. Saving, submitting, approving and sending are
  distinct operations; none of the first three sends anything.
- Every reply mutation locks the reply row (`SELECT … FOR UPDATE`), commits the
  state change and its audit event in one transaction, and reloads the committed
  state for the response.
- The demo-send gate requires state `approved`, `approved_version == version`,
  matching `submitted_version`, reviewer metadata, a stored approval decision for
  that exact revision and matching revision text. Database CHECK constraints
  mirror the approval invariants, so even a bypassed service call cannot persist
  a `sent` reply without a current approval.
- Sending moves `new`/`open` tickets to `pending` and never sends email, SMS or
  any other message. Sent replies are immutable; a follow-up starts a new reply.
- Reviewer comments are staff-only and are excluded from reply bodies and
  general activity summaries. Activity rows link `reply_id` + `reply_version`.
- Actor and reviewer attribution come from the authenticated account; request
  bodies cannot name an actor. Authors can never approve their own reply,
  including administrators.

## Accounts and bootstrap

Accounts are never seeded with the demo data and no default credential is
committed. Create them explicitly after seeding:

```bash
# First administrator (or one role account) via environment variables
export BOOTSTRAP_ADMIN_EMAIL="ops@example.com"
export BOOTSTRAP_ADMIN_PASSWORD="<at least 12 characters>"
python -m scripts.bootstrap

# Development-only account per role, linked to seeded agents AG-03 / AG-01 / AG-08
export DEMO_ACCOUNTS_ENABLED=true
export DEMO_ACCOUNT_PASSWORD="<at least 12 characters>"
python -m scripts.bootstrap
```

- The command is idempotent: an existing email is skipped and its password is
  never overwritten.
- Demo accounts are refused outside `APP_ENV=development`; production
  administrator creation also requires `ALLOW_BOOTSTRAP_ADMIN=true`.
- Create additional accounts with `app.services.auth.create_account` (Argon2id
  hashing) rather than inserting password hashes by hand.

## Authentication and authorization

- **Accounts:** `user_accounts` stores email, Argon2id hash, display name, role
  (`agent` / `reviewer` / `admin`), active flag and an optional unique link to a
  seeded support agent. Role is always read from PostgreSQL, never from a token
  claim or request body.
- **Sign-in:** `POST /api/v1/auth/login` verifies the password (unknown emails
  still perform a dummy hash check), rate-limits failures in process memory and
  returns a short-lived HS256 access token plus an HttpOnly, SameSite refresh
  cookie scoped to `/api/v1/auth`.
- **Refresh:** `POST /api/v1/auth/refresh` rotates the opaque refresh token on
  every use (only its SHA-256 hash is stored); a previously used token is
  rejected and revokes every session for the account. A rejected, expired or
  replayed cookie is cleared in the browser, and the response is `no-store`.
  `POST /api/v1/auth/logout` revokes the presented session and, when the access
  token is still valid, every session for the account.
- **Access tokens:** 15 minutes by default, held in frontend memory only. Each
  token carries its refresh-session id, so logout and replay-triggered family
  revocation reject it immediately. The server also re-loads the account on
  every request, so deactivating an account or changing its role takes effect
  immediately.
- **Roles:** the matrix lives in `app/authorization.py`. Agents can triage,
  note and draft/submit replies; reviewers can additionally approve or request
  changes; admins can additionally manage accounts. Permission dependencies are
  applied per route, and all operational routers also require authentication.
- **Attribution:** `actor_id` / `reviewer_id` are never accepted from request
  bodies. Notes, ticket changes, reply revisions, reviews and demo sends record
  the authenticated account and its linked agent.
- **Self-approval:** a reply author can never approve or request changes on
  their own reply (`403 self_approval_forbidden`), including administrators.
- **Errors:** `401 not_authenticated` / `invalid_token` / `refresh_invalid` and
  `403 forbidden` / `self_approval_forbidden` use the shared error envelope.

## Tests

```bash
python -m pytest -q
python -m pytest tests/test_ticket_mutations.py -q   # one module
```

Tests require the Docker database. The session fixture creates a separate
`ticketflow_test` database, runs `alembic upgrade head`, and truncates all
tables before every test. The development database is never read or modified,
and the fixture refuses any database name that is not `<name>_test`.

`tests/test_config.py` pins the production fail-fast rules (weak or placeholder
secrets, insecure cookies, the local development database URL, non-HTTPS
origins, demo accounts, wildcard CORS) so a misconfigured deployment cannot
start silently.

Coverage includes Phase 5/6 behaviour, the reply workflow and Phase 8
authentication/authorization: login success and generic failures, CSRF marker,
inactive accounts, expired/garbage access tokens, refresh rotation and reuse
rejection, logout revocation, database-derived roles, per-process sign-in
throttling, every operational route rejecting unauthenticated calls, agent /
reviewer / admin role boundaries, administrator and reviewer self-approval
prevention, and spoofed `actor_id` / `reviewer_id` / `author_id` body fields
being ignored. Workflow detail: draft creation
and scoping, empty/oversized rejection, immutable revisions and true no-op
saves, pending/approved/changes-requested edit invalidation, sent immutability,
submit/approve/request-changes rules, stale-version conflicts, approval queue
search/filter/sort/pagination, reviewer identity and internal feedback
separation, every demo-send gate rejection, ticket-status transition, audit
linking (`reply_id`/`reply_version`), transactional rollback when an audit write
fails, dashboard reply counts (per logical reply), database-level approval
constraints, and a real two-thread PostgreSQL concurrency test proving two
simultaneous sends cannot both succeed. Migration drift, downgrade/upgrade,
enum/timezone/FK integrity and seed idempotency are also covered.

The current suite is **216 passing tests** against PostgreSQL.

## Container image and deployment

`Dockerfile` builds a dependency-complete, non-root image with no configuration
baked in; every value is read from the environment at run time:

```bash
docker build -t ticketflow-api ./backend
docker run --rm -p 8000:8000 --env-file .env ticketflow-api
```

Migrations are deliberately not run at import time. The repository-root
`docker-compose.yml` applies `python -m alembic upgrade head` before starting
uvicorn, so a restart never leaves the schema behind the code. Step-by-step
instructions for both the local and the containerised path, the full
configuration reference and the production checklist are in
[`../docs/architecture/deployment.md`](../docs/architecture/deployment.md).

## Limitations

- Sign-in throttling is per process; a multi-instance deployment needs a
  shared limiter (or an edge rate limit).
- No analytics endpoint; windowed trends, CSAT/SLA and delivery metrics do not
  exist.
- No note editing/deletion; notes are append-only.
- Ticket triage has no optimistic concurrency control (`If-Match`). Reply
  transitions instead use exact-version checks plus row-level locks.
- Demo sending is simulated only. No email, SMS, Telegram or other provider is
  integrated, and no customer message is delivered.
- Agent roster has no active/assignable flag; all seeded agents are assignable.
- No caching, background jobs, metrics, tracing or log shipping; the service
  logs to stdout/stderr only.
- CI runs the backend, frontend and API-backed browser suites, and
  `backend/Dockerfile` plus the root `docker-compose.yml` provide a
  reproducible stack, but there is still no TLS termination, no shared
  multi-instance rate limiter and no managed-database or backup automation.
  See `../docs/architecture/deployment.md`.
- Demo-send delivery remains simulated.
- Seed data covers the 24 detailed tickets, not generated filler.

## Frontend integration

The frontend ships `HttpTicketService` behind the existing `TicketService`
interface and selects it by default (`VITE_DATA_MODE=api`). Feature pages,
hooks and components were not rewritten: the adapter maps snake_case responses,
reshapes pagination, joins note bodies from the notes resource, resolves
`"mine"` through `/auth/me`, sends exact reply versions, and keeps the demo
service available only when `VITE_DATA_MODE=demo` is set explicitly (with a
visible demo banner). Sign-in, session restore, protected routes and sign-out
are implemented against `/api/v1/auth/*`.

The mapping reference is
[`../docs/frontend-backend-integration.md`](../docs/frontend-backend-integration.md).
