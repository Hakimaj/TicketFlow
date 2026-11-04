# TicketFlow API contract — `/api/v1` (Phase 10)

Status: **implemented and tested** for the operations below. Everything under
“Planned” is not implemented and must not be treated as working.

Phase 8 adds authenticated accounts, short-lived access tokens, rotating
HttpOnly refresh sessions, a role/permission matrix and trusted attribution on
top of the Phase 7 reply workflow (drafts, immutable revisions, human
approval/change requests, a searchable approval queue and a transactionally
enforced demo-send gate).

Phase 10 adds three capabilities on top of that, without changing the existing
session or approval guarantees:

- **staff ticket intake** — `POST /tickets` (§6.1);
- **optimistic concurrency on triage** — every ticket now carries `version` and
  every triage mutation requires `expected_version` (§6.2–§6.6);
- **account administration** — `GET/POST /accounts` and `PATCH /accounts/{id}`
  plus a self-service `POST /auth/password`, with a forced password change for
  provisioned accounts (§11.4).

Phase 5/6 ticket, note, activity, agent and dashboard endpoints are otherwise
unchanged except for the additive reply dashboard fields, `reply_version` on
activities and the account references listed in §11.

Base URL in local development: `http://127.0.0.1:8000/api/v1`.
Generated reference: `http://127.0.0.1:8000/docs` and
`http://127.0.0.1:8000/api/v1/openapi.json`.

The frontend calls this API by default (`VITE_DATA_MODE=api`). Every
operational endpoint requires `Authorization: Bearer <access token>`; only
`/health/*` and `/auth/*` are public. Tokens are short-lived, roles are read
from PostgreSQL on every request, and actor/reviewer values in request bodies
are ignored. See §11 for the session and authorization contract.

## 1. Conventions

- **Transport:** JSON over HTTP.
- **Versioning:** every application route lives under `/api/v1`.
- **Identifiers:** tickets use public IDs (`TF-1051`, case-insensitive in the
  path). Agents use `AG-xx`. Activities use `ACT-xxxx`. Replies use
  `REP-xxxxxxxxxxxx`. Notes, revision IDs and review-decision IDs are opaque
  UUID strings.
- **Timestamps:** ISO 8601 UTC with milliseconds and `Z`, e.g.
  `2026-10-21T12:00:00.000Z`. Database columns are `timestamptz`; naive request
  values are treated as UTC.
- **Field naming:** responses use `snake_case`; frontend mapping is in §12.
- **Enum values:** lowercase strings identical to the frontend unions:

| Concept | Values |
| --- | --- |
| `status` | `new`, `open`, `pending`, `needs_review`, `resolved`, `closed` |
| `priority` | `urgent`, `high`, `normal`, `low` |
| `category` | `billing`, `delivery`, `technical`, `returns`, `general` |
| `channel` | `web_form`, `email`, `phone`, `chat` |
| `assigned_team` | `customer_support`, `billing_team`, `logistics_team`, `technical_support`, `returns_team` |
| `action` | `created`, `categorized`, `assigned`, `replied_draft`, `replied_sent`, `status_changed`, `escalated`, `review_flagged`, `merged`, `resolved`, `priority_changed`, `note_added`, `reply_submitted`, `reply_approved`, `reply_changes_requested` |
| `actor_type` | `agent`, `system`, `automation` |
| reply `state` | `draft`, `pending_approval`, `approved`, `changes_requested`, `sent` |
| review `decision` | `approved`, `changes_requested` |

CORS allows only the explicitly configured origins and the methods
`GET`, `POST`, `PATCH`, `HEAD`, `OPTIONS`.

## 2. Errors

Every non-2xx response uses one envelope:

```json
{
  "error": {
    "code": "ticket_not_found",
    "message": "Ticket TF-9999 was not found.",
    "details": [{ "field": "status", "message": "Input should be ..." }]
  }
}
```

`details` is present for validation failures and, for conflicts, may carry a
`field`/`message` hint plus machine-readable context (for example
`expected_version`, `current_version` and `updated_at` on a ticket conflict).

| HTTP | `code` | When |
| --- | --- | --- |
| 404 | `ticket_not_found` | Unknown public ticket ID |
| 404 | `reply_not_found` | Unknown public reply ID |
| 404 | `not_found` | Unknown route |
| 405 | `method_not_allowed` | Unsupported method |
| 422 | `validation_error` | Body/query/path validation failed |
| 422 | `invalid_query` | Conflicting query parameters or reversed date range |
| 422 | `invalid_actor` | `actor_id` does not name an existing agent |
| 422 | `actor_unavailable` | No demo actor configured and no `actor_id` supplied |
| 422 | `invalid_agent` | Assignment references a nonexistent agent |
| 422 | `reply_empty` | Defensive: a persisted revision contains no text at submit time |
| 409 | `reply_already_exists` | Ticket already has a non-sent reply |
| 409 | `reply_immutable` | Attempt to edit a demo-sent reply |
| 409 | `reply_already_sent` | Repeated demo send |
| 409 | `reply_already_pending` | Repeated submission |
| 409 | `reply_already_approved` | Submission of an approved reply without a revision |
| 409 | `reply_not_pending` | Approval/change request on a reply not awaiting approval |
| 409 | `reply_version_conflict` | Review request names a stale/nonexistent version |
| 409 | `approval_required` | Demo-send gate rejected the current state/version/approval |
| 409 | `ticket_version_conflict` | Triage mutation sent a stale `expected_version` |
| 409 | `ticket_conflict` | Concurrent requester insert blocked creation; retry |
| 409 | `account_exists` | Email already belongs to an account (or was created concurrently) |
| 409 | `agent_already_linked` | Support agent already backs another account |
| 404 | `account_not_found` | Unknown account ID |
| 400 | `invalid_current_password` | Password change sent the wrong current password |
| 422 | `password_unchanged` | New password identical to the current one |
| 422 | `empty_update` | Account PATCH without any field |
| 403 | `password_change_required` | Provisioned account must change its password first |
| 403 | `self_management_forbidden` | Admin tried to change their own role/activation |
| 409 | `last_admin` | Change would leave no active administrator |
| 503 | `database_unavailable` | PostgreSQL unreachable |
| 500 | `internal_error` | Unexpected failure (generic message only) |

Responses never include SQL, stack traces, connection strings, credentials or
driver messages. Note bodies are never returned in errors or activity summaries.

## 3. Health

| Method | Path | Behaviour |
| --- | --- | --- |
| GET | `/api/v1/health/live` | `200` while the process runs; no DB access |
| GET | `/api/v1/health/ready` | `SELECT 1`; `200` ready, `503` unavailable |

```json
{ "status": "ok", "service": "TicketFlow API", "version": "0.1.0" }
```

```json
{ "status": "ready", "checks": { "database": "ok" } }
```

The readiness body never reveals why the database is unreachable.

## 4. `GET /api/v1/tickets`

Server-side search, filtering, sorting and pagination. All parameters combine
with AND.

| Parameter | Type | Default | Notes |
| --- | --- | --- | --- |
| `page` | int ≥ 1 | `1` | 1-based |
| `page_size` | int 1–100 | `20` | Enforced cap |
| `search` | string ≤ 120 | — | Case-insensitive ticket ID, subject or requester name; `%`/`_` literal |
| `status` | enum, repeatable | — | `?status=open&status=pending` |
| `priority` | enum, repeatable | — | |
| `category` | enum, repeatable | — | |
| `assigned_agent_id` | string | — | e.g. `AG-02` |
| `unassigned` | bool | `false` | Conflicts with `assigned_agent_id` → 422 |
| `sort_by` | enum | `created_at` | `created_at`, `updated_at`, `priority`, `status`, `subject`, `category` |
| `sort_dir` | enum | `desc` | `asc`, `desc` |

Priority/status sort in domain order, not alphabetically. Ties break on
`public_id` ascending. `page_count = ceil(total/page_size)` (`0` for no
matches); a page past the end returns `200` with empty items and the real
`total`.

```json
{
  "items": [
    {
      "id": "TF-1051",
      "subject": "Charged twice from Telebirr for order #ET-88412",
      "requester_name": "Marta Alemu",
      "channel": "web_form",
      "category": "billing",
      "priority": "urgent",
      "status": "open",
      "assigned_team": "billing_team",
      "assigned_agent_id": "AG-02",
      "assigned_agent_name": "Hana Tesfaye",
      "created_at": "2026-10-21T13:50:21.000Z",
      "updated_at": "2026-10-21T14:26:21.000Z"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 24, "page_count": 2 }
}
```

List rows omit the customer email, original message and internal triage note.
List responses also omit notes and replies.

## 5. `GET /api/v1/tickets/{ticket_id}`

Returns the ticket with requester summary and triage metadata; `404` when
unknown.

```json
{
  "id": "TF-1051",
  "subject": "Charged twice from Telebirr for order #ET-88412",
  "requester_name": "Marta Alemu",
  "channel": "web_form",
  "category": "billing",
  "priority": "urgent",
  "status": "open",
  "assigned_team": "billing_team",
  "assigned_agent_id": "AG-02",
  "assigned_agent_name": "Hana Tesfaye",
  "version": 3,
  "created_at": "2026-10-21T13:50:21.000Z",
  "updated_at": "2026-10-21T14:26:21.000Z",
  "description": "I paid for one order but two notifications ...",
  "requester": {
    "id": "ed66f788-da35-425b-ab96-2b36ff6c1163",
    "name": "Marta Alemu",
    "email": "marta.alemu@myetmail.example"
  },
  "due_at": "2026-10-21T22:26:21.000Z",
  "suggested_category": "billing",
  "suggested_priority": "urgent",
  "review_note": null
}
```

`due_at` is `null` for terminal or non-urgent tickets. Replies, notes and
activity are not embedded; use their dedicated endpoints.

## 6. Ticket intake and mutations

Intake is a single `POST`; triage is four focused `PATCH` endpoints with no
generic field update. Request bodies never carry an actor, role or status
authority: the acting account comes from the access token. Every triage body
must carry the `expected_version` the client last read.

### 6.1 `POST /api/v1/tickets` (intake)

Requires the `tickets:write` permission (agent, reviewer and admin all have it)
and a Bearer token.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tickets \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
        "subject": "Refund for order ET-99120 has not arrived",
        "description": "The return was collected two weeks ago and no refund appeared.",
        "category": "billing",
        "priority": "high",
        "channel": "email",
        "requester_name": "Marta Alemu",
        "requester_email": "marta.alemu@example.com"
      }'
```

| Field | Required | Rules |
| --- | --- | --- |
| `subject` | yes | 3–300 chars after trimming; blank rejected |
| `description` | yes | 10–5000 chars after trimming; blank rejected |
| `category` | yes | one of the five categories |
| `priority` | no | defaults to `normal` |
| `channel` | no | defaults to `web_form` |
| `requester_name` | yes | 2–160 chars after trimming |
| `requester_email` | yes | must look like an address; stored lower-case |

Defaults and attribution, applied server-side and not overridable:

- `status` is always `new`; the body cannot set it.
- `assigned_team` comes from the category → team mapping in §6.4 and no agent is
  guessed.
- `due_at` uses the same 8-hour SLA target as triage for `urgent`/`high` and is
  `null` otherwise.
- `version` starts at `1`.
- An existing requester with the same normalized email is reused, so one
  customer can own several tickets.
- The creator comes from the access token; the `created` audit event stores both
  the agent and the account reference. Detail:
  `Ticket created via web_form intake.`

Returns `201` with the ticket in the detail shape (including `version`). The
requester row, ticket row and audit event commit in one transaction; if any part
fails, nothing is persisted. A concurrent insert of the same new requester email
is retried once and then reported as `409 ticket_conflict`. Ticket numbers are
allocated under a PostgreSQL advisory lock, so `TF-####` values stay unique and
sequential.

Malformed bodies and invalid enum values return `422 validation_error` with
field-level details and never create a row.

### 6.2 `PATCH /api/v1/tickets/{ticket_id}/status`

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/tickets/TF-1051/status \
  -H 'Content-Type: application/json' \
  -d '{"status": "pending", "expected_version": 3}'
```

Rules:

- `expected_version` is **required** and must be ≥ 1.
- Values are the six statuses above; anything else → `422 validation_error`.
- `updated_at` and `version` advance.
- `resolved`/`closed` clear `due_at`.
- Audit action: `resolved` for resolved, `review_flagged` for needs review,
  otherwise `status_changed`. Detail: `Status changed from Open to Pending.`
- Repeating the current status is a no-op: response is the current ticket, no
  audit event, `updated_at`/`version` unchanged.

### 6.3 `PATCH /api/v1/tickets/{ticket_id}/priority`

```json
{ "priority": "urgent" }
```

- Active (`new`/`open`/`pending`) urgent/high tickets receive an 8-hour target
  from now; other priorities clear `due_at`.
- Terminal tickets keep their existing `due_at`.
- Audit action `priority_changed`, detail
  `Priority changed from Low to Urgent.`
- Repeating the current priority is a no-op.

### 6.4 `PATCH /api/v1/tickets/{ticket_id}/category`

```json
{ "category": "delivery" }
```

Category → team is authoritative:

| Category | `assigned_team` |
| --- | --- |
| `billing` | `billing_team` |
| `delivery` | `logistics_team` |
| `technical` | `technical_support` |
| `returns` | `returns_team` |
| `general` | `customer_support` |

- An existing agent assignment is **preserved**. The API never silently
  reassigns or unassigns an agent when the category changes.
- Audit action `categorized`, detail
  `Category changed from Billing to Delivery (routed to Logistics Team).`
- Repeating the current category is a no-op.

### 6.5 `PATCH /api/v1/tickets/{ticket_id}/assignment`

```json
{ "agent_id": "AG-04" }
```

- `agent_id` is **required and nullable**. `{ "agent_id": null }` deliberately
  unassigns. Omitting the field, or sending an empty string, is a validation
  error, never an accidental unassignment.
- Unknown agent → `422 invalid_agent`; no change or event.
- Any existing agent is assignable (the current domain has no active flag and
  the frontend offers the whole roster).
- Assignment changes only `assigned_agent_id`; the category-derived team is
  preserved. Reassign the category separately if a team move is intended.
- Audit detail is one of `Assigned to X.`, `Reassigned from A to B.`,
  `Unassigned (previously assigned to A).`
- Repeating the current assignee is a no-op.

### 6.6 Transactions, no-ops and concurrency

- Ticket change + required activity event commit in one database transaction.
  If either fails, both are rolled back; no partial audit state is possible.
- Successful responses are returned only after commit.
- No-op requests create no audit entry and do not touch `updated_at`/`version`.
- Every triage mutation takes a `SELECT … FOR UPDATE` row lock, compares
  `expected_version` to the persisted `version`, and only then writes, all
  inside one transaction. Two operators acting on the same version therefore
  serialise: the first commits `version + 1`, the second sees the new value and
  is rejected with `409 ticket_version_conflict`:

```json
{
  "error": {
    "code": "ticket_version_conflict",
    "message": "Ticket TF-1043 changed since you loaded it. Reload the ticket and apply your change again.",
    "details": [
      {
        "field": "expected_version",
        "message": "Expected version 3 but the ticket is already at version 4.",
        "expected_version": 3,
        "current_version": 4,
        "updated_at": "2026-10-27T09:14:02.000Z"
      }
    ]
  }
}
```

  A rejected request writes nothing (no field change, no audit event, no version
  bump) and is never retried by the server. The client reloads the ticket and
  asks the user to reapply their change.
- `expected_version` is a precondition only; it never grants authorization. The
  acting account and its permissions are still resolved from PostgreSQL.
- Demo sending an approved reply also changes triage state (status →
  `pending`), so it bumps `version` too; a triage form loaded before the send is
  rejected rather than overwriting the new status.

## 7. Internal notes

Notes are staff-only records, never customer replies.

### `POST /api/v1/tickets/{ticket_id}/notes`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tickets/TF-1051/notes \
  -H 'Content-Type: application/json' \
  -d '{"content": "Customer confirmed the reversal window.", "actor_id": "AG-02"}'
```

- `201` on success, `404` for an unknown ticket.
- Content is trimmed; blank/whitespace-only and >4000 characters → `422`.
- Author is resolved from `actor_id` (or the demo agent) and must exist.
- A dedicated `ticket_notes` row is created. The `note_added` activity stores
  `Internal note added.` plus `note_id` and `is_internal_note=true`; the note
  body is **never** copied into activity metadata.
- The ticket's `updated_at` advances. Note + activity + ticket touch commit
  atomically.

```json
{
  "id": "0f6c2f34-9d5d-4b7b-8e95-5b31f0e9f1a4",
  "ticket_id": "TF-1051",
  "content": "Customer confirmed the reversal window.",
  "author": { "id": "AG-02", "name": "Hana Tesfaye" },
  "created_at": "2026-10-21T18:12:04.512Z",
  "updated_at": "2026-10-21T18:12:04.512Z"
}
```

### `GET /api/v1/tickets/{ticket_id}/notes`

Query: `page` (≥1, default 1), `page_size` (1–100, default 20). Returns notes
for that ticket only, oldest first with a UUID tiebreak. Unknown ticket → `404`.

```json
{
  "items": [],
  "pagination": { "page": 1, "page_size": 20, "total": 0, "page_count": 0 }
}
```

Notes are never returned by reply endpoints or activity summaries. Internal
notes remain a separate resource from customer replies, and there is no
edit/delete API.

## 8. Activity history

Both endpoints read the same `ticket_activities` rows written by mutations,
notes and the seeded history. They never read a second audit system.

### `GET /api/v1/tickets/{ticket_id}/activities`

Returns a JSON array (oldest first, stable `public_id` tiebreak) for one
ticket. Unknown ticket → `404`. No pagination is needed for a single ticket's
timeline in this phase.

### `GET /api/v1/activities`

| Parameter | Type | Default | Notes |
| --- | --- | --- | --- |
| `page` | int ≥ 1 | `1` | |
| `page_size` | int 1–100 | `20` | |
| `ticket_id` | string ≤ 32 | — | Exact public ticket ID; unknown → empty list |
| `action` | enum, repeatable | — | e.g. `?action=note_added&action=assigned` |
| `actor_id` | string ≤ 16 | — | Exact agent ID; unknown → empty list |
| `search` | string ≤ 120 | — | Ticket ID, actor name, action value, action label or safe summary; LIKE wildcards escaped |
| `start` | datetime | — | Inclusive lower bound (UTC assumed if offset omitted) |
| `end` | datetime | — | **Exclusive** upper bound; `start > end` → `422 invalid_query` |
| `sort_dir` | enum | `desc` | `desc` newest first, `asc` oldest first |

Ordering is `created_at` in the requested direction with `public_id` ascending
as the tiebreak, so equal timestamps are deterministic. Pagination semantics
match the ticket list.

```json
{
  "items": [
    {
      "id": "ACT-040",
      "ticket_id": "TF-1051",
      "reply_id": null,
      "reply_version": null,
      "note_id": null,
      "actor_id": "AG-02",
      "actor_name": "Hana Tesfaye",
      "actor_type": "agent",
      "action": "assigned",
      "summary": "Claimed for Billing triage; duplicate-charge form sent to requester.",
      "is_internal_note": false,
      "created_at": "2026-10-21T11:36:00.000Z"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 19, "page_count": 1 }
}
```

`summary` is the stored short description, or the action label when absent. It
never contains customer messages, customer email addresses, reply drafts,
reviewer comments or note bodies. Note events expose only `note_id`; reply
events expose `reply_id` and the exact `reply_version`.

## 9. Agents and dashboard

### `GET /api/v1/agents`

Optional filters `team` and `role`. Returns the small persistent roster ordered
by agent ID; no pagination is needed. No email, credentials or account data.

```json
{
  "items": [
    {
      "id": "AG-01",
      "name": "Abebe Kebede",
      "role": "supervisor",
      "team": "customer_support",
      "is_demo_user": true
    }
  ]
}
```

All seeded agents are assignable; the current domain has no active flag.

### `GET /api/v1/dashboard/summary`

SQL aggregates over tickets and logical replies:

| Field | Definition |
| --- | --- |
| `total_tickets` | All persisted tickets |
| `active_tickets` | Status `new`, `open` or `pending` |
| `unassigned_tickets` | Active tickets with no agent |
| `urgent_high_tickets` | Active tickets with priority urgent/high |
| `needs_review_tickets` | All tickets with ticket-level status `needs_review` (separate from reply approvals) |
| `pending_reply_approvals` | Logical replies in `pending_approval` |
| `draft_replies` | Logical replies in `draft` |
| `approved_replies_awaiting_send` | Logical replies in `approved` |
| `sent_replies_demo` | Logical replies marked sent in demo mode (not deliveries) |
| `status_counts` | All tickets per status (zero values included, domain order) |
| `category_counts` | All tickets per category |
| `priority_counts` | All tickets per priority |
| `generated_at` | Server UTC time of the request |

```json
{
  "generated_at": "2026-10-21T18:00:00.000Z",
  "total_tickets": 24,
  "active_tickets": 17,
  "unassigned_tickets": 5,
  "urgent_high_tickets": 7,
  "needs_review_tickets": 2,
  "pending_reply_approvals": 2,
  "draft_replies": 0,
  "approved_replies_awaiting_send": 1,
  "sent_replies_demo": 1,
  "status_counts": [{ "status": "new", "count": 4 }],
  "category_counts": [{ "category": "billing", "count": 6 }],
  "priority_counts": [{ "priority": "urgent", "count": 4 }]
}
```

SLA/CSAT, revenue, trends and real delivery counts are deliberately **not**
included: no such history exists, and `sent_replies_demo` is a simulated
application action rather than proof of customer delivery.

## 10. Reply workflow (Phase 7)

### 10.1 Model and revision history

Three related records, all in PostgreSQL:

| Table | Purpose |
| --- | --- |
| `customer_replies` | The **logical reply**: current state, current version/body, `submitted_version`, `approved_version`, current reviewer metadata, demo-send metadata, author |
| `reply_revisions` | **Immutable** body snapshots, unique on `(reply_id, version)`; never updated |
| `reply_reviews` | **Append-only** human decisions, each tied to one exact revision (`revision_id`, `version`) with reviewer snapshot and internal comment |

Rules enforced in the schema as well as the service:

- `approved_version = version` whenever `state = 'approved'` (and approval
  metadata is present);
- `approved_version = version` whenever `state = 'sent'` (with an explicit
  `IS NOT NULL` guard, because `NULL = version` would otherwise pass a CHECK);
- `submitted_version = version` whenever `state = 'pending_approval'`;
- a `changes_requested` review decision requires a non-blank internal comment
  (max 2000 chars);
- one non-`sent` reply per ticket (partial unique index).

Changing the body always inserts a new revision. Historical revisions and
review decisions are never overwritten. `reviewer_feedback` on the logical
reply is the *current* comment; historical comments remain in `reply_reviews`.
Reviewer comments are staff-only and are never part of the reply body or a
general activity summary.

### 10.2 State machine

```
draft ──submit──▶ pending_approval ──approve──▶ approved ──send-demo──▶ sent
  ▲                      │
  │                      └──request-changes──▶ changes_requested
  └──────────── edit / resubmit ────────────────────┘
```

| Operation | Allowed from | Result | Audit action |
| --- | --- | --- | --- |
| Save/revision | `draft`, `pending_approval`, `approved`, `changes_requested` | `draft`; content unchanged is a no-op | `replied_draft` |
| Submit | `draft`, `changes_requested` | `pending_approval` | `reply_submitted` |
| Approve | `pending_approval` + exact current version | `approved` | `reply_approved` |
| Request changes | `pending_approval` + exact current version + comment | `changes_requested` | `reply_changes_requested` |
| Send demo | `approved` + exact current version + stored approval decision | `sent` | `replied_sent` (+ `status_changed` when applicable) |

Saving, submitting and approving are **separate operations**. None of them
sends anything. Approval never changes the ticket status. Only the explicit
demo-send may move a reply to `sent`, and it also moves `new`/`open` tickets to
`pending` (the existing frontend rule). Resolved/closed tickets keep their
status.

A reply in `changes_requested` may be resubmitted without changing the text
(matching the frontend demo service) or revised first; either way the earlier
change-request decision remains in `reply_reviews` and no approval carries over.

### 10.3 `POST /api/v1/tickets/{ticket_id}/replies`

Creates the ticket's single active draft, revision 1 and an audit event in one
transaction. Returns `201` with the reply detail.

```json
{ "body": "Dear Marta, ...", "actor_id": "AG-02" }
```

- `body` is trimmed and must be 1–8000 characters; blank/whitespace → `422`
  (the frontend demo service also rejects empty drafts).
- The **recipient cannot be supplied**: it is derived from the ticket requester
  and returned as `recipient: {name, email}`.
- Unknown ticket → `404 ticket_not_found`; unknown actor → `422 invalid_actor`.
- Existing non-sent reply → `409 reply_already_exists` (the message/details name
  the reply). After a reply is sent, a new draft can be created.
- No ticket status change.

### 10.4 `GET /api/v1/tickets/{ticket_id}/replies`

`page` (≥1, default 1) and `page_size` (1–100, default 20). Returns only that
ticket's replies, newest creation first, with `pagination={page,page_size,total,page_count}`.
Unknown ticket → `404`. Each item is the summary shape (no revision/review
arrays).

### 10.5 `GET /api/v1/replies/{reply_id}`

Returns the current summary plus `revisions` (oldest version first, each with
`id`, `version`, `body`, `author`, `created_at`) and `reviews` (oldest first,
each with `decision`, `version`, `reviewer_id`, `reviewer_name`, `comment`,
`created_at`). Unknown reply → `404 reply_not_found`.

```json
{
  "id": "REP-4F2A9C1B7D3E",
  "ticket_id": "TF-1051",
  "author": { "id": "AG-02", "name": "Hana Tesfaye" },
  "recipient": { "name": "Marta Alemu", "email": "marta.alemu@myetmail.example" },
  "body": "Dear Marta, ...",
  "state": "pending_approval",
  "version": 1,
  "submitted_at": "2026-10-21T11:36:00.000Z",
  "submitted_version": 1,
  "reviewed_at": null,
  "reviewer_id": null,
  "reviewer_name": null,
  "reviewer_feedback": null,
  "approved_version": null,
  "sent_at": null,
  "sent_by_actor_name": null,
  "created_at": "2026-10-21T11:06:00.000Z",
  "updated_at": "2026-10-21T11:36:00.000Z",
  "revisions": [{ "id": "...", "version": 1, "body": "Dear Marta, ...", "author": { "id": "AG-02", "name": "Hana Tesfaye" }, "created_at": "2026-10-21T11:06:00.000Z" }],
  "reviews": []
}
```

### 10.6 `PATCH /api/v1/replies/{reply_id}`

```json
{ "body": "Revised text", "actor_id": "AG-02" }
```

- Identical text (after trimming) is a true no-op: no new revision, no event,
  no `updated_at` change.
- Changed text creates the next immutable revision and increments `version`.
- Editing `pending_approval`, `approved` or `changes_requested` returns the
  reply to `draft`, clears `submitted_at`/`submitted_version`/reviewer fields/
  `approved_version`, and requires resubmission. Prior review decisions stay in
  the history.
- A `sent` reply is immutable → `409 reply_immutable`; start a new reply.

### 10.7 `POST /api/v1/replies/{reply_id}/submit`

Body: `{ "actor_id": "AG-02" }` (optional). Rejects sent (`409
reply_already_sent`), pending (`409 reply_already_pending`) and approved
(`409 reply_already_approved`) replies. On success records `submitted_at`,
`submitted_version`, clears any current review metadata and writes
`reply_submitted`. At least one revision body must be non-blank.

### 10.8 `GET /api/v1/replies/approvals`

Pending-approval queue. Only current `pending_approval` replies appear; drafts,
changes-requested, approved and sent replies never do.

| Parameter | Type | Default | Notes |
| --- | --- | --- | --- |
| `page` | int ≥ 1 | `1` | |
| `page_size` | int 1–100 | `20` | |
| `search` | string ≤ 120 | — | Ticket ID/subject, reply ID, author name or reply text; LIKE wildcards escaped |
| `category` | enum, repeatable | — | Ticket category |
| `priority` | enum, repeatable | — | Ticket priority |
| `sort_dir` | enum | `desc` | Submission time; `public_id` ascending tiebreak |

Filtering, counting, ordering and pagination run in SQL. Ticket subject,
category, priority and requester name are read from the joined ticket, not from
cached copies.

```json
{
  "items": [{
    "reply_id": "REP-101",
    "ticket_id": "TF-1051",
    "ticket_subject": "Charged twice from Telebirr for order #ET-88412",
    "ticket_category": "billing",
    "ticket_priority": "urgent",
    "ticket_status": "open",
    "requester_name": "Marta Alemu",
    "author": { "id": "AG-02", "name": "Hana Tesfaye" },
    "version": 1,
    "submitted_version": 1,
    "submitted_at": "2026-10-21T11:36:00.000Z",
    "preview": "Dear Marta, Thank you for reaching out ...",
    "state": "pending_approval"
  }],
  "pagination": { "page": 1, "page_size": 20, "total": 2, "page_count": 1 }
}
```

`preview` is whitespace-collapsed and limited to 180 characters; fetch the
reply detail for the full submitted text. The queue has no `body` field.

### 10.9 `POST /api/v1/replies/{reply_id}/approve`

```json
{ "version": 1, "reviewer_id": "AG-01", "comment": "Looks good." }
```

- Requires `pending_approval`; otherwise `409 reply_not_pending`.
- `version` must equal the currently submitted version; stale values →
  `409 reply_version_conflict`.
- Records reviewer, timestamp, the exact approved version and an append-only
  `reply_reviews` decision, then transitions to `approved`.
- Optional `comment` (≤2000) is internal; it is stored on the decision, never in
  the body or general activity summary.
- Does **not** send and does **not** change the ticket status. Repeated approval
  fails with `reply_not_pending`.

### 10.10 `POST /api/v1/replies/{reply_id}/request-changes`

```json
{ "version": 1, "reviewer_id": "AG-01", "comment": "Add the 24–48 hour window." }
```

Requires pending state and the exact submitted version. `comment` is mandatory,
trimmed, non-blank and ≤2000 characters. Stores the decision and internal
feedback for that revision, transitions to `changes_requested`, and writes a
safe `reply_changes_requested` event that does not contain the comment. The
reply can then be revised and resubmitted.

### 10.11 `POST /api/v1/replies/{reply_id}/send-demo`

**This marks the reply as sent in demo mode. No customer message is delivered.**

Body: `{ "actor_id": "AG-01" }` (optional). The server-side gate requires all of:

1. current state is `approved`;
2. `approved_version` equals the current `version`;
3. `submitted_version` equals the current version and reviewer metadata exists;
4. a stored `approved` review decision exists for that exact revision;
5. the current revision body matches the reply body;
6. the reply has not already been sent.

Inside one transaction the reply row is locked (`SELECT … FOR UPDATE`), the
ticket is locked, the reply becomes `sent`, `sent_at` and
`sent_by_actor_name` are recorded, and the audit events are written. Concurrent
send attempts serialize; the loser sees the committed `sent` state and gets
`409 reply_already_sent`. Calling the service directly applies the same gate.

```json
{
  "reply": { "id": "REP-...", "state": "sent", "sent_at": "...", "sent_by_actor_name": "Abebe Kebede", "approved_version": 1, "...": "..." },
  "delivery": "demo_marked_sent",
  "notice": "The reply was marked as sent in demo mode. No email, SMS or other customer message was delivered."
}
```

`delivery` is a stable machine value and never claims delivery. Failures return
`409 approval_required` (wrong state/version/missing approval), `409
reply_already_sent`, or `409 reply_immutable` for edits.

### 10.12 Reply activity events

| Action | When | Safe detail | Links |
| --- | --- | --- | --- |
| `replied_draft` | Draft created or revised | Version and invalidation reason; never the body | `reply_id`, `reply_version` |
| `reply_submitted` | Submitted/resubmitted | Version and actor | `reply_id`, `reply_version` |
| `reply_approved` | Approved | Version and reviewer | `reply_id`, `reply_version` |
| `reply_changes_requested` | Changes requested | Version and reviewer; comment excluded | `reply_id`, `reply_version` |
| `replied_sent` | Demo send | Version, actor and “no external message transmitted” | `reply_id`, `reply_version` |
| `status_changed` | Demo send moved new/open → pending | Previous/new status | `reply_id`, `reply_version` |

Each event commits in the same transaction as its transition. A failure rolls
back the reply change, revisions/review decisions and audit row together.

### 10.13 Dashboard reply metrics

`GET /api/v1/dashboard/summary` now also returns, counted per **logical reply**
(never per revision):

| Field | Definition |
| --- | --- |
| `pending_reply_approvals` | Replies in `pending_approval` |
| `draft_replies` | Replies in `draft` |
| `approved_replies_awaiting_send` | Replies in `approved` (approval does not send) |
| `sent_replies_demo` | Replies in `sent` — simulated sends, **not** deliveries |

The existing ticket-level `needs_review_tickets` is unchanged and separate.
Aggregates run as SQL `GROUP BY` over `customer_replies.state`.

## 11. Authentication, authorization and actor identity

### 11.1 Endpoints

| Method & path | Auth | Behaviour |
| --- | --- | --- |
| `POST /auth/login` | Public + `X-Requested-With: ticketflow` | Verifies email/password (Argon2id). Returns `{access_token, token_type, expires_in, user}` and sets the refresh cookie. Generic `401 invalid_credentials` for unknown, inactive or wrong-password accounts. `429 too_many_attempts` after repeated failures. |
| `POST /auth/refresh` | Refresh cookie + browser marker | Rotates the refresh token (previous token becomes unusable) and returns a new access token/profile. `401 refresh_invalid` when missing, revoked, expired or reused; reuse also revokes every active session for the account. |
| `POST /auth/logout` | Optional access token + cookie | Revokes the presented session, and all active sessions for the account when the access token is valid. Clears the cookie. Safe with an expired access token. |
| `GET /auth/me` | Bearer | Returns the database-backed account: `id`, `email`, `display_name`, `role`, `agent_id`, `agent_name`, `must_change_password`, `permissions`. |
| `POST /auth/password` | Bearer + browser marker | Replaces the signed-in account's own password. Body `{current_password, new_password}` (≥12 chars). Verifies with Argon2id, revokes every existing refresh session, issues a new rotated one and clears `must_change_password`. `400 invalid_current_password`, `422 password_unchanged`. |

The refresh cookie is HttpOnly, SameSite (configurable) and scoped to
`/api/v1/auth`. Cookie-authenticated POSTs also require
`X-Requested-With: ticketflow` and an allowed `Origin` when present
(`403 csrf_rejected` / `origin_rejected`). Access tokens are HS256 JWTs with
`iss`, `aud`, `typ=access`, `iat`, `exp`, a `sid` tied to the refresh-session row
and a short TTL (15 minutes by default). The JWT is never persisted
server-side; the `sid` check makes logout and replay revocation take effect
immediately.

### 11.2 Roles and permissions

| Operation | agent | reviewer | admin |
| --- | --- | --- | --- |
| Read tickets, notes, activities, agents, dashboard | yes | yes | yes |
| Triage mutations, assignment, internal notes | yes | yes | yes |
| Create/edit/submit reply drafts, demo-send an approved reply | yes | yes | yes |
| Approve / request changes | no | yes | yes |
| Manage accounts | no | no | yes |

Permission dependencies live in `app/authorization.py` and are applied per
route; all operational routers additionally require a valid Bearer token.
Failures use `401 not_authenticated` / `invalid_token` or `403 forbidden`.

An account whose `must_change_password` flag is set (an administrator
provisioned it with an initial password) can sign in, call `/auth/me`, change
its password and log out; every operational endpoint answers `403
password_change_required` until it does.

### 11.3 Trusted attribution

`actor_id`, `reviewer_id`, `author_id` and role values sent by a client are
ignored. The acting account comes from the validated access token, with the
role re-read from `user_accounts`. Notes, ticket changes, reply revisions,
reviews and demo sends store both the historical agent id and the
`*_account_id` reference. Historical rows created before Phase 8 keep their
agent attribution with a NULL account reference rather than inventing an
account.

A reply author can never approve or request changes on their own reply
(`403 self_approval_forbidden`), including an administrator. Activity and review
rows remain append-only through the API; this is not a tamper-proof audit
system against direct database access.

### 11.4 Account administration (`accounts:manage`)

Administrator only; agents and reviewers receive `403 forbidden` on every
endpoint below. Responses never contain a password hash, refresh-token hash or
session identifier.

| Method & path | Behaviour |
| --- | --- |
| `GET /accounts` | Paginated list (`page`, `page_size` ≤ 100, `search` over email/name/agent, `role`, `is_active`). Items carry `id`, `email`, `display_name`, `role`, `is_active`, `must_change_password`, `agent_id`, `agent_name`, `created_at`, `updated_at`. |
| `POST /accounts` | Provisions an account. Body: `email`, `display_name`, `role`, `password` (initial, ≥12 chars), optional `agent_id` and `is_active`. The password is hashed with the shared Argon2id helper, never returned or logged, and the account is flagged `must_change_password`. `409 account_exists` for a duplicate email, `409 agent_already_linked`, `422 invalid_agent`. |
| `PATCH /accounts/{account_id}` | Updates `display_name`, `role`, `agent_id` (send `null` to unlink) and/or `is_active`. Omitted fields stay untouched; an empty body is `422 empty_update`. Deactivating revokes every refresh session immediately, and the account can no longer sign in or rotate a session. |

Guards enforced server-side:

- the acting identity and role come from the database, never from the body;
- an administrator cannot change their own `role` or `is_active`
  (`403 self_management_forbidden`), so a request cannot escalate or lock out
  the caller;
- a change that would leave no active administrator is refused (`409
  last_admin`) — defensive, because the self-management guard already keeps the
  acting administrator active;
- one support agent backs at most one account, and emails are unique and stored
  lower-case;
- accounts are deactivated, never hard-deleted, so historical ticket and audit
  attribution stays valid.

## 12. Frontend ↔ API mapping

### Ticket fields

Unchanged from Phase 5 plus `version` (Phase 10): `id`, `subject`, `channel`,
`category`, `priority`, `status`, `assigned_team`, `assigned_agent_id`,
`assigned_agent_name`, `version`, `created_at`, `updated_at`; detail adds
`description`, `requester`, `due_at`, `suggested_category`,
`suggested_priority`, `review_note`. The list still omits requester
email/description/review note. `version` maps to the frontend `Ticket.version`
(optional there because demo fixtures have no concurrent writers).

### Operations ↔ `TicketService`

| Frontend method | API |
| --- | --- |
| `listTickets(query)` | `GET /tickets` (see pagination mapping below) |
| `getTicket(id)` | `GET /tickets/{id}` |
| `createTicket(input)` | `POST /tickets` (no actor/status/version fields) |
| `updateStatus(id, status, agent?, {expectedVersion})` | `PATCH /tickets/{id}/status` |
| `updatePriority(id, priority, agent?, {expectedVersion})` | `PATCH /tickets/{id}/priority` |
| `updateCategory(id, category, agent?, {expectedVersion})` | `PATCH /tickets/{id}/category` |
| `assignTicket(id, agentId, agent?, {expectedVersion})` | `PATCH /tickets/{id}/assignment` with `{"agent_id": agentId}` (`null` unassigns) |
| `addInternalNote(id, note)` | `POST /tickets/{id}/notes` (returns a note, not a `TicketActivity`) |
| `getTicketActivities(id)` | `GET /tickets/{id}/activities` |
| `listActivityLog(query)` | `GET /activities` |
| `listAgents()` / `getAgent(id)` | `GET /agents`; fetch once and look up by ID |
| `getReplies(ticketId)` | `GET /tickets/{id}/replies` |
| `getReply(replyId)` | `GET /replies/{replyId}` |
| `saveReplyDraft(ticketId, body, author)` | `POST /tickets/{id}/replies` (new) or `PATCH /replies/{replyId}` (edit) |
| `submitReplyForApproval(replyId)` | `POST /replies/{replyId}/submit` |
| `approveReply(replyId, reviewer)` | `POST /replies/{replyId}/approve` with `{version, reviewer_id}` |
| `requestReplyChanges(replyId, feedback, reviewer)` | `POST /replies/{replyId}/request-changes` with `{version, reviewer_id, comment}` |
| `markReplySent(replyId, actor)` | `POST /replies/{replyId}/send-demo` |
| `listPendingReplies()` | `GET /replies/approvals` |
| `listAllReplies()` | not implemented as one call; combine per-ticket lists or the queue |
| `getDashboardStats()` | `GET /dashboard/summary` (ticket + reply metrics) |
| `getAdjacentTicketIds`, analytics, facets | not implemented |
| account service (`listAccounts`/`createAccount`/`updateAccount`) | `GET/POST /accounts`, `PATCH /accounts/{id}` |

Every triage method requires `expectedVersion`. The HTTP service refuses to
send a mutation without it (`missing_ticket_version`) rather than dropping the
precondition, and maps `ticket_version_conflict` to a reload prompt. The detail
page then refetches the ticket and asks the operator to reapply the change; it
never retries automatically.

### Type mapping

**`ActivityResponse` → frontend `TicketActivity`**

| API | Frontend |
| --- | --- |
| `id` | `id` |
| `ticket_id` | `ticketId` |
| `reply_id` | `replyId` |
| `reply_version` | no direct field; use as revision metadata |
| `actor_name` | `actorName` |
| `actor_type` | `actorType` |
| `action` | `action` |
| `summary` | `detail` |
| `created_at` | `createdAt` |
| `note_id`, `actor_id`, `is_internal_note` | no direct frontend fields; carry as extra metadata |

**`ActivityResponse` → frontend `ActivityLogEntry`**: `summary` maps directly;
`activity.id` is already the public ID. The frontend `range: 7 | 30 | 'all'`
filter becomes `start` (midnight UTC/local decisions must be made in the
adapter); its actor-name filter must use `actor_id` or `search`, because no
name-only filter or facet endpoint exists yet.

**Notes** have no frontend type yet. A later integration would add a small
`InternalNote` model (`id`, `ticketId`, `content`, `author`, timestamps). The
current UI shows note text through the ticket activity timeline; with the API,
that text must be fetched from the notes endpoint, while the timeline shows the
safe summary and `note_id`.

**`ReplySummary` / `ReplyDetail` → frontend `CustomerReply`**

| API | Frontend |
| --- | --- |
| `id` | `id` |
| `ticket_id` | `ticketId` |
| `author.id` / `author.name` | `authorId` / `authorName` |
| `body` | `body` (current revision) |
| `state` | `state` |
| `version` | `version` |
| `created_at` / `updated_at` | `createdAt` / `updatedAt` |
| `submitted_at` | `submittedAt` |
| `reviewed_at` | `reviewedAt` |
| `reviewer_id` / `reviewer_name` | `reviewerId` / `reviewerName` |
| `reviewer_feedback` | `reviewerFeedback` (internal; do not render to customers) |
| `sent_at` / `sent_by_actor_name` | `sentAt` / `sentByActorName` |

Extra API-only fields: `recipient` (derived from the ticket requester),
`submitted_version`, `approved_version`, `revisions[]`, `reviews[]`. The
frontend model has no revision/decision arrays yet; the adapter must add them
if the UI needs history. `approved_version` is the authoritative send-gate
version and must not be inferred from `state` in the client.

**Approval queue → `listPendingReplies()` / Reply Approvals page:** each item
maps `reply_id` → `CustomerReply.id`, `ticket_*` → parent ticket fields,
`author` → author fields, `version`/`submitted_version`/`submitted_at`,
`state` → `state`, and `preview` → the card preview. Because the queue omits
`body` and the reviewer review fields, fetch `GET /replies/{id}` before showing a
full review pane. Queue pagination is `{items, pagination}` with `page`,
`page_size`, `search`, repeatable `category`/`priority` and `sort_dir`.

**Demo-send result:** `POST /replies/{id}/send-demo` returns
`{reply, delivery: "demo_marked_sent", notice}`. Map `reply` to `CustomerReply`;
surface `notice` (or an equivalent “marked as sent in demo mode” label) and never
report actual delivery.

**Dashboard mapping:** `openTickets` ← `active_tickets`,
`unassignedTickets` ← `unassigned_tickets`, `highPriorityOpen` ←
`urgent_high_tickets`, `needsReviewTickets` ← `needs_review_tickets`,
`statusCounts` ← `status_counts`, `pendingApprovals` ←
`pending_reply_approvals`. `categoryDistribution` in the frontend is active-only
while the API breakdown is all tickets; `prioritySummary`, `receivedTrend`,
`recentTickets` and `recentActivity` still have no API equivalent. Keep
`needs_review_tickets` separate from `pending_reply_approvals`.

### Behaviour differences

1. Responses are snake_case and paginated as `{items, pagination}`; the adapter
   must reshape to camelCase and `TicketPage`.
2. Mutations commit immediately and return the whole updated ticket; the demo
   service also mutates shared state and notifies subscribers.
3. Assignment requires an explicit value: `{ "agent_id": null }` to unassign.
   Omission is a 422, not an unassignment.
4. Category changes re-route the team but preserve the assigned agent; the
   current frontend behaves the same way.
5. `actor_id` is accepted but not authenticated; do not display it as a verified
   user.
6. Timestamps parse the same as fixtures (`Z` suffix).
7. Errors arrive as `{error:{code,message,details?}}`; map `code` to
   `TicketServiceError` and keep existing loading/empty/error UI states.
8. Notes are a separate resource from replies and from activity summaries.
9. Activity history is append-only and server-derived; no client-side
   summarization is needed for privacy.
10. Replies are now a separate persisted resource. The demo service's
    `saveReplyDraft(ticketId, ...)` upsert splits into create (POST) and edit
    (PATCH); an adapter must remember the active reply ID per ticket.
11. The API rejects empty reply bodies, blank reviewer comments, editing a sent
    reply, and repeated or stale review actions; map `409` codes to the existing
    `TicketServiceError` UI.

## 13. Persisted but not exposed

- `reply_revisions` and `reply_reviews` are readable through
  `GET /replies/{id}` but have no update/delete API (intentionally append-only).
- The one-active-reply rule is enforced by a PostgreSQL partial unique index;
  there is no endpoint to delete or archive a reply.
- `ticket_notes`: readable/creatable only through the endpoints above; no edit
  or delete.

## 14. Planned for later phases (not implemented)

| Operation | Proposed endpoint |
| --- | --- |
| `listAllReplies()` across tickets (non-pending) | `GET /api/v1/replies` with filters |
| Sanitized activity facets | `GET /api/v1/activities/facets` |
| Analytics | `GET /api/v1/analytics` |
| Ticket team filter | `GET /api/v1/tickets?assigned_team=...` |
| Note edit/delete | later, if the domain requires it |
| Account password reset by an administrator | `POST /api/v1/accounts/{id}/reset-password` |
| Account hard delete | not planned: deactivation preserves attribution |

These are proposals only. They are not registered, not in OpenAPI, and not
implemented. Approval and demo sending must remain separate server operations,
and sending must require a current approved version plus a recorded reviewer.
