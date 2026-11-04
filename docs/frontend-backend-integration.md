# Frontend → backend integration notes

Status: **Phase 10 — API mode is the default and verified against the real
backend.** Every operational page uses the persistent API through
`HttpTicketService`, with authenticated accounts, server-side role enforcement
and a complete reply workflow (drafts, immutable revisions, human approval /
change requests, approval queue, explicit demo send). The in-memory
`DemoTicketService` remains available only with an explicit `VITE_DATA_MODE=demo`
and is visibly labelled in the shell. Phase 10 added staff ticket intake
(`/tickets/new`), administrator account management (`/accounts`) and stale-edit
conflict handling. This document records the frontend contract, the adapter
behavior actually shipped, and the remaining gaps (windowed analytics
endpoints, activity facets).

See [`backend-api-contract.md`](./backend-api-contract.md) for the HTTP
contract, including `/auth/*`, the permission matrix and error codes.

## 1. Current architecture

```
UI components / feature hooks
        │  typed calls only
        ▼
TicketService (src/services/ticketService.ts)
        │
        ├── HttpTicketService ── apiClient ── /api/v1 (API mode, default)
        │        ▲ access token in memory, refresh cookie
        │
        └── DemoTicketService ── in-memory fixtures (VITE_DATA_MODE=demo)
```

- Components never import fixture arrays. `src/services/index.ts` exports the
  single `ticketService` instance typed as `TicketService`, selected by
  `src/config/app-mode.ts`.
- `apiClient.ts` owns the base URL, in-memory access token, single shared
  refresh-and-retry on `401`, and error-envelope mapping. Cookie endpoints
  (`/auth/login`, `/auth/refresh`, `/auth/logout`) always send credentials.
- `AuthProvider` restores the session once on startup (rotating the HttpOnly
  refresh cookie), exposes the verified account and permissions, and returns the
  user to `/login` when refresh fails. StrictMode double-mounts share one
  restore so a rotated token is never presented twice.
- `DemoTicketService` simulates ~280 ms latency and loses data on reload; it is
  used only in explicit demo mode.
- Mutations publish through `TicketService.subscribe`; the app shell, dashboard,
  ticket workspace, approvals queue, analytics and activity log refetch.
- `src/lib/preferences.ts` and `PreferencesProvider` store only two harmless
  presentation values in `localStorage` (`ticketflow.preferences.v1`): table
  density and default start page. No ticket, reply, note, customer or auth data
  is stored there.

## 2. Domain models

| Model | File | Key fields |
| --- | --- | --- |
| `Ticket` | `src/types/ticket.ts` | `id`, `subject`, `description`, requester fields, `channel`, `category`, `priority`, `status`, `assignedTeam`, `assignedAgentId`, timestamps, optional triage suggestion/review fields |
| `Agent` | `src/types/ticket.ts` | `id`, `name`, `role` (`admin`/`supervisor`/`agent`), nullable `team`, `email`, `isDemoUser` |
| `TicketActivity` | `src/types/ticket.ts` | `id`, `ticketId`, optional `replyId`, `actorName`, `actorType`, `action`, nullable `detail`, `createdAt`, `isInternalNote` |
| `CustomerReply` | `src/types/reply.ts` | `id`, `ticketId`, author fields, `body`, `state`, `version`, created/updated/submitted/reviewed/sent timestamps, reviewer fields/feedback, sender name |
| `AnalyticsStats` | `src/types/analytics.ts` | Current-state distributions plus windowed creation/sent counts and a daily volume trend |
| `ActivityLogEntry` | `src/types/activity.ts` | Sanitized projection: `id`, `ticketId`, `replyId`, actor, action, `summary`, `createdAt` |

`TicketActivity.detail` is the ticket-workspace record and may contain internal
content. `ActivityLogEntry` is deliberately separate: the service replaces note
bodies, reply drafts and reviewer comments with safe operational summaries.

On the backend, note text is now a dedicated `ticket_notes` record, and
`ticket_activities.detail` never contains it: note events carry a fixed summary
plus `note_id`. Any future adapter must fetch note text from the notes endpoint
rather than expecting it in the activity timeline.

## 3. Service operations (existing contract)

### Ticket queues and triage

| Method | Behaviour |
| --- | --- |
| `listTickets(query)` | Search/filter/sort/paginate; returns `TicketPage` |
| `getTicket(id)` | One ticket or `null` |
| `getAdjacentTicketIds(id)` | Previous/next IDs for triage navigation |
| `listAgents()` / `getAgent(id)` | Roster and assignee lookup |
| `updateStatus`, `updatePriority`, `updateCategory`, `assignTicket` | Triage mutations; append audit events; publish |
| `addInternalNote(ticketId, note, agent)` | Internal-only note + audit event; never customer-visible |

### Reply workflow

| Method | Behaviour |
| --- | --- |
| `getReplies(ticketId)`, `getReply(replyId)` | Reply lookup |
| `listPendingReplies()`, `listAllReplies()` | Approval queue data (reply + parent ticket) |
| `saveReplyDraft(ticketId, body, author)` | Creates/updates the one active non-sent reply |
| `submitReplyForApproval(replyId, author)` | `draft`/`changes_requested` → `pending_approval` |
| `approveReply(replyId, reviewer)` | `pending_approval` → `approved`; does **not** send |
| `requestReplyChanges(replyId, feedback, reviewer)` | Requires non-empty feedback; → `changes_requested` |
| `markReplySent(replyId, actor)` | `approved` → `sent`; demo-only, records send metadata |

### Derived views and audit

| Method | Behaviour |
| --- | --- |
| `getDashboardStats(trendDays?)` | Overview metrics and recent data |
| `getAnalytics(range)` | Current-state distributions + 7/30/all windowed counts and trend |
| `getTicketActivities(ticketId)` | Chronological workspace timeline (may contain internal content) |
| `listActivity(limit?)` | Recent raw activity for the dashboard/workspace |
| `listActivityLog(query)` | Sanitized, searchable, action/actor/range filtered, sorted, paginated audit log |
| `getActivityLogFacets()` | Actors and action types present, with counts |
| `subscribe(listener)` | Mutation notification; returns unsubscribe |

### Backend availability (through Phase 8, as implemented by the adapter)

| Frontend method | Backend status | Endpoint(s) |
| --- | --- | --- |
| `listTickets`, `getTicket` | implemented | `GET /tickets`, `GET /tickets/{id}` |
| `updateStatus`, `updatePriority`, `updateCategory`, `assignTicket` | implemented (persistent + audited) | `PATCH /tickets/{id}/{status,priority,category,assignment}` |
| `listAgents` | implemented | `GET /agents` (roster; look up by ID) |
| `addInternalNote` | implemented, different return type | `POST /tickets/{id}/notes` returns a note, not a `TicketActivity` |
| `getTicketActivities` | implemented | `GET /tickets/{id}/activities` |
| `listActivityLog` | implemented via server filters + client-side actor/range narrowing | `GET /activities` |
| `getActivityLogFacets` | composed by walking paged results | `GET /activities?page_size=100` |
| `getAnalytics` | composed from dashboard summary + paged active tickets/replies | `GET /dashboard/summary?trend_days=N`, `GET /tickets`, `GET /replies` |
| `getDashboardStats` | dashboard summary + paged recent lists | `GET /dashboard/summary?trend_days=N`, `GET /tickets`, `GET /activities` |
| `getAdjacentTicketIds` | composed from the ordered queue | `GET /tickets?sort_by=created_at&sort_dir=asc` |
| `getReplies` | implemented | `GET /tickets/{id}/replies` (paginated) |
| `getReply` | implemented, richer | `GET /replies/{id}` adds `revisions[]` and `reviews[]` |
| `saveReplyDraft` | implemented as create + edit | `POST /tickets/{id}/replies`, `PATCH /replies/{id}` |
| `submitReplyForApproval` | implemented | `POST /replies/{id}/submit` |
| `approveReply` | implemented, version required | `POST /replies/{id}/approve` |
| `requestReplyChanges` | implemented, version required | `POST /replies/{id}/request-changes` |
| `markReplySent` | implemented, returns a wrapper | `POST /replies/{id}/send-demo` → `{reply, delivery, notice}` |
| `listPendingReplies` | implemented with search/filter/pagination | `GET /replies/approvals` |
| `listAllReplies` | not implemented as one call | combine per-ticket lists with the queue |
| `getAnalytics` | not implemented | — |
| `getActivityLogFacets` | not implemented | — |

## 4. Source of truth and derived rules

- **Tickets, replies and activity events** live in the service instance. They are
  cloned from fixtures on construction, then mutated only through service methods.
- **Analytics** is derived per request from current tickets/replies. It never
  reads from a separate analytics fixture. Window semantics:
  - ticket creation metrics and volume-created counts use `Ticket.createdAt`;
  - reply creation counts use `CustomerReply.createdAt`;
  - demo-send counts use `CustomerReply.sentAt`;
  - resolved/closed counts use `Ticket.updatedAt` as a **proxy**, because the
    dataset has no separate resolution event timestamp;
  - status, priority, category, agent workload and reply-state charts are
    **current state**, not historical snapshots.
- **Activity log** derives from the same `TicketActivity` records used by ticket
  timelines, not a second log system. Reply events carry `replyId`, and the
  backend additionally stores `reply_version` for the exact revision. Search
  matches ticket ID, actor name, action label and the sanitized summary;
  content-bearing detail is never projected into this view.
- No SLA, resolution-duration, CSAT, revenue or fabricated trend data exists.

## 5. State-transition rules the backend must preserve

Reply lifecycle:

```
draft ──submit──▶ pending_approval ──approve──▶ approved ──demo send──▶ sent
  ▲                      │
  │                      └──request changes──▶ changes_requested
  └──────────── edit/resubmit ─────────────────────┘
```

The backend implements these same transitions with additional guarantees:

- Only one active (non-`sent`) reply per ticket (partial unique index); a new
  draft starts after a reply is sent.
- Every distinct body is an immutable `reply_revisions` row with a unique
  `(reply_id, version)`. Saving identical text is a true no-op (no revision, no
  event, no timestamp change); any change increments `version`.
- Editing while `pending_approval`, `approved` or `changes_requested` returns the
  reply to `draft` and clears current submission/approval metadata. Historical
  review decisions remain append-only in `reply_reviews`.
- Reviews name the exact submitted `version`. Approval records
  `approved_version`; a stale version is `409 reply_version_conflict`.
- `requestReplyChanges` rejects empty/whitespace feedback. Feedback is internal
  and retained in the review history even after the current feedback is cleared.
  General activity summaries never include it.
- `markReplySent` requires current state `approved`, `approved_version == version`,
  an approved review decision for that exact revision, matching revision text, and
  no prior send. The same gate is enforced by service code, PostgreSQL CHECK
  constraints and row locks. Direct service calls cannot bypass it.
- Approval never sends. Sending is explicit, records actor/time, writes a
  `replied_sent` event, and moves `new`/`open` tickets to `pending`.
  Resolved/closed tickets keep their status.
- Sent replies are immutable; editing returns `409 reply_immutable` and the UI
  must start a new reply.
- Invalid transitions throw `TicketServiceError` in the demo service; the API
  uses `409` codes that an adapter should map to the same error type.

Ticket statuses: `new`, `open`, `pending`, `needs_review`, `resolved`, `closed`.
“Active workload” is defined as `new` + `open` + `pending`; ticket-level
`needs_review` is counted separately from reply approval.

## 6. Backend responsibilities

Implemented through Phase 8: liveness/readiness, ticket list/detail, persistent
triage mutations, internal notes, ticket and global activity history, agent
lookup, ticket + reply dashboard aggregates, the complete persistent reply
workflow, authenticated accounts, refresh rotation, role/permission enforcement
and trusted attribution. Still proposed: windowed analytics endpoints, activity
facets and adjacent-ticket navigation.

1. **Session/identity — implemented.** Accounts live in PostgreSQL with
   Argon2id hashes; access tokens are short-lived and held in memory, refresh
   tokens rotate in an HttpOnly cookie, and the server reloads the account
   (including role) on every request. Protected routes call `/auth/me`-derived
   identity; `actor_id`/`reviewer_id` body fields are ignored and self-approval
   is rejected for every role.
2. **Ticket read/write** — implemented for list/detail and four triage
   mutations. Server mutation rules: category re-routes the team but preserves
   the agent; assignment requires explicit `null` to unassign; unchanged values
   are no-ops with no audit event; ticket change + audit commit atomically.
3. **Reply workflow** — implemented transactionally: create/edit draft (with
   immutable revisions), submit, approve, request changes and demo send. Each
   transition locks the reply row and commits its audit event in the same
   transaction.
4. **Approval gate** — implemented server-side: send requires `approved` state,
   the approved version equal to the current revision, a stored approval
   decision for that revision and matching revision text. Mirrored by database
   CHECK constraints; direct service calls are rejected identically.
5. **Audit events** — implemented append-only writes with stable public IDs,
   actor snapshot, timestamp and ticket/reply/revision/note linkage. The general
   activity projection is privacy-safe; note bodies stay in `ticket_notes` and
   reviewer comments stay in `reply_reviews` / reply detail only.
6. **Analytics** — the dashboard summary now includes reply-state counts
   (`pending_reply_approvals`, `draft_replies`,
   `approved_replies_awaiting_send`, `sent_replies_demo`). Windowed analytics,
   trends, CSAT/SLA and real delivery metrics remain unimplemented.
7. **Preferences** — remain browser-local; no server settings API.

### 6.1 Differences an adapter must handle

- snake_case ↔ camelCase; `{items, pagination}` → `TicketPage`.
- `updateStatus` etc. return the updated ticket after commit; call subscribers
  after the response resolves.
- `assignTicket(id, null)` must send `{"agent_id": null}`; omission is rejected.
- Category changes preserve `assignedAgentId`; team is derived from category.
- Errors use `{error:{code,message,details?}}`; map to `TicketServiceError`.
- `addInternalNote` returns a note (`id`, `ticket_id`, `content`, `author`,
  timestamps) rather than the `TicketActivity` the UI currently expects. The
  adapter can return the linked activity or refetch the activity list.
- Activity `summary` maps to `TicketActivity.detail`; note bodies must be read
  from the notes endpoint, not from activity data.
- `listActivityLog` has `start`/`end` instead of `range`, `actor_id`/`search`
  instead of an actor-name filter, and no facet endpoint.
- `getDashboardStats`: `active_tickets`/`unassigned_tickets`/
  `urgent_high_tickets`/`needs_review_tickets`/`status_counts` map to existing
  fields, and `pendingApprovals` now maps to `pending_reply_approvals`. Keep
  ticket-level `needs_review_tickets` separate from reply approvals. API
  category/priority breakdowns cover all tickets, while the UI computes
  category counts over active tickets — the adapter derives
  `categoryDistribution` (and analytics equivalents) from paged
  `?status=new&status=open&status=pending` list calls, not from
  `category_counts`. `receivedTrend`/`prioritySummary` come from
  `/dashboard/summary?trend_days=N`; `recentTickets`/`recentActivity` come
  from paged `/tickets` and `/activities` calls. Do not silently substitute
  differently-scoped numbers.
- `saveReplyDraft` is an upsert in the demo service but two operations over HTTP:
  create the ticket's draft (`POST`, fails `409 reply_already_exists`) or edit an
  existing one (`PATCH`). The adapter must know whether the ticket already has
  an active reply.
- `getReplies` is paginated (`{items, pagination}`) and newest-first by
  `created_at`; the demo method returns an unpaged array.
- `getReply` returns `revisions[]` (immutable bodies with version IDs) and
  `reviews[]` (append-only decisions with internal comments) in addition to the
  `CustomerReply` fields. The demo model has no equivalent arrays.
- `reviewerFeedback` is the *current* feedback only. After a revision it is
  cleared; earlier comments remain in `reviews[]`. Reviewer comments must never
  be rendered as customer-facing text.
- `markReplySent` returns `{reply, delivery: "demo_marked_sent", notice}` rather
  than a bare reply. Map `reply` and surface the demo notice; do not treat
  `delivery` as proof of customer delivery.
- The approval queue returns a limited `preview` (≤180 chars) and no full
  `body`; fetch `GET /replies/{id}` for the review pane. It supports `page`,
  `page_size`, `search`, repeatable `category`/`priority`, and `sort_dir`
  (submission time), which the demo `listPendingReplies()` does not.
- A review/approval request must include the exact `version`. On a stale version
  the API returns `409 reply_version_conflict`; on a non-pending reply,
  `409 reply_not_pending`. Map both to `TicketServiceError` and refetch.

Implemented adapter: `src/services/httpTicketService.ts` implements
`TicketService` over these endpoints and is selected by default
(`VITE_DATA_MODE` unset or `api`). Only `VITE_DATA_MODE=demo` selects the
fixtures, and the shell then shows a persistent demo banner. The API base URL
defaults to `http://127.0.0.1:8000/api/v1` in development and `/api/v1` on the
same origin in production; `VITE_API_BASE_URL` overrides it. Method signatures
and the error type are unchanged. Behavior notes from the implementation:

- `getAdjacentTicketIds` walks the paged `/tickets?sort_by=created_at&sort_dir=asc`
  queue because the API has no neighbors endpoint.
- `listTickets` with `assignmentScope: "mine"` resolves the signed-in agent via
  `GET /auth/me` (`agent_id`); without a linked agent account the filter fails.
- `addInternalNote` posts to `/tickets/{id}/notes` and derives a
  `TicketActivity` (`note_added`) from the created note. `getTicketActivities`
  joins note bodies back from `GET /tickets/{id}/notes` because audit summaries
  deliberately never contain note text, so notes remain readable after reload
  without leaking into the general activity log.
- `saveReplyDraft` implements the two-step upsert: `POST`, then on
  `409 reply_already_exists` it looks up the active (non-sent) reply and edits
  it with `PATCH`.
- `approveReply`/`requestReplyChanges` fetch the current reply first to send
  the exact `version`; stale versions surface `409 reply_version_conflict`.
- `reply-state` mutations notify `subscribe` listeners, keeping the same
  in-session reactivity as the demo service.
- The API filters activity by actor ID, not actor name; `listActivityLog`
  therefore applies exact actor-name narrowing (and combined
  search + actor queries) client-side after paging through server-filtered
  results.

## 7. Expected UI behaviour during integration

| State | Existing pattern |
| --- | --- |
| Loading | `ListSkeleton` / `PanelSkeleton`; first load shows skeletons; refetches keep existing data visible |
| Success | Data rendered; mutations show inline feedback/toasts and publish via `subscribe` |
| Validation | Domain rules throw `TicketServiceError`; forms show inline errors (e.g. empty reply, missing reviewer feedback) |
| Empty | `EmptyState` with a clear next action; activity filters offer “Clear filters” |
| Error | `ErrorState` with retry; stale data remains visible where practical |
| Not found | Ticket detail shows a not-found state with return navigation |

Network failures map to the same `Error` shapes consumed by these states. Pages
never substitute fixture data on a failed request; API mode shows an error with
a retry action (`ApiClientError.message` carries the server or mapped message).
Avoid optimistic state that contradicts the service (especially for
approval/send).

## 8. Current simulated/demo-only functionality

- API mode (the default) reads and writes persistent records; a failed request
  shows an error state and never falls back to fixtures. Demo mode requires
  `VITE_DATA_MODE=demo` and displays a visible banner; its data resets on
  reload.
- Sending is labelled “(Demo)”; no email, chat, Telegram or other delivery exists
  in either the frontend or the backend. The backend `send-demo` endpoint records
  only a simulated application action and explicitly returns
  `delivery: "demo_marked_sent"` with a no-delivery notice.
- Each signed-in account performs actions under its own identity. The backend
  rejects self-approval for every role, and reply approval never sends.
- Analytics and activity-log figures are composed in the browser from persisted
  API data (paged list/dashboard calls); there is no dedicated analytics or
  activity-facet endpoint yet.
- “New Ticket” is a preview dialog; intake is not implemented.
- Browser preferences are local presentation state only.

## 9. Authentication flow (implemented)

```
/login → POST /auth/login ──► access token (memory) + refresh cookie (HttpOnly)
                              │
app start → POST /auth/refresh (single-flight) ──► session restored or /login
                              │
401 on any request → one shared refresh → retry once; failure clears the session
```

- The access token is never written to `localStorage` or `sessionStorage`.
- `/login` returns the user to the page that required the session.
- Routes are guarded; `/approvals` additionally requires `replies:review`, and
  navigation hides destinations the account cannot use. The server re-checks
  every endpoint.
- Signing out calls `/auth/logout`, revokes the session server-side and clears
  the local token. After logout, protected API calls return `401`.
- Demo mode (`VITE_DATA_MODE=demo`) skips the login flow entirely and uses a
  clearly labelled local demonstration account.
- Browser verification: `e2e/app.spec.ts` covers demo mode;
  `e2e-api/workflow.spec.ts` (`npm run test:e2e:api`) runs the complete
  two-account workflow against a real backend and a disposable `*_e2e`
  database.
