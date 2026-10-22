# TicketFlow backend (Phase 6: ticket operations)

Runnable FastAPI service backed by PostgreSQL. Phase 6 builds on the Phase 5
foundation with persistent triage mutations, internal notes, activity history,
agent lookup and ticket dashboard aggregates.

> The frontend still runs entirely on its in-memory `DemoTicketService`. No page
> calls this API yet. Do **not** expose this API publicly: there is no
> authentication and the write endpoints are development-only.

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
    models/            # agents, requesters, tickets, replies, notes, activity
    schemas/           # Pydantic API contracts (never ORM objects)
    repositories/      # SQL queries, filters, allow-listed sorting, aggregates
    services/          # orchestration, transactions, ORM → API mapping
    api/
      deps.py          # request-scoped DB session
      errors.py        # one JSON error envelope for every failure
      params.py        # shared validated ticket path parameter
      routes/          # health, tickets, notes, activities, agents, dashboard
    seed.py            # idempotent demo fixtures mirrored from the frontend
  alembic/versions/
    20261021_0001_initial_schema.py
    20261021_0002_ticket_operations.py
  scripts/seed.py      # CLI: python -m scripts.seed
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
  `ticket_activities.note_id` link. The initial migration is never edited.
- No table is created at API startup; `create_all()` is never used.

## Demo data

```bash
python -m scripts.seed
```

- Inserts 8 agents, 24 requesters, 24 tickets, 5 historical replies and 19
  historical activity records — the same IDs, categories, priorities, statuses,
  assignments and reply↔ticket pairings as the frontend fixtures.
- Idempotent: rows are matched by stable ID/email and existing rows are never
  updated or deleted, so reruns report `0 created` and preserve local edits.
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
| GET | `/api/v1/dashboard/summary` | SQL-derived ticket metrics |

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
- `status_counts` / `category_counts` / `priority_counts`: all tickets, in
  domain order, with zero-count values included.

No reply-approval, SLA, CSAT or revenue metrics are claimed.

## Actor identity limitation

There is no authentication. Mutation and note requests accept an optional
`actor_id` naming an existing seeded agent; it is **untrusted development
metadata**, not a verified identity, and any caller can claim any agent. When
omitted, the seeded demo agent (`AG-01`) is recorded. Activity history is
append-only by API design but is not tamper-proof against database access.
Authentication and server-derived identity are later phases.

## Tests

```bash
python -m pytest -q
python -m pytest tests/test_ticket_mutations.py -q   # one module
```

Tests require the Docker database. The session fixture creates a separate
`ticketflow_test` database, runs `alembic upgrade head`, and truncates all
tables before every test. The development database is never read or modified.

Coverage includes Phase 5 behaviour plus: every mutation rule, all category→
team routes, assignment edge cases (omit vs explicit null, unknown agent,
same-agent no-op), no-op audit policy, actor validation, transactional rollback
when the audit insert fails, note validation/scoping/pagination/atomicity,
ticket and global activity filters/ordering/pagination/privacy, agent roster
filters, dashboard aggregates and mutation propagation, migration drift and
downgrade/upgrade, enum/timezone/FK/check-constraint integrity, seeding
idempotency, and sanitized database-outage responses.

## Limitations

- No authentication/authorization; write endpoints are local-development only.
- No customer reply workflow API (draft/submit/approve/request changes/demo
  send), approvals queue or analytics endpoint.
- No note editing/deletion; notes are append-only.
- No optimistic concurrency control (`If-Match`/version); it is not warranted
  by the current single-operator demo model and is documented as absent rather
  than implied.
- No reply-approval dashboard counts until the reply API exists.
- Agent roster has no active/assignable flag; all seeded agents are assignable.
- No rate limiting, caching, background jobs, metrics, CI or production
  deployment/TLS.
- Seed data covers the 24 detailed tickets, not generated filler.
- The frontend is not connected to the API.

## Frontend integration (planned)

`frontend/src/services/ticketService.ts` defines the UI contract. A later phase
will add an `HttpTicketService` behind the same interface, with camelCase ↔
snake_case mapping, pagination reshaping, note/activity type mapping, and an
authenticated actor replacing `DEMO_USER`. No frontend file was switched in
Phase 6; the existing demo service remains the only data source for every page.
