import type { ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { Spinner } from '@/components/shared/states'
import { Button } from '@/components/ui/button'
import { useAuth } from './use-auth'

/** Where an account with an administrator-issued password must go first. */
export const CHANGE_PASSWORD_PATH = '/change-password'

/**
 * Route guard for the authenticated workspace.
 *
 * Unauthenticated visitors are sent to `/login`, which returns them to the
 * requested page after sign-in. A missing permission renders an explicit
 * "not available for your role" state instead of a broken screen — the server
 * enforces the same rule on every endpoint.
 */
export function RequireAuth({
  children,
  permission,
}: {
  children: ReactNode
  permission?: string
}) {
  const { status, hasPermission, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Spinner label="Restoring your session…" />
      </div>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  // A provisioned account must set its own password before the workspace
  // opens. The server enforces the same rule on every operational endpoint.
  if (
    user?.must_change_password &&
    location.pathname !== CHANGE_PASSWORD_PATH
  ) {
    return <Navigate to={CHANGE_PASSWORD_PATH} replace />
  }

  if (permission && !hasPermission(permission)) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center px-6 py-20 text-center">
        <span
          aria-hidden="true"
          className="mb-3 flex size-10 items-center justify-center rounded-full bg-danger-tint text-danger"
        >
          <ShieldAlert className="size-5" />
        </span>
        <h1 className="text-base font-semibold text-foreground">
          Not available for your role
        </h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Your account does not have the review permission this page requires.
          Ask an administrator if you need access.
        </p>
        <Button variant="outline" size="sm" asChild className="mt-4">
          <Link to="/">Back to overview</Link>
        </Button>
      </div>
    )
  }

  return children
}
