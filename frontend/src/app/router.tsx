import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout'
import { DashboardPage } from '@/features/dashboard'
import { TicketsPage, TicketDetailPage } from '@/features/tickets'
import { ApprovalsPage } from '@/features/approvals'
import { AnalyticsPage } from '@/features/analytics'
import { ActivityLogsPage } from '@/features/activity'
import { SettingsPage } from '@/features/settings'

/**
 * TicketFlow application routes.
 *
 * Every sidebar entry resolves to a working screen. `TicketsPage` covers All
 * Tickets, My Tickets, Unassigned and Needs Review through its `scope` prop.
 * `/tickets/:ticketId` resolves to the interactive TicketDetailPage.
 * `/approvals` manages customer reply human approvals.
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
        <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />

        {/* Reply Approvals */}
        <Route path="/approvals" element={<ApprovalsPage />} />

        {/* Operational insight */}
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/activity" element={<ActivityLogsPage />} />
        <Route path="/settings" element={<SettingsPage />} />

        {/* Fallbacks */}
        <Route path="/settings/*" element={<Navigate to="/settings" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
