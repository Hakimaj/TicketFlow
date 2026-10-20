import * as React from 'react'
import { ticketService } from '@/services'
import type { Agent } from '@/types/ticket'

/** Roster for assignee display; loaded through the service, never fixtures. */
export function useAgents() {
  const [agents, setAgents] = React.useState<Agent[]>([])

  React.useEffect(() => {
    let cancelled = false
    const load = () => {
      ticketService
        .listAgents()
        .then((next) => {
          if (!cancelled) setAgents(next)
        })
        .catch(() => {
          /* Assignee labels fall back to team names. */
        })
    }

    load()
    const unsubscribe = ticketService.subscribe(load)
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [])

  return agents
}
