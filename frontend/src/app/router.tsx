import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout'
import { RequireAuth } from '@/auth'
import { LoginPage } from '@/features/auth/login-page'
import { ChangePasswordPage } from '@/features/auth/change-password-page'
import { DashboardPage } from '@/features/dashboard'
import { NewTicketPage, TicketsPage, TicketDetailPage } from '@/features/tickets'
import { ApprovalsPage } from '@/features/approvals'
import { AnalyticsPage } from '@/features/analytics'
import { ActivityLogsPage } from '@/features/activity'
import { AccountsPage } from '@/features/accounts'
import { SettingsPage } from '@/features/settings'

/**
 * TicketFlow application routes.
 *
 * `/login` is the only public screen. Every operational route is wrapped in a
 * session guard, and reply approvals / account management additionally require
 * the server-granted `replies:review` / `accounts:manage` permissions.
 *
 * A provisioned account is redirected to `/change-password` by the guard until
 * it replaces its initial password; the API enforces the same rule.
 */
export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePasswordPage />
          </RequireAuth>
        }
      />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<DashboardPage />} />

        {/* Ticket queues and staff intake */}
        <Route path="/tickets/new" element={<NewTicketPage />} />
        <Route path="/tickets" element={<TicketsPage scope="all" />} />
        <Route path="/tickets/mine" element={<TicketsPage scope="mine" />} />
        <Route path="/tickets/unassigned" element={<TicketsPage scope="unassigned" />} />
        <Route path="/tickets/needs-review" element={<TicketsPage scope="needs_review" />} />
        <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />

        {/* Reply Approvals — review permission required */}
        <Route
          path="/approvals"
          element={
            <RequireAuth permission="replies:review">
              <ApprovalsPage />
            </RequireAuth>
          }
        />

        {/* Operational insight */}
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/activity" element={<ActivityLogsPage />} />

        {/* Account administration — `accounts:manage` required */}
        <Route
          path="/accounts"
          element={
            <RequireAuth permission="accounts:manage">
              <AccountsPage />
            </RequireAuth>
          }
        />

        <Route path="/settings" element={<SettingsPage />} />

        {/* Fallbacks */}
        <Route path="/settings/*" element={<Navigate to="/settings" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
