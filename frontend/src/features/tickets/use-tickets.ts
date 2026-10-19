import * as React from 'react'
import type {
  TicketCategory,
  TicketPage,
  TicketPriority,
  TicketQuery,
  TicketSortField,
  TicketStatus,
} from '@/types/ticket'
import { ticketService, TicketServiceError } from '@/services'

/**
 * Facet state shared by every ticket-queue page. Keeping it in one hook
 * means All Tickets / My Tickets / Unassigned / Needs Review all get
 * identical search, filter, sort, pagination and error handling built on
 * the same service interface.
 */

export type TicketQueueScope = 'all' | 'mine' | 'unassigned' | 'needs_review'

export interface TicketFacets {
  search: string
  statuses: TicketStatus[]
  categories: TicketCategory[]
  priorities: TicketPriority[]
}

export const EMPTY_FACETS: TicketFacets = {
  search: '',
  statuses: [],
  categories: [],
  priorities: [],
}

export function hasActiveFacets(facets: TicketFacets): boolean {
  return Boolean(
    facets.search.trim() ||
      facets.statuses.length ||
      facets.categories.length ||
      facets.priorities.length,
  )
}

const SCOPE_TO_QUERY: Record<
  TicketQueueScope,
  Pick<TicketQuery, 'assignmentScope' | 'statuses'>
> = {
  all: {},
  mine: { assignmentScope: 'mine' },
  unassigned: { assignmentScope: 'unassigned' },
  needs_review: { statuses: ['needs_review'] },
}

export const SORTABLE_COLUMNS: TicketSortField[] = [
  'createdAt',
  'subject',
  'category',
  'priority',
  'status',
]

export interface UseTicketsResult {
  data: TicketPage | null
  loading: boolean
  error: Error | null
  /** Demo-only switch that forces the error state to be exercised. */
  errorSimulated: boolean
  setErrorSimulated: (value: boolean) => void
  refetch: () => void
}

export function useTickets(
  scope: TicketQueueScope,
  facets: TicketFacets,
  sortBy: TicketSortField,
  sortDir: 'asc' | 'desc',
  page: number,
): UseTicketsResult {
  const [data, setData] = React.useState<TicketPage | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<Error | null>(null)
  const [errorSimulated, setErrorSimulated] = React.useState(false)
  const [refetchKey, setRefetchKey] = React.useState(0)

  const refetch = React.useCallback(() => setRefetchKey((k) => k + 1), [])

  React.useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const finish = (result: TicketPage | null, err: Error | null) => {
      if (cancelled) return
      setData(result)
      setError(err)
      setLoading(false)
    }

    if (errorSimulated) {
      // Demo control: exercises the exact error UI a real API failure will
      // produce, without pretending anything about a backend.
      finish(null, new TicketServiceError('Simulated request failure (demo control).'))
      return () => {
        cancelled = true
      }
    }

    ticketService
      .listTickets({
        search: facets.search.trim() || null,
        statuses: facets.statuses.length ? facets.statuses : null,
        categories: facets.categories.length ? facets.categories : null,
        priorities: facets.priorities.length ? facets.priorities : null,
        sortBy,
        sortDir,
        page,
        pageSize: 12,
        ...SCOPE_TO_QUERY[scope],
      })
      .then((result) => finish(result, null))
      .catch((err: unknown) =>
        finish(
          null,
          err instanceof TicketServiceError
            ? err
            : new TicketServiceError('Failed to load tickets', err),
        ),
      )

    return () => {
      cancelled = true
    }
  }, [
    scope,
    facets.search,
    facets.statuses,
    facets.categories,
    facets.priorities,
    sortBy,
    sortDir,
    page,
    refetchKey,
    errorSimulated,
  ])

  return {
    data,
    loading,
    error,
    errorSimulated,
    setErrorSimulated,
    refetch,
  }
}
