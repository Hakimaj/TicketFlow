# Frontend → backend integration notes

Status: **Phase 4 frontend only.** This document describes the code that exists
today and the contract a future backend must satisfy. It does **not** describe
working endpoints, credentials, or server behaviour. Any API operations listed
under “Proposed backend operations” are proposals, not existing routes.

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

## 6. Proposed backend operations (not implemented)

A future HTTP-backed implementation should satisfy the same `TicketService`
methods so feature code does not change. Proposed responsibilities:

1. **Session/identity** — replace the hard-coded `DEMO_USER` with an
   authenticated agent/session; enforce role permissions server-side.
2. **Ticket read/write** — list with server-side search/filter/sort/pagination;
   fetch one; triage mutations with authorization and concurrency handling.
3. **Reply workflow** — transactional draft/save/submit/approve/request-changes/
   send operations. Approval and send must be separate server operations.
4. **Approval gate** — server must reject send unless the exact approved version
   is current and a reviewer is recorded. The client guard is not security.
5. **Audit events** — append server-side, immutable, with stable IDs, actor,
   timestamp, ticket/reply linkage; expose a sanitized list projection so
   internal content is not sent to the general log UI.
6. **Analytics** — return derived aggregates with explicit “as of” time and
   window semantics; or expose source data and keep derivations in shared
   selectors. Do not add SLA/CSAT fields unless the underlying records support
   them.
7. **Preferences** — remain browser-local unless a future user-settings API is
   explicitly added. Do not store customer data here.

Suggested adapter shape (proposal): create `HttpTicketService implements
TicketService`, swap the exported instance in `src/services/index.ts`, and keep
the existing method signatures and error type. No endpoint names are specified
here because none exist.

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

- All data is in-memory; reload resets tickets, replies and activity.
- Sending is labelled “(Demo)”; no email, chat, Telegram or other delivery exists.
- One hard-coded demo identity (`AG-01`, supervisor) performs every action;
  self-approval is possible by design. There is no login, token or role check.
- Analytics/activity calculations run in the browser against demo records.
- “New Ticket” is a preview dialog; intake is not implemented.
- Browser preferences are local presentation state only.
