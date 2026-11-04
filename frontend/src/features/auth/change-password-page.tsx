import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, ShieldCheck } from 'lucide-react'
import { BrandMark } from '@/components/layout/sidebar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/auth'
import { ApiClientError } from '@/services/apiClient'

/**
 * Password change for the signed-in account.
 *
 * Reached automatically when an administrator provisioned the account with an
 * initial password: the API refuses every operational endpoint until the
 * password is replaced, so this page is the only way forward. Changing it also
 * revokes every other refresh session.
 */

const MIN_PASSWORD_LENGTH = 12

export function ChangePasswordPage() {
  const { changePassword, user } = useAuth()
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = React.useState('')
  const [newPassword, setNewPassword] = React.useState('')
  const [confirmation, setConfirmation] = React.useState('')
  const [error, setError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)
  const submittingRef = React.useRef(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (submittingRef.current) return
    setError(null)

    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(`Choose a password of at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }
    if (newPassword !== confirmation) {
      setError('The new passwords do not match.')
      return
    }

    submittingRef.current = true
    setSubmitting(true)
    try {
      await changePassword(currentPassword, newPassword)
      navigate('/', { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : 'The password could not be changed. Check the connection and retry.',
      )
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <BrandMark />
          <p className="text-xs text-muted-foreground">
            {user?.must_change_password
              ? 'Your account uses an initial password set by an administrator.'
              : 'Signed in as ' + (user?.email ?? 'your account')}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-border bg-card p-5 shadow-xs"
          aria-label="Change your password"
        >
          <div>
            <h1 className="text-base font-semibold text-foreground">
              Set a new password
            </h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              The workspace stays locked until this is done. Other signed-in
              devices are signed out when the password changes.
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
            <Label htmlFor="current-password">Current password</Label>
            <Input
              id="current-password"
              name="current-password"
              type="password"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="new-password">New password</Label>
            <Input
              id="new-password"
              name="new-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD_LENGTH}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <p className="text-2xs text-muted-foreground">
              At least {MIN_PASSWORD_LENGTH} characters.
            </p>
          </div>

          <div className="space-y-1">
            <Label htmlFor="confirm-password">Confirm new password</Label>
            <Input
              id="confirm-password"
              name="confirm-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD_LENGTH}
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </div>

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? 'Saving…' : 'Save new password'}
          </Button>

          <p className="flex items-start gap-1.5 text-2xs text-muted-foreground">
            <ShieldCheck aria-hidden="true" className="mt-0.5 size-3 shrink-0" />
            <span>
              Passwords are hashed with Argon2id on the server and never stored
              or logged in clear text.
            </span>
          </p>
        </form>
      </div>
    </div>
  )
}
