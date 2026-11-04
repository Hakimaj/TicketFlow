import * as React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { AlertCircle, ShieldCheck } from 'lucide-react'
import { BrandMark } from '@/components/layout/sidebar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/auth'
import { ApiClientError } from '@/services/apiClient'
import { API_BASE_URL } from '@/config/app-mode'

interface LocationState {
  from?: { pathname?: string; search?: string }
}

export function LoginPage() {
  const { status, signIn } = useAuth()
  const location = useLocation()
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [error, setError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)

  const state = location.state as LocationState | null
  const destination = `${state?.from?.pathname ?? '/'}${
    state?.from?.search ?? ''
  }`

  // Authenticated or demo sessions never need this page.
  if (status === 'authenticated' || status === 'demo') {
    return <Navigate to={destination} replace />
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (submitting) return
    setError(null)
    setSubmitting(true)
    try {
      await signIn(email.trim(), password)
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : 'Could not sign in. Check your connection and try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <BrandMark />
          <p className="text-xs text-muted-foreground">
            Support operations workspace
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-border bg-card p-5 shadow-xs"
          aria-label="Sign in to TicketFlow"
        >
          <div>
            <h1 className="text-base font-semibold text-foreground">Sign in</h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Use your TicketFlow staff account. Sessions are verified by the
              API, not by the browser.
            </p>
          </div>

          {error ? (
            <p
              role="alert"
              className="flex items-start gap-1.5 rounded-md border border-danger/30 bg-danger-tint px-2.5 py-2 text-xs text-danger"
            >
              <AlertCircle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              {error}
            </p>
          ) : null}

          <div className="space-y-1">
            <Label htmlFor="login-email">Email</Label>
            <Input
              id="login-email"
              name="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@ticketflow.local"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="login-password">Password</Label>
            <Input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>

          <p className="flex items-start gap-1.5 text-2xs text-muted-foreground">
            <ShieldCheck aria-hidden="true" className="mt-0.5 size-3 shrink-0" />
            <span>
              Access tokens stay in this tab&apos;s memory; the refresh session
              is an HttpOnly cookie. Signing out revokes it server-side.
            </span>
          </p>
          <p className="text-2xs text-subtle-foreground">
            API: <code>{API_BASE_URL}</code>
          </p>
        </form>
      </div>
    </div>
  )
}
