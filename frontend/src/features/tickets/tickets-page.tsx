import * as React from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { FilterX, FlaskConical } from 'lucide-react'
import type {
  TicketCategory,
  TicketPriority,
  TicketSortField,
  TicketStatus,
} from '@/types/ticket'
import { PageHeader } from '@/components/shared/page-header'
import { Pagination } from '@/components/shared/pagination'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/shared/states'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/input'
import { ConfirmDialog } from '@/components/shared/confirm-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
  TICKET_STATUSES,
} from '@/lib/ticket-config'
import { cn } from '@/lib/utils'
import {
  EMPTY_FACETS,
  hasActiveFacets,
  useTickets,
  type TicketFacets,
  type TicketQueueScope,
} from './use-tickets'
import { TicketTable } from './ticket-table'

const SCOPE_META: Record<
  TicketQueueScope,
  { title: string; description: string }
> = {
  all: {
    title: 'All Tickets',
    description:
      'Every ticket in the queue — search, filter and triage from here.',
  },
  mine: {
    title: 'My Tickets',
    description: 'Tickets assigned to the demo user (Abebe Kebede).',
  },
  unassigned: {
    title: 'Unassigned',
    description:
      'Active tickets waiting for an owner. Claim one to keep queue time down.',
  },
  needs_review: {
    title: 'Needs Review',
    description:
      'Tickets the classification step could not route confidently. Status is fixed to “Needs Review” on this queue.',
  },
}

/**
 * Search-filter-sort-paginate view over the ticket dataset. All data flows
 * through the TicketService interface; nothing here knows about fixtures.
 */
export function TicketsPage({ scope }: { scope: TicketQueueScope }) {
  const meta = SCOPE_META[scope]
  const [searchParams] = useSearchParams()
  const [facets, setFacets] = React.useState<TicketFacets>(() => ({
    ...EMPTY_FACETS,
    search: searchParams.get('q') ?? '',
  }))
  const [sortBy, setSortBy] = React.useState<TicketSortField>('createdAt')
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('desc')
  const [page, setPage] = React.useState(1)
  const [clearDialogOpen, setClearDialogOpen] = React.useState(false)

  /* Follow ?q= changes that come from the global header search. */
  React.useEffect(() => {
    const urlQ = searchParams.get('q') ?? ''
    setFacets((f) => {
      if (f.search === urlQ) return f
      return { ...f, search: urlQ }
    })
    setPage(1)
  }, [searchParams])

  /** Reflect the local search box into the URL without navigating. */
  const writeSearchParam = React.useCallback((value: string) => {
    const url = new URL(window.location.href)
    if (value.trim()) url.searchParams.set('q', value.trim())
    else url.searchParams.delete('q')
    const qs = url.searchParams.toString()
    window.history.replaceState(
      null,
      '',
      `${url.pathname}${qs ? `?${qs}` : ''}${url.hash}`,
    )
  }, [])

  const { data, loading, error, errorSimulated, setErrorSimulated, refetch } =
    useTickets(scope, facets, sortBy, sortDir, page)

  const activeFilters = hasActiveFacets(facets)
  const activeGroups = [
    facets.search.trim().length > 0,
    facets.statuses.length > 0,
    facets.categories.length > 0,
    facets.priorities.length > 0,
  ].filter(Boolean).length

  function setFacet<K extends keyof TicketFacets>(key: K, value: TicketFacets[K]) {
    setFacets((f) => ({ ...f, [key]: value }))
    setPage(1)
    if (key === 'search') writeSearchParam(value as string)
  }

  function clearFilters() {
    setFacets(EMPTY_FACETS)
    setPage(1)
    writeSearchParam('')
  }

  function handleSort(field: TicketSortField) {
    if (field === sortBy) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(field)
      setSortDir(field === 'createdAt' ? 'desc' : 'asc')
    }
    setPage(1)
  }

  return (
    <div>
      <PageHeader
        title={meta.title}
        description={meta.description}
        breadcrumb={
          scope !== 'all' ? (
            <Link to="/tickets" className="hover:text-foreground hover:underline">
              Tickets
            </Link>
          ) : undefined
        }
      />

      <Card className="overflow-hidden">
        {/* Toolbar: queue-local search + facet selects + demo controls */}
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
          <div className="min-w-[200px] flex-1 sm:max-w-xs">
            <SearchInput
              type="search"
              aria-label="Search this queue"
              placeholder="Search this queue…"
              value={facets.search}
              onChange={(e) => setFacet('search', e.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Status */}
            {scope === 'needs_review' ? (
              <Select value="needs_review" disabled>
                <SelectTrigger
                  className="w-[10rem] cursor-not-allowed"
                  aria-label="Status filter, fixed to Needs Review on this queue"
                >
                  <span className="text-xs text-muted-foreground">
                    Status: <span className="font-medium text-foreground">Needs Review</span>
                  </span>
                </SelectTrigger>
              </Select>
            ) : (
              <Select
                value={facets.statuses[0] ?? 'all'}
                onValueChange={(value) =>
                  setFacet('statuses', value === 'all' ? [] : ([value] as TicketStatus[]))
                }
              >
                <SelectTrigger className="w-[10rem]" aria-label="Filter by status">
                  <span className="truncate text-xs text-muted-foreground">
                    Status:{' '}
                    <span
                      className={cn(
                        facets.statuses[0] && 'font-medium text-foreground',
                      )}
                    >
                      {facets.statuses[0] ? STATUS_LABELS[facets.statuses[0]] : 'All'}
                    </span>
                  </span>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  {TICKET_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* Category */}
            <Select
              value={facets.categories[0] ?? 'all'}
              onValueChange={(value) =>
                setFacet('categories', value === 'all' ? [] : ([value] as TicketCategory[]))
              }
            >
              <SelectTrigger className="w-[10.5rem]" aria-label="Filter by category">
                <span className="truncate text-xs text-muted-foreground">
                  Category:{' '}
                  <span
                    className={cn(
                      facets.categories[0] && 'font-medium text-foreground',
                    )}
                  >
                    {facets.categories[0] ? CATEGORY_LABELS[facets.categories[0]] : 'All'}
                  </span>
                </span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {TICKET_CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {CATEGORY_LABELS[c]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Priority */}
            <Select
              value={facets.priorities[0] ?? 'all'}
              onValueChange={(value) =>
                setFacet('priorities', value === 'all' ? [] : ([value] as TicketPriority[]))
              }
            >
              <SelectTrigger className="w-[10.5rem]" aria-label="Filter by priority">
                <span className="truncate text-xs text-muted-foreground">
                  Priority:{' '}
                  <span
                    className={cn(
                      facets.priorities[0] && 'font-medium text-foreground',
                    )}
                  >
                    {facets.priorities[0] ? PRIORITY_LABELS[facets.priorities[0]] : 'All'}
                  </span>
                </span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All priorities</SelectItem>
                {TICKET_PRIORITIES.map((p) => (
                  <SelectItem key={p} value={p}>
                    {PRIORITY_LABELS[p]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {activeFilters ? (
              activeGroups >= 2 ? (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setClearDialogOpen(true)}
                  >
                    <FilterX aria-hidden="true" />
                    Clear filters
                  </Button>
                  <ConfirmDialog
                    open={clearDialogOpen}
                    onOpenChange={setClearDialogOpen}
                    title="Clear all filters?"
                    description="Search, status, category and priority filters will reset."
                    confirmLabel="Clear filters"
                    onConfirm={clearFilters}
                  />
                </>
              ) : (
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  <FilterX aria-hidden="true" />
                  Clear filters
                </Button>
              )
            ) : null}
          </div>

          <div className="ml-auto flex items-center gap-2">
            {data && !loading && !error ? (
              <p
                aria-live="polite"
                className="whitespace-nowrap text-xs text-muted-foreground"
              >
                <span className="font-medium text-foreground">{data.total}</span>{' '}
                {data.total === 1 ? 'ticket' : 'tickets'} match
              </p>
            ) : null}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Demo controls, including a toggle that simulates a failed request"
                >
                  <FlaskConical aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-64">
                <DropdownMenuCheckboxItem
                  checked={errorSimulated}
                  onCheckedChange={(checked) => {
                    setErrorSimulated(Boolean(checked))
                    refetch()
                  }}
                  onSelect={(e) => e.preventDefault()}
                >
                  Simulate request error
                </DropdownMenuCheckboxItem>
                <p className="px-2 py-1.5 text-2xs text-subtle-foreground">
                  Exercises the failure UI used when the real API misbehaves.
                </p>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* Body */}
        {loading ? (
          <ListSkeleton rows={8} />
        ) : error ? (
          <ErrorState
            title="Tickets could not be loaded"
            description={error.message}
            onRetry={() => {
              setErrorSimulated(false)
              refetch()
            }}
          />
        ) : !data ? null : data.items.length === 0 ? (
          data.total === 0 && !activeFilters ? (
            <EmptyState
              title="This queue is empty"
              description="New tickets will appear here as soon as intake runs."
              action={
                <Button variant="outline" size="sm" asChild>
                  <Link to="/">Back to Overview</Link>
                </Button>
              }
            />
          ) : (
            <EmptyState
              title="No tickets match these filters"
              description="Try a different search term, or clear one or more filters."
              action={
                <Button variant="outline" size="sm" onClick={clearFilters}>
                  <FilterX aria-hidden="true" />
                  Clear filters
                </Button>
              }
            />
          )
        ) : (
          <>
            <TicketTable
              tickets={data.items}
              sortBy={sortBy}
              sortDir={sortDir}
              onSort={handleSort}
            />
            <Pagination
              page={data.page}
              pageCount={data.pageCount}
              total={data.total}
              pageSize={data.pageSize}
              onPageChange={setPage}
            />
          </>
        )}
      </Card>
    </div>
  )
}
