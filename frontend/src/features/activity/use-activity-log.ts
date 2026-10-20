import * as React from 'react'
import { ticketService } from '@/services'
import type {
  ActivityLogFacets,
  ActivityLogPage,
  ActivityLogQuery,
} from '@/types/activity'

/**
 * Paged, sanitized audit-log query. The service owns filtering, sorting and
 * pagination so a future backend can implement the same contract.
 */
export function useActivityLog(query: ActivityLogQuery) {
  const [result, setResult] = React.useState<ActivityLogPage | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<Error | null>(null)
  const [reloadToken, setReloadToken] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false

    const load = (showLoading: boolean) => {
      if (showLoading) setLoading(true)
      ticketService
        .listActivityLog(query)
        .then((page) => {
          if (cancelled) return
          setResult(page)
          setError(null)
          setLoading(false)
        })
        .catch((err: unknown) => {
          if (cancelled) return
          setError(err instanceof Error ? err : new Error('Activity logs could not be loaded.'))
          setLoading(false)
        })
    }

    load(true)
    const unsubscribe = ticketService.subscribe(() => load(false))
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [query, reloadToken])

  return {
    result,
    loading,
    error,
    reload: () => setReloadToken((token) => token + 1),
  }
}

/** Actor/action facets for the filter controls, refreshed after mutations. */
export function useActivityLogFacets() {
  const [facets, setFacets] = React.useState<ActivityLogFacets | null>(null)

  React.useEffect(() => {
    let cancelled = false
    const load = () => {
      ticketService
        .getActivityLogFacets()
        .then((next) => {
          if (!cancelled) setFacets(next)
        })
        .catch(() => {
          /* Filters remain usable with an empty option list. */
        })
    }

    load()
    const unsubscribe = ticketService.subscribe(load)
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [])

  return facets
}
