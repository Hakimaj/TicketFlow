import * as React from 'react'
import { ticketService } from '@/services'
import type { AnalyticsRange, AnalyticsStats } from '@/types/analytics'

/**
 * Loads derived analytics from the shared service and refreshes whenever the
 * service publishes a ticket or reply mutation. No fixture data is read here.
 */
export function useAnalytics(range: AnalyticsRange) {
  const [stats, setStats] = React.useState<AnalyticsStats | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<Error | null>(null)
  const [reloadToken, setReloadToken] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false

    const load = (showLoading: boolean) => {
      if (showLoading) setLoading(true)
      ticketService
        .getAnalytics(range)
        .then((next) => {
          if (cancelled) return
          setStats(next)
          setError(null)
          setLoading(false)
        })
        .catch((err: unknown) => {
          if (cancelled) return
          setError(err instanceof Error ? err : new Error('Analytics could not be loaded.'))
          setLoading(false)
        })
    }

    load(true)
    const unsubscribe = ticketService.subscribe(() => load(false))
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [range, reloadToken])

  return {
    stats,
    loading,
    error,
    reload: () => setReloadToken((token) => token + 1),
  }
}
