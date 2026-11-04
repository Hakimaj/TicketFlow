# Deployment and reproducibility

Status: **Phase 9 — release readiness.** This document is the supported way to
start TicketFlow from a clean checkout, and the operator checklist for anything
beyond local evaluation.

TicketFlow is a React + TypeScript + Vite client talking to a FastAPI +
PostgreSQL service. There is no build-time coupling to a vendor: the only
runtime dependency is PostgreSQL.

---

## 1. Prerequisites

| Component | Version | Notes |
| --- | --- | --- |
| Node.js | 20 or 22 | `frontend/package.json` engines-compatible; CI uses 22 |
| Python | 3.11+ | CI and the container use 3.13 |
| PostgreSQL | 16 | Provided by Docker Compose, or any reachable PG 16 |
| Docker + Compose | any current release | Only for the container paths below |
| Google Chrome (stable) | any current release | Only for Playwright; both configs use `channel: 'chrome'` |

No paid service, API key or hosted account is required. Customer message
delivery is deliberately simulated (`send-demo`); no email/SMS/chat provider is
integrated.

---

## 2. Configuration

Nothing secret is committed. Three templates exist and none contain a real
credential:

| Template | Used by | Copy to |
| --- | --- | --- |
| `backend/.env.example` | Local backend development (venv + uv/uvicorn) | `backend/.env` |
| `.env.example` (repository root) | `docker compose up` full stack | `.env` |
| `frontend/.env.example` | Vite build-time overrides only | `frontend/.env.local` (optional) |

### Backend / API settings

| Variable | Required | Purpose |
| --- | --- | --- |
| `JWT_SECRET` | **yes** (except `APP_ENV=test`) | HS256 signing key, at least 32 characters |
| `DATABASE_URL` | yes in practice | `postgresql+psycopg://…`; only PostgreSQL URLs are accepted |
| `APP_ENV` | no (`development`) | `development` \| `test` \| `production` |
| `CORS_ORIGINS` | no | Comma-separated browser origins; `*` is rejected |
| `COOKIE_SECURE` | in production | Must be `true` when `APP_ENV=production` |
| `COOKIE_SAMESITE` | no (`lax`) | `none` additionally requires `COOKIE_SECURE=true` |
| `ACCESS_TOKEN_TTL_MINUTES` | no (`15`) | 1–120 |
| `REFRESH_TOKEN_TTL_DAYS` | no (`14`) | 1–90 |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` | no (`5` / `300`) | Per-process failed-sign-in throttle |
| `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` | bootstrap only | Read by `scripts.bootstrap`; never commit |
| `DEMO_ACCOUNTS_ENABLED` / `DEMO_ACCOUNT_PASSWORD` | no | Development demo accounts; refused in production |

`APP_ENV=production` fails startup unless: `JWT_SECRET` is set, non-placeholder
and ≥32 characters; `COOKIE_SECURE=true`; `DEMO_ACCOUNTS_ENABLED=false`;
`DATABASE_URL` is not the local development default; and every
`CORS_ORIGINS` entry is `https://`. These rules are pinned by
`backend/tests/test_config.py`.

The local templates use `127.0.0.1` rather than `localhost` in
`DATABASE_URL`. This avoids Windows/Docker Desktop resolving `localhost` to IPv6
`::1` first, where the loopback-only PostgreSQL publish is not listening. Alembic
and the test/e2e admin engines also bound connection attempts so an unreachable
host fails instead of hanging.

### Frontend build-time settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_DATA_MODE` | `api` | Only the exact value `demo` selects the in-memory fixtures |
| `VITE_API_BASE_URL` | dev `http://127.0.0.1:8000/api/v1`, production `/api/v1` | API origin; relative values are allowed |

The frontend never holds a credential: the access token lives in memory only
and the refresh token is an HttpOnly cookie owned by the API.

---

## 3. Option A — local development (no application containers)

Terminal 1 — database:

```bash
cd backend
cp .env.example .env          # set POSTGRES_* and JWT_SECRET
docker compose up -d db       # PostgreSQL only (backend/docker-compose.yml)
docker compose ps             # wait for "healthy"
```

Terminal 2 — API:

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m scripts.seed               # optional demo dataset
python -m scripts.bootstrap          # create the first account (env credentials)
python -m uvicorn app.main:app --reload --port 8000
```

Terminal 3 — web client:

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

Sign in at `/login` with the account created by `scripts.bootstrap`, or start
demo mode with `VITE_DATA_MODE=demo npm run dev`.

---

## 4. Option B — full Docker Compose stack

```bash
cp .env.example .env                 # set JWT_SECRET and POSTGRES_PASSWORD
docker compose up -d --build         # db + api + web
docker compose exec api python -m scripts.seed        # optional demo dataset
docker compose exec \
  -e BOOTSTRAP_ADMIN_EMAIL=you@example.com \
  -e BOOTSTRAP_ADMIN_PASSWORD='a-strong-password' \
  api python -m scripts.bootstrap
open http://localhost:8080
```

What the stack does:

- `db` — PostgreSQL 16 in a named volume (`ticketflow-app-pgdata`) that is
  separate from the development volume used by `backend/docker-compose.yml`, so
  the two can never mount the same data directory.
- `api` — runs `alembic upgrade head` and then uvicorn; migrations are applied
  before the port serves traffic, and re-running is a no-op.
- `web` — nginx serving the production build and proxying `/api/` to `api:8000`
  on the same origin, so there is no CORS hop and the refresh cookie stays
  first-party. The production build defaults to the relative `/api/v1` base
  URL.

Useful commands:

```bash
docker compose logs -f api           # API logs
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose down                  # stop, keep data
docker compose down -v               # stop and DELETE the stack's data
```

`docker compose down -v` destroys only this stack's volume. It never touches the
development database volume.

---

## 5. Migrations

The schema is Alembic-managed; no table is created at application startup.

```bash
cd backend
python -m alembic upgrade head       # apply
python -m alembic downgrade -1       # one revision back
python -m alembic current            # applied revision
python -m alembic history            # full chain
```

Chain: `0001_initial_schema` → `0002_ticket_operations` →
`0003_reply_workflow` → `0004_auth` → `0005_intake_accounts`.

Already-applied migrations are never edited; schema changes ship as new
revisions. Downgrade/upgrade round-trips are covered by the test suite.

---

## 6. Accounts

Accounts are never seeded with demo data and no default credential is
committed.

- First administrator: `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD`
  (≥12 characters) through `python -m scripts.bootstrap`.
- Development demo accounts (`agent@ticketflow.local`,
  `reviewer@ticketflow.local`, `admin@ticketflow.local`): set
  `DEMO_ACCOUNTS_ENABLED=true` and `DEMO_ACCOUNT_PASSWORD`; refused unless
  `APP_ENV=development`.
- Seeding demo tickets refuses to run with `APP_ENV=production` unless
  `ALLOW_DEMO_SEED=true` is set deliberately.

Bootstrap is idempotent: existing accounts are reported and never overwritten.

---

## 7. Production checklist

Before pointing real users at an instance:

1. `APP_ENV=production`, `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax`,
   `DEMO_ACCOUNTS_ENABLED=false`.
2. `JWT_SECRET` generated with a CSPRNG (≥32 characters) and stored in a
   secret manager — not in an image, compose file or repository.
3. `DATABASE_URL` pointing at a managed PostgreSQL instance with backups.
4. Terminate TLS in front of the stack and serve the web client and API from
   the same HTTPS origin (`CORS_ORIGINS` lists only that origin).
5. Add an edge or shared rate limiter: sign-in throttling is per process and is
   not a defence for a multi-instance deployment.
6. Run `alembic upgrade head` as a deploy step (the compose `api` service does
   this automatically) and confirm `/api/v1/health/live` and
   `/api/v1/health/ready`.
7. Create real accounts with `scripts.bootstrap`; do not run `scripts.seed`
   unless a demo dataset is genuinely wanted.

---

## 8. Operational limitations

These are known and accepted for this phase — see
[`../release-checklist.md`](../release-checklist.md) for the full list.

- Sign-in throttling is per-process. The Compose `api` service starts uvicorn
  with `--forwarded-allow-ips=*` but publishes no host port, and nginx
  overwrites `X-Forwarded-For` with the real peer address; the limit is
  therefore per account-and-IP inside the provided stack. Any other topology
  must restrict forwarded-header trust to its known reverse proxies. A shared
  limiter is still required for a multi-instance deployment.
- Demo sending records a simulated action and never delivers a message.
- Access tokens are short-lived (15 minutes by default), session-bound with
  rotating refresh sessions, and revoked immediately on logout; an instance
  restart does not by itself invalidate database sessions.
- There is no analytics endpoint; the client derives windowed figures from
  paged API calls.
- `web` has no TLS, HSTS or HTTP→HTTPS redirect; put a reverse proxy or load
  balancer in front of it.
- Logs go to stdout/stderr only; no metrics, tracing or log shipping.
