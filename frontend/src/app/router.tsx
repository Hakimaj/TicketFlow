import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout'
import { DashboardPage } from '@/features/dashboard'
import { TicketsPage } from '@/features/tickets'
import { TicketDetailPlaceholder } from '@/features/tickets'
import { PlaceholderPage } from '@/features/placeholders'

/**
 * Phase 1 routing.
 *
 * Every sidebar entry resolves — unimplemented areas render an intentional
 * placeholder rather than a blank screen. `TicketsPage` covers All Tickets,
 * My Tickets, Unassigned and Needs Review through its `scope` prop.
 */
export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />

        {/* Ticket queues */}
        <Route path="/tickets" element={<TicketsPage scope="all" />} />
        <Route path="/tickets/mine" element={<TicketsPage scope="mine" />} />
        <Route path="/tickets/unassigned" element={<TicketsPage scope="unassigned" />} />
        <Route path="/tickets/needs-review" element={<TicketsPage scope="needs_review" />} />
        <Route path="/tickets/:ticketId" element={<TicketDetailPlaceholder />} />

        {/* Phase 2+ areas */}
        <Route path="/analytics" element={<PlaceholderPage area="analytics" />} />
        <Route path="/activity" element={<PlaceholderPage area="activity" />} />
        <Route path="/settings" element={<PlaceholderPage area="settings" />} />
        <Route
          path="/settings/profile"
          element={<PlaceholderPage area="settings" />}
        />

        {/* Fallbacks */}
        <Route path="/settings/*" element={<Navigate to="/settings" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
