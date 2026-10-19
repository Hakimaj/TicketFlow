import * as React from 'react'
import { ticketService, TicketServiceError } from '@/services'
import type { DashboardStats } from '@/types/ticket'

/** Loads the derived dashboard numbers once; exposes refetch for retries. */
export function useDashboardStats(trendDays = 30) {
  const [stats, setStats] = React.useState<DashboardStats | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<Error | null>(null)
  const [refetchKey, setRefetchKey] = React.useState(0)

  const refetch = React.useCallback(() => setRefetchKey((k) => k + 1), [])

  React.useEffect(() => {
    return ticketService.subscribe(() => {
      refetch()
    })
  }, [refetch])

  React.useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    ticketService
      .getDashboardStats(trendDays)
      .then((result) => {
        if (cancelled) return
        setStats(result)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(
          err instanceof TicketServiceError
            ? err
            : new TicketServiceError('Failed to load dashboard statistics', err),
        )
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [trendDays, refetchKey])

  return { stats, loading, error, refetch }
}
