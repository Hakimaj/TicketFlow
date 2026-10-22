# TicketFlow API contract — `/api/v1` (Phase 6)

Status: **implemented and tested** for the 14 operations below. Everything
under “Planned” is not implemented and must not be treated as working.

Base URL in local development: `http://127.0.0.1:8000/api/v1`.
Generated reference: `http://127.0.0.1:8000/docs` and
`http://127.0.0.1:8000/api/v1/openapi.json`.

The frontend still uses its in-memory demo service; no page calls this API yet.
There is **no authentication**: write endpoints are development-only and must
not be exposed publicly. `actor_id` values are unverified caller-supplied
metadata, not authenticated identities.

## 1. Conventions

- **Transport:** JSON over HTTP.
- **Versioning:** every application route lives under `/api/v1`.
- **Identifiers:** tickets use public IDs (`TF-1051`, case-insensitive in the
  path). Agents use `AG-xx`. Activities use `ACT-xxxx`. Replies (when exposed)
  use `REP-xxx`. Notes and requester IDs are opaque UUID strings.
- **Timestamps:** ISO 8601 UTC with milliseconds and `Z`, e.g.
  `2026-10-21T12:00:00.000Z`. Database columns are `timestamptz`; naive request
  values are treated as UTC.
- **Field naming:** responses use `snake_case`; frontend mapping is in §11.
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
| reply `state` (not exposed yet) | `draft`, `pending_approval`, `approved`, `changes_requested`, `sent` |

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

`details` is present for validation failures only.

| HTTP | `code` | When |
| --- | --- | --- |
| 404 | `ticket_not_found` | Unknown public ticket ID |
| 404 | `not_found` | Unknown route |
| 405 | `method_not_allowed` | Unsupported method |
| 422 | `validation_error` | Body/query/path validation failed |
| 422 | `invalid_query` | Conflicting query parameters or reversed date range |
| 422 | `invalid_actor` | `actor_id` does not name an existing agent |
| 422 | `actor_unavailable` | No demo actor configured and no `actor_id` supplied |
| 422 | `invalid_agent` | Assignment references a nonexistent agent |
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

## 6. Ticket mutations

Four focused endpoints, no generic field update. Every request body accepts an
optional `actor_id` (development-only, see §10). Every successful mutation
returns the updated ticket in the detail shape above.

### 6.1 `PATCH /api/v1/tickets/{ticket_id}/status`

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/tickets/TF-1051/status \
  -H 'Content-Type: application/json' \
  -d '{"status": "pending", "actor_id": "AG-02"}'
```

Rules:

- Values are the six statuses above; anything else → `422 validation_error`.
- `updated_at` advances.
- `resolved`/`closed` clear `due_at`.
- Audit action: `resolved` for resolved, `review_flagged` for needs review,
  otherwise `status_changed`. Detail: `Status changed from Open to Pending.`
- Repeating the current status is a no-op: response is the current ticket, no
  audit event, `updated_at` unchanged.

### 6.2 `PATCH /api/v1/tickets/{ticket_id}/priority`

```json
{ "priority": "urgent" }
```

- Active (`new`/`open`/`pending`) urgent/high tickets receive an 8-hour target
  from now; other priorities clear `due_at`.
- Terminal tickets keep their existing `due_at`.
- Audit action `priority_changed`, detail
  `Priority changed from Low to Urgent.`
- Repeating the current priority is a no-op.

### 6.3 `PATCH /api/v1/tickets/{ticket_id}/category`

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

### 6.4 `PATCH /api/v1/tickets/{ticket_id}/assignment`

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

### 6.5 Transaction and no-op policy

- Ticket change + required activity event commit in one database transaction.
  If either fails, both are rolled back; no partial audit state is possible.
- Successful responses are returned only after commit.
- No-op requests create no audit entry and do not touch `updated_at`.
- There is no optimistic concurrency control in Phase 6 (no `If-Match`). The
  single-operator demo model does not justify it; concurrent-write semantics
  remain an explicit later concern.

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

Notes are never returned by reply endpoints (none exist yet) or activity
summaries. There is no edit/delete API.

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
never contains customer messages, customer email addresses, reply drafts or
note bodies. Note events expose only `note_id`.

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

Ticket-only aggregates computed with SQL:

| Field | Definition |
| --- | --- |
| `total_tickets` | All persisted tickets |
| `active_tickets` | Status `new`, `open` or `pending` |
| `unassigned_tickets` | Active tickets with no agent |
| `urgent_high_tickets` | Active tickets with priority urgent/high |
| `needs_review_tickets` | All tickets with ticket-level status `needs_review` |
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
  "status_counts": [{ "status": "new", "count": 4 }],
  "category_counts": [{ "category": "billing", "count": 6 }],
  "priority_counts": [{ "priority": "urgent", "count": 4 }]
}
```

Reply-approval counts, SLA/CSAT, revenue and trends are deliberately **not**
included: the reply workflow is not exposed and no such history exists.

## 10. Actor identity (important limitation)

No authentication exists. `actor_id` on mutations/notes selects which seeded
agent is recorded in the audit event and can be any existing agent; it is not
proof of who performed the action. Omitting it records the seeded demo agent
`AG-01`. Activity rows are append-only through the API, but this is not a
tamper-proof audit system. Authentication and server-derived identity are a
later phase; until then, run the write API only on a local development
interface.

## 11. Frontend ↔ API mapping

### Ticket fields

Unchanged from Phase 5: `id`, `subject`, `channel`, `category`, `priority`,
`status`, `assigned_team`, `assigned_agent_id`, `assigned_agent_name`,
`created_at`, `updated_at`; detail adds `description`, `requester`,
`due_at`, `suggested_category`, `suggested_priority`, `review_note`. The list
still omits requester email/description/review note.

### Operations ↔ `TicketService`

| Frontend method | API |
| --- | --- |
| `listTickets(query)` | `GET /tickets` (see pagination mapping below) |
| `getTicket(id)` | `GET /tickets/{id}` |
| `updateStatus(id, status)` | `PATCH /tickets/{id}/status` |
| `updatePriority(id, priority)` | `PATCH /tickets/{id}/priority` |
| `updateCategory(id, category)` | `PATCH /tickets/{id}/category` |
| `assignTicket(id, agentId)` | `PATCH /tickets/{id}/assignment` with `{"agent_id": agentId}` (`null` unassigns) |
| `addInternalNote(id, note)` | `POST /tickets/{id}/notes` (returns a note, not a `TicketActivity`) |
| `getTicketActivities(id)` | `GET /tickets/{id}/activities` |
| `listActivityLog(query)` | `GET /activities` |
| `listAgents()` / `getAgent(id)` | `GET /agents`; fetch once and look up by ID |
| `getDashboardStats()` | `GET /dashboard/summary` (ticket metrics only) |
| `getAdjacentTicketIds`, replies, approvals, analytics, facets | not implemented |

### Type mapping

**`ActivityResponse` → frontend `TicketActivity`**

| API | Frontend |
| --- | --- |
| `id` | `id` |
| `ticket_id` | `ticketId` |
| `reply_id` | `replyId` |
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

**Dashboard mapping:** `openTickets` ← `active_tickets`,
`unassignedTickets` ← `unassigned_tickets`, `highPriorityOpen` ←
`urgent_high_tickets`, `needsReviewTickets` ← `needs_review_tickets`,
`statusCounts` ← `status_counts`. `categoryDistribution` in the frontend is
active-only while the API breakdown is all tickets; the `prioritySummary`,
`receivedTrend`, `recentTickets`, `recentActivity` and `pendingApprovals`
fields have no API equivalent yet.

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

## 12. Persisted but not exposed

- `customer_replies`: full Phase 3 workflow metadata (state, version, submitted/
  reviewed/sent timestamps, reviewer, internal feedback). No reply routes exist.
- Reply-related activity rows seeded from the frontend remain readable through
  the activity endpoints for compatibility, but no reply workflow writes them.
- `ticket_notes`: readable/creatable only through the endpoints above; no edit
  or delete.

## 13. Planned for later phases (not implemented)

| Operation | Proposed endpoint |
| --- | --- |
| Replies for a ticket | `GET /api/v1/tickets/{id}/replies` |
| Draft / submit / approve / request changes / demo send | reply workflow routes |
| Approvals queue | `GET /api/v1/replies?state=pending_approval` |
| Sanitized activity facets | `GET /api/v1/activities/facets` |
| Analytics | `GET /api/v1/analytics` |
| Ticket team filter | `GET /api/v1/tickets?assigned_team=...` |
| Note edit/delete | later, if the domain requires it |
| Optimistic concurrency | version/`If-Match` on mutations |
| Authentication / authorization | session or token scheme |

These are proposals only. They are not registered, not in OpenAPI, and not
implemented. Approval and demo sending must remain separate server operations,
and sending must require a current approved version plus a recorded reviewer.
