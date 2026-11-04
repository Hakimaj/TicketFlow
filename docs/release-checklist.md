# Release checklist

Scope: core product completeness (staff ticket intake, administrator account
management, optimistic concurrency), plus the Phase 9 security and
reproducibility baseline. This is **not** a production launch sign-off; read
section 5 before pointing real users at an instance.

Deployment instructions live in
[`architecture/deployment.md`](./architecture/deployment.md); the HTTP contract
is in [`backend-api-contract.md`](./backend-api-contract.md); the frontend
contract is in [`frontend-backend-integration.md`](./frontend-backend-integration.md).

---

## 1. Repeatable verification

Run everything from a clean checkout with PostgreSQL 16 reachable (the
`backend/docker-compose.yml` service or any PG 16). Commands are the ones that
exist in the repository; nothing below is a hypothetical check.

| # | Check | Command | Expected | Result for this revision |
| --- | --- | --- | --- | --- |
| 1 | Migration chain applies | `cd backend && python -m alembic upgrade head` | exits 0, head = `0005_intake_accounts` | **Pass** — head `0005_intake_accounts` (verified on a disposable scratch database) |
| 2 | Migration chain reverses | `python -m alembic downgrade base && python -m alembic upgrade head` | exits 0 both ways | **Pass** — `upgrade → downgrade base → upgrade` all exit 0, `current` = `0005_intake_accounts`; `downgrade 0004_auth → upgrade head` also passes |
| 3 | Migration drift | `python -m alembic check` | `No new upgrade operations detected.` | **Pass** |
| 4 | Backend suite (real PostgreSQL) | `cd backend && python -m pytest -q` | all tests pass | **Pass** — 260 passed, 0 failed |
| 5 | Frontend type-check | `cd frontend && npm run typecheck` | no output, exit 0 | **Pass** |
| 6 | Frontend lint | `npm run lint` | no output, exit 0 | **Pass** |
| 7 | Frontend unit/contract tests | `npm test` | all tests pass | **Pass** — 71 passed (7 files) |
| 8 | Production build | `npm run build` | `dist/` written, exit 0 | **Pass** |
| 9 | Demo-mode browser suite | `npm run test:e2e` | all tests pass | **Pass** — 8 passed (Chrome) |
| 10 | API-backed workflows | `npm run test:e2e:api` | all tests pass | **Pass** — 9 passed against the real API and an isolated `ticketflow_e2e` database |
| 11 | Configuration guards | `python -m pytest tests/test_config.py -q` | all tests pass | **Pass** — 18 passed |
| 12 | Compose definition is valid | `docker compose --env-file .env.example config -q` | exit 0 | **Pass** |
| 13 | Full stack image build | `docker compose up -d --build` | images rebuild, all services healthy | **Blocked in this environment** — Docker Hub egress was refused while resolving base-image auth; no current-revision image could be built |
| 14 | Existing images start and route | `docker compose up -d --no-build` then checks below | all services healthy; API readiness, SPA fallback and auth challenge work | **Pass with cached images** — `db`, `api`, `web` healthy; `ready` = `{"status":"ready","checks":{"database":"ok"}}`; SPA deep link `200`; unauthenticated `/api/v1/tickets` = `401`; current `nginx.conf` passes `nginx -t` |

Migration checks 1–2 were run against a purpose-created scratch database that
was dropped afterwards; the development database was never migrated down or
reset. The same round-trip runs in CI on a throwaway PostgreSQL service.

The cached images used for check 14 predate this working tree, so they validate
Compose wiring and health ordering, not the final image contents. Re-run check 13
with registry access before publishing an image. The current Dockerfiles parsed
far enough for their build definitions to load, and the current `nginx.conf` was
syntax-checked inside the cached nginx image.

Rows 10, 12, 13 and 14 need PostgreSQL or a container runtime. Destructive test
setup is restricted:

- `backend/tests/conftest.py` refuses any test database name that does not match
  `[A-Za-z0-9_]+_test` and never reads the development database.
- `backend/scripts/e2e_prepare.py` refuses any name that does not match
  `[A-Za-z0-9_]+_e2e`.

Both refuse to run against a name that could be a real deployment, before any
destructive statement executes.

---

## 2. Security posture

Enforced server-side (frontend visibility rules are a usability aid only):

| Area | Enforcement | Regression coverage |
| --- | --- | --- |
| Password storage | Argon2id (`argon2-cffi`) | `tests/test_auth.py` |
| Access tokens | HS256 JWT, 15-minute default TTL, `typ`/`iss`/`aud` verified, bound to the refresh-session id (`sid`) | `test_expired_access_token_is_rejected`, `test_protected_endpoints_require_a_valid_token` |
| Refresh sessions | Opaque token, SHA-256 hash only, row-locked rotation, replay revokes the family | `test_refresh_rotates_and_replay_revokes_the_session_family`, `test_concurrent_refresh_serializes_on_the_session_row` |
| Logout | Revokes the cookie session and every session for the account; session-bound access tokens are rejected immediately | `test_logout_revokes_the_cookie_session`, `test_logout_with_access_token_revokes_every_session`, API E2E |
| Cookie safety | HttpOnly, `Path=/api/v1/auth`, `SameSite`, `Secure` in production | `test_login_returns_access_token_and_profile`, `tests/test_config.py` |
| CSRF | `X-Requested-With` marker + `Origin` allow-list on cookie POSTs | `test_login_requires_browser_marker` |
| Route protection | Every operational router requires a verified access token | `tests/test_authorization.py` (every route) |
| Authorization | Role → permission matrix; `replies:review` for review decisions | `tests/test_authorization.py` |
| Actor identity | `actor_id`/`reviewer_id`/`author_id` from the token, never the body | `tests/test_authorization.py` (spoofed fields ignored) |
| Self-approval | Author can never approve/request changes; no role exempt | `tests/test_reply_gate.py` |
| Approval gate | State + exact version + stored decision, mirrored by DB CHECK constraints; row lock on send | `tests/test_reply_gate.py`, `tests/test_schema.py` |
| Demo send | Explicit, approved-only, records a simulated action; no delivery path | `tests/test_replies.py` |
| Config fail-fast | Production rejects weak/placeholder secrets, insecure cookies, dev DB URL, non-HTTPS origins, demo accounts | `tests/test_config.py` |
| No demo fallback | Fixtures require explicit `VITE_DATA_MODE=demo` | `src/services/__tests__/app-mode.test.ts` |
| Secret hygiene | `.env` git-ignored, templates only, no credential in the frontend bundle | manual diff review, `frontend/.env.example` |

Access tokens are held in browser memory; no ticket, reply, customer or auth
data is written to `localStorage` (only two presentation preferences).

---

## 3. Data and workflow integrity

- Tickets, notes, replies, revisions, review decisions and activity rows persist
  in PostgreSQL through Alembic migrations; nothing is inferred client-side.
- Each mutation commits together with its audit event, or both roll back.
- Reply revisions are immutable; editing after submit/approve/request-changes
  returns the reply to `draft` and clears approval metadata.
- Stale approvals cannot be sent: the approved version must equal the current
  revision.
- Concurrent sends cannot both succeed (row lock + database constraints), proven
  by a real two-thread test.
- Migration drift, downgrade/upgrade, enum/timezone/FK integrity and seed
  idempotency are covered by the suite.

---

## 4. Frontend/backend integration

- API mode is the default; the demo dataset is opt-in and visibly labelled.
- A failed operational request surfaces an error state — it never silently shows
  fixture data or reports success.
- Session restore rotates the refresh cookie once on startup (StrictMode
  double-mounts share one restore); an expired session returns the user to
  `/login`.
- `401` triggers exactly one refresh-and-retry; a second failure signs the user
  out instead of looping.
- State is re-read from the API after a full page reload, which the API-backed
  Playwright workflow asserts.
- API-mode Playwright also exercises invalid credentials, CSRF/origin rejection,
  anonymous and malformed-token requests, role boundaries (agent/reviewer/admin),
  reviewer self-approval rejection, approval-without-send, logout revocation,
  refresh-cookie replay rejection, and a failed-request retry state.

---

## 5. Deployment prerequisites (blockers for anything beyond local evaluation)

1. **TLS** — the web container serves plain HTTP. Terminate TLS in front and set
   `COOKIE_SECURE=true`, `APP_ENV=production`, and `https://`-only
   `CORS_ORIGINS`, or the API refuses to start (by design).
2. **Shared rate limiting** — sign-in throttling is in-process memory; a
   multi-instance deployment needs a shared store or an edge limiter.
3. **Secrets management** — `JWT_SECRET` and database credentials must come from
   a secret manager, never an image, compose file or repository.
4. **Managed PostgreSQL with backups** — the compose volume is a single point of
   failure and has no backup automation.
5. **Log aggregation, metrics and alerting** — the stack only writes to
   stdout/stderr.

---

## 6. Known limitations

- Demo sending is simulated; no customer message is ever delivered, and no
  delivery, CSAT or SLA metric exists.
- No analytics endpoint (the client derives windowed figures from paged calls)
  and no activity-facets endpoint.
- Ticket intake captures requester name/email, subject, description, category,
  priority and channel only; there is no attachment, custom-field or
  SLA-policy editor.
- Account management provisions one initial password and forces a change on
  first sign-in; there is no e-mail delivery, password reset link, MFA or
  self-service registration.
- Optimistic concurrency protects ticket triage (`status`, `priority`,
  `category`, assignment) and reply transitions. Notes and account edits carry
  no version precondition beyond the row-level protections described above.
- The agent roster has no active/assignable flag; all seeded agents are
  assignable.
- Sign-in throttling state is lost on restart.
- There is no audit-log tamper protection: rows are append-only through the API,
  but a database-level actor is out of scope.
- Demo mode still bundles fixture modules; they are only ever displayed after
  explicit opt-in.
- The API-backed Playwright launcher is cross-platform
  (`frontend/scripts/e2e-api-server.mjs`); set `E2E_PYTHON=python` outside the
  repository virtualenv layout and `E2E_DATABASE_URL` if the isolated database
  is not the documented local one.

---

## 7. Rollback

- Code: redeploy the previous image tag or commit; the API and web are stateless.
- Schema: `python -m alembic downgrade -1` (or `-<n>`) per revision. Take a
  database backup first — downgrades are not guaranteed to preserve rows added
  after the migration.
- Full stack: `docker compose down` stops the stack and keeps data;
  `docker compose down -v` deletes the stack's volume and is irreversible.

---

## 8. Assessment

| Target | Verdict |
| --- | --- |
| Local evaluation / demo | **Ready.** Documented setup, seeded or bootstrapped accounts, automated browser and API workflows. |
| Staging | **Ready with conditions.** Complete the five infrastructure items in section 5 that are not code (TLS, shared limiter, secret manager, backups, observability). |
| Production | **Not yet.** Sending is simulated, multi-instance rate limiting is missing, account provisioning is manual (no e-mail reset or MFA), and the deployment has no metrics, log shipping or audit-tamper protection. |

Re-run section 1 to reproduce the results recorded above. Verification was
performed on PostgreSQL 16 (Docker), Node 22, Python 3.13 and Google Chrome, on
the revision described in the handover report.
