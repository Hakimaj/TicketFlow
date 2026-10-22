# Frontend → backend integration notes

Status: **Phase 6 — frontend unchanged.** The frontend still runs entirely on
`DemoTicketService`; no page, hook or adapter has been switched to HTTP. The
backend now supports persisted ticket mutations, internal notes, activity
history, agent lookup and ticket dashboard aggregates in addition to the
Phase 5 reads (see [`backend-api-contract.md`](./backend-api-contract.md)).
This document remains the frontend-side contract and the plan for the later
integration. Reply workflow, analytics and authentication endpoints are still
proposals.

## 1. Current architecture

```
UI components / feature hooks
        │  typed calls only
        ▼
TicketService (src/services/ticketService.ts)
        │
        ▼
DemoTicketService (src/services/demoTicketService.ts)
        │
        ▼
In-memory fixtures (src/data/*.ts), cloned per service instance
```

- Components never import fixture arrays. `src/services/index.ts` exports the
  single `ticketService` instance typed as `TicketService`.
- `apiClient.ts` is a reserved HTTP helper; it is **not** used by the demo
  service. No API base URL or credential is configured.
- `DemoTicketService` simulates ~280 ms latency so loading/error states are
  exercised. Data is lost on page reload.
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

### Backend availability (Phase 6)

| Frontend method | Backend status | Endpoint |
| --- | --- | --- |
| `listTickets`, `getTicket` | implemented | `GET /tickets`, `GET /tickets/{id}` |
| `updateStatus`, `updatePriority`, `updateCategory`, `assignTicket` | implemented (persistent + audited) | `PATCH /tickets/{id}/{status,priority,category,assignment}` |
| `listAgents` | implemented | `GET /agents` (roster; look up by ID) |
| `addInternalNote` | implemented, different return type | `POST /tickets/{id}/notes` returns a note, not a `TicketActivity` |
| `getTicketActivities` | implemented | `GET /tickets/{id}/activities` |
| `listActivityLog` | implemented with date bounds instead of `range` | `GET /activities` |
| `getDashboardStats` | partial | `GET /dashboard/summary` (ticket metrics only) |
| `getAdjacentTicketIds` | not implemented | — |
| `getReplies`, reply workflow, `listPendingReplies`, `listAllReplies` | not implemented | — |
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
  timelines, not a second log system. Reply events recorded from Phase 3 onward
  carry `replyId`. Search matches ticket ID, actor name, action label and the
  sanitized summary; content-bearing detail is never projected into this view.
- No SLA, resolution-duration, CSAT, revenue or fabricated trend data exists.

## 5. State-transition rules the backend must preserve

Reply lifecycle:

```
draft ──submit──▶ pending_approval ──approve──▶ approved ──demo send──▶ sent
  ▲                      │
  │                      └──request changes──▶ changes_requested
  └──────────── edit/resubmit ─────────────────────┘
```

- Only one active (non-`sent`) reply per ticket; a new draft starts after a reply
  is sent.
- Saving identical text preserves state/approval. Editing content while
  `pending_approval`, `approved` or `changes_requested` increments `version`,
  returns the reply to `draft`, clears reviewer fields, and requires resubmission.
- `requestReplyChanges` rejects empty feedback. Feedback is internal and retained
  in the audit event even after it is cleared from the reply.
- `markReplySent` requires current state `approved` **and** a recorded reviewer.
  Direct service calls cannot bypass this gate.
- Approval never sends. Sending is explicit, records actor/time, writes a
  `replied_sent` event, and moves `new`/`open` tickets to `pending`.
- Sent replies are immutable; editing creates a new reply record.
- Invalid transitions throw `TicketServiceError`.

Ticket statuses: `new`, `open`, `pending`, `needs_review`, `resolved`, `closed`.
“Active workload” is defined as `new` + `open` + `pending`; ticket-level
`needs_review` is counted separately from reply approval.

## 6. Backend responsibilities for the later integration

Implemented in Phase 6: liveness/readiness, ticket list/detail, persistent
triage mutations, internal notes, ticket and global activity history, agent
lookup and ticket dashboard aggregates. Still proposed: reply workflow,
analytics, identity, facets, adjacent navigation and concurrency.

1. **Session/identity** — replace the hard-coded `DEMO_USER` with an
   authenticated agent/session; enforce role permissions server-side. Until
   then, backend `actor_id` is unverified development metadata.
2. **Ticket read/write** — implemented for list/detail and four triage
   mutations. Server mutation rules: category re-routes the team but preserves
   the agent; assignment requires explicit `null` to unassign; unchanged values
   are no-ops with no audit event; ticket change + audit commit atomically.
3. **Reply workflow** — still proposed: transactional draft/save/submit/approve/
   request-changes/send operations. Approval and send must remain separate
   server operations.
4. **Approval gate** — proposed; the server must reject send unless the exact
   approved version is current and a reviewer is recorded.
5. **Audit events** — implemented append-only writes with stable public IDs,
   actor snapshot, timestamp and ticket/reply/note linkage. The general activity
   projection is privacy-safe; note bodies stay in `ticket_notes`.
6. **Analytics** — ticket dashboard summary is implemented; windowed analytics,
   trends and reply-state metrics are not. Do not add SLA/CSAT fields unless the
   underlying records support them.
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
  fields. API category/priority breakdowns cover all tickets, while the current
  UI computes category/priority over active tickets; `pendingApprovals`,
  `receivedTrend`, `recentTickets`, `recentActivity` and `prioritySummary` have
  no API equivalent yet. Do not silently substitute differently-scoped numbers.

Suggested adapter shape (proposal): create `HttpTicketService implements
TicketService`, swap the exported instance in `src/services/index.ts`, and keep
the existing method signatures and error type. Do not switch only part of the
app: mixed demo/API sources would show inconsistent records.

## 7. Expected UI behaviour during integration

| State | Existing pattern |
| --- | --- |
| Loading | `ListSkeleton` / `PanelSkeleton`; first load shows skeletons; refetches keep existing data visible |
| Success | Data rendered; mutations show inline feedback/toasts and publish via `subscribe` |
| Validation | Domain rules throw `TicketServiceError`; forms show inline errors (e.g. empty reply, missing reviewer feedback) |
| Empty | `EmptyState` with a clear next action; activity filters offer “Clear filters” |
| Error | `ErrorState` with retry; stale data remains visible where practical |
| Not found | Ticket detail shows a not-found state with return navigation |

Future network failures should map to the same `Error` shapes consumed by these
states. Avoid optimistic state that contradicts the service (especially for
approval/send).

## 8. Current simulated/demo-only functionality

- Frontend data remains in-memory; reload resets tickets, replies and activity.
  Backend data is persistent, but no frontend page reads it in this phase.
- Sending is labelled “(Demo)”; no email, chat, Telegram or other delivery exists
  in either the frontend or the backend (no reply workflow API exists yet).
- One hard-coded demo identity (`AG-01`, supervisor) performs every action;
  self-approval is possible by design. There is no login, token or role check.
- Analytics/activity calculations run in the browser against demo records.
- “New Ticket” is a preview dialog; intake is not implemented.
- Browser preferences are local presentation state only.
