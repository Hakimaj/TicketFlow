import * as React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar, type NavCounts } from './sidebar'
import { TopHeader } from './top-header'
import { ticketService } from '@/services'

/**
 * Persistent application shell: fixed sidebar + sticky top header scrolling
 * content. Counts for the "Unassigned" and "Needs Review" badges are fetched
 * once from the demo service, exactly as the future API integration would.
 */
export function AppLayout() {
  const location = useLocation()
  const [counts, setCounts] = React.useState<NavCounts>({})

  React.useEffect(() => {
    let cancelled = false
    const fetchCounts = () => {
      ticketService
        .getDashboardStats()
        .then((stats) => {
          if (!cancelled) {
            setCounts({
              unassigned: stats.unassignedTickets,
              needs_review: stats.needsReviewTickets,
            })
          }
        })
        .catch(() => {
          /* Badge counts are cosmetic; the pages surface real errors. */
        })
    }

    fetchCounts()
    const unsubscribe = ticketService.subscribe(() => {
      fetchCounts()
    })

    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [])

  // Move keyboard focus to the content region on route change (a11y).
  const mainRef = React.useRef<HTMLElement | null>(null)
  React.useEffect(() => {
    mainRef.current?.focus({ preventScroll: false })
  }, [location.pathname])

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar counts={counts} />
      <div className="flex min-h-screen flex-1 flex-col lg:pl-60">
        <TopHeader counts={counts} />
        <main
          id="content"
          ref={mainRef}
          tabIndex={-1}
          aria-label="Page content"
          className="min-w-0 flex-1 px-4 py-5 outline-none lg:px-6"
        >
          <Outlet />
        </main>
        <footer className="shrink-0 border-t border-border px-4 py-2.5 text-2xs text-subtle-foreground lg:px-6">
          TicketFlow demo workspace — demonstration data only; no external
          services are connected.
        </footer>
      </div>
    </div>
  )
}
