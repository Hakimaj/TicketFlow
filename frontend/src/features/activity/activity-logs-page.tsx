import * as React from 'react'
import { Link } from 'react-router-dom'
import { FilterX, ScrollText } from 'lucide-react'
import { PageHeader } from '@/components/shared/page-header'
import { Pagination } from '@/components/shared/pagination'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/shared/states'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ACTIVITY_ACTION_LABELS } from '@/lib/activity-config'
import { formatDateTime } from '@/lib/format'
import type { ActivityAction, ActivityActorType } from '@/types/ticket'
import type { ActivityLogQuery, ActivityRange } from '@/types/activity'
import { useActivityLog, useActivityLogFacets } from './use-activity-log'

const PAGE_SIZE = 20

const ACTOR_TYPE_LABELS: Record<ActivityActorType, string> = {
  agent: 'Agent',
  automation: 'Automation',
  system: 'System',
}

const RANGE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'all', label: 'All time' },
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
]

function actionVariant(
  action: ActivityAction,
): 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'neutral' {
  switch (action) {
    case 'reply_approved':
    case 'resolved':
      return 'success'
    case 'reply_changes_requested':
    case 'escalated':
      return 'danger'
    case 'reply_submitted':
    case 'replied_draft':
    case 'review_flagged':
      return 'warning'
    case 'replied_sent':
      return 'primary'
    default:
      return 'neutral'
  }
}

export function ActivityLogsPage() {
  const [search, setSearch] = React.useState('')
  const [action, setAction] = React.useState<ActivityAction | 'all'>('all')
  const [actor, setActor] = React.useState('all')
  const [range, setRange] = React.useState<ActivityRange>('all')
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('desc')
  const [page, setPage] = React.useState(1)

  const facets = useActivityLogFacets()

  const query = React.useMemo<ActivityLogQuery>(
    () => ({
      search: search.trim() || null,
      actions: action === 'all' ? null : [action],
      actorName: actor === 'all' ? null : actor,
      range,
      sortDir,
      page,
      pageSize: PAGE_SIZE,
    }),
    [search, action, actor, range, sortDir, page],
  )

  const { result, loading, error, reload } = useActivityLog(query)

  const hasFilters =
    search.trim() !== '' ||
    action !== 'all' ||
    actor !== 'all' ||
    range !== 'all' ||
    sortDir !== 'desc'

  const clearFilters = () => {
    setSearch('')
    setAction('all')
    setActor('all')
    setRange('all')
    setSortDir('desc')
    setPage(1)
  }

  // Any filter/sort change starts from the first page.
  React.useEffect(() => {
    setPage(1)
  }, [search, action, actor, range, sortDir])

  const currentPage = result?.page ?? page

  return (
    <div className="space-y-5">
      <PageHeader
        title="Activity Logs"
        description="Sanitized audit trail for ticket and reply workflow events. Internal note bodies, reply drafts and reviewer feedback are not shown here."
      />

      <Card className="overflow-hidden">
        <CardHeader>
          <div>
            <CardTitle className="flex items-center gap-1.5">
              <ScrollText aria-hidden="true" className="size-4 text-subtle-foreground" />
              Audit events
            </CardTitle>
            <CardDescription>
              Sourced from the same activity records that power each ticket
              timeline. Search matches ticket ID, actor, action label or the
              safe summary.
            </CardDescription>
          </div>
          {result ? (
            <p aria-live="polite" className="shrink-0 text-xs text-muted-foreground">
              {result.total} {result.total === 1 ? 'event' : 'events'}
            </p>
          ) : null}
        </CardHeader>

        <CardContent className="space-y-3 pb-3">
          <div className="grid gap-2 lg:grid-cols-[minmax(0,1.5fr)_repeat(4,minmax(0,1fr))_auto]">
            <div>
              <Label htmlFor="activity-search" className="sr-only">
                Search activity
              </Label>
              <SearchInput
                id="activity-search"
                aria-label="Search activity by ticket, actor or action"
                placeholder="Search ticket ID, actor or action"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>

            <div>
              <Label htmlFor="activity-action" className="sr-only">
                Filter by action
              </Label>
              <Select
                value={action}
                onValueChange={(value) =>
                  setAction(value === 'all' ? 'all' : (value as ActivityAction))
                }
              >
                <SelectTrigger id="activity-action" className="w-full">
                  <SelectValue placeholder="All actions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All actions</SelectItem>
                  {(facets?.actions ?? []).map((entry) => (
                    <SelectItem key={entry.action} value={entry.action}>
                      {ACTIVITY_ACTION_LABELS[entry.action]} ({entry.count})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="activity-actor" className="sr-only">
                Filter by actor
              </Label>
              <Select value={actor} onValueChange={setActor}>
                <SelectTrigger id="activity-actor" className="w-full">
                  <SelectValue placeholder="All actors" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All actors</SelectItem>
                  {(facets?.actors ?? []).map((entry) => (
                    <SelectItem key={entry.name} value={entry.name}>
                      {entry.name} ({entry.count})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="activity-range" className="sr-only">
                Filter by date range
              </Label>
              <Select
                value={String(range)}
                onValueChange={(value) =>
                  setRange(value === 'all' ? 'all' : (Number(value) as ActivityRange))
                }
              >
                <SelectTrigger id="activity-range" className="w-full">
                  <SelectValue placeholder="All time" />
                </SelectTrigger>
                <SelectContent>
                  {RANGE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="activity-sort" className="sr-only">
                Sort order
              </Label>
              <Select
                value={sortDir}
                onValueChange={(value) => setSortDir(value as 'asc' | 'desc')}
              >
                <SelectTrigger id="activity-sort" className="w-full">
                  <SelectValue placeholder="Newest first" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="desc">Newest first</SelectItem>
                  <SelectItem value="asc">Oldest first</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="justify-start lg:justify-center"
              onClick={clearFilters}
              disabled={!hasFilters}
            >
              <FilterX aria-hidden="true" />
              Clear filters
            </Button>
          </div>
        </CardContent>

        {error ? (
          <ErrorState
            title="Activity logs could not be loaded"
            description="The activity service did not return the audit trail."
            onRetry={reload}
          />
        ) : loading && !result ? (
          <ListSkeleton rows={8} label="Loading activity logs" />
        ) : result && result.total === 0 ? (
          <EmptyState
            title={hasFilters ? 'No events match these filters' : 'No activity recorded yet'}
            description={
              hasFilters
                ? 'Try a broader date range, a different action, or clear the filters.'
                : 'Ticket and reply events will appear here once they are recorded.'
            }
            action={
              hasFilters ? (
                <Button variant="outline" size="sm" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        ) : result ? (
          <div className={loading ? 'opacity-60 transition-opacity' : undefined}>
            <Table aria-label="Activity log events">
              <TableHeader>
                <TableRow className="hover:bg-card-muted">
                  <TableHead className="pl-4">Time</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Ticket</TableHead>
                  <TableHead className="hidden md:table-cell">Reply</TableHead>
                  <TableHead className="pr-4">Summary</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap pl-4 align-top text-xs text-muted-foreground">
                      <time dateTime={entry.createdAt}>
                        {formatDateTime(entry.createdAt)}
                      </time>
                    </TableCell>
                    <TableCell className="align-top">
                      <span className="block max-w-[150px] truncate text-sm text-foreground">
                        {entry.actorName}
                      </span>
                      <span className="block text-2xs text-subtle-foreground">
                        {ACTOR_TYPE_LABELS[entry.actorType]}
                      </span>
                    </TableCell>
                    <TableCell className="align-top">
                      <Badge variant={actionVariant(entry.action)}>
                        {ACTIVITY_ACTION_LABELS[entry.action]}
                      </Badge>
                    </TableCell>
                    <TableCell className="align-top">
                      <Link
                        to={`/tickets/${entry.ticketId}`}
                        state={{ returnTo: '/activity' }}
                        className="font-medium tabular-nums text-primary underline-offset-2 hover:underline"
                      >
                        {entry.ticketId}
                      </Link>
                    </TableCell>
                    <TableCell className="hidden align-top text-xs text-muted-foreground md:table-cell">
                      {entry.replyId ? (
                        <span className="font-mono text-2xs">{entry.replyId}</span>
                      ) : (
                        <span className="text-subtle-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[440px] align-top text-xs text-muted-foreground">
                      {entry.summary}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination
              page={currentPage}
              pageCount={result.pageCount}
              total={result.total}
              pageSize={result.pageSize}
              onPageChange={setPage}
              itemLabel="events"
              ariaLabel="Activity log pages"
            />
          </div>
        ) : null}
      </Card>

      <p className="text-xs text-muted-foreground">
        This log is an internal operational view. Message bodies and reviewer
        comments stay in their dedicated ticket and approval contexts.
      </p>
    </div>
  )
}
