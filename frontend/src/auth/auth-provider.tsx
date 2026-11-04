import * as React from 'react'
import { isDemoMode } from '@/config/app-mode'
import { setRefreshHandler, setUnauthorizedHandler } from '@/services/apiClient'
import {
  changePassword as changePasswordRequest,
  endSession,
  restoreSession,
  signInWithPassword,
} from '@/services/authService'
import type { AccountProfile } from '@/types/auth'
import { AuthContext, type AuthContextValue, type AuthState } from './context'
import { DEMO_ACCOUNT } from './demo-account'

/**
 * Session state for the application.
 *
 * API mode restores the session once on startup by rotating the HttpOnly
 * refresh cookie. Demo mode never contacts a backend and exposes a clearly
 * labelled demonstration identity.
 */

/**
 * One shared restore across mounts. React StrictMode mounts effects twice in
 * development, and refresh tokens rotate on every use: two parallel refreshes
 * would make the second look like token reuse.
 */
let restoreInFlight: Promise<AccountProfile> | null = null

function restoreOnce(): Promise<AccountProfile> {
  if (!restoreInFlight) {
    restoreInFlight = restoreSession().finally(() => {
      restoreInFlight = null
    })
  }
  return restoreInFlight
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<AuthState>(() =>
    isDemoMode
      ? { status: 'demo', user: DEMO_ACCOUNT, sessionError: null }
      : { status: 'loading', user: null, sessionError: null },
  )

  const applyUser = React.useCallback((user: AccountProfile) => {
    setState({ status: 'authenticated', user, sessionError: null })
  }, [])

  React.useEffect(() => {
    if (isDemoMode) return
    let cancelled = false

    setRefreshHandler(async () => {
      const user = await restoreOnce()
      if (!cancelled) applyUser(user)
    })
    setUnauthorizedHandler(() => {
      if (cancelled) return
      setState({
        status: 'unauthenticated',
        user: null,
        sessionError: 'Your session has expired. Sign in again.',
      })
    })

    restoreOnce()
      .then((user) => {
        if (!cancelled) applyUser(user)
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: 'unauthenticated', user: null, sessionError: null })
        }
      })

    return () => {
      cancelled = true
      setRefreshHandler(null)
      setUnauthorizedHandler(null)
    }
  }, [applyUser])

  const signIn = React.useCallback(
    async (email: string, password: string) => {
      const user = await signInWithPassword(email, password)
      applyUser(user)
    },
    [applyUser],
  )

  const signOut = React.useCallback(async () => {
    if (isDemoMode) return
    try {
      await endSession()
    } catch {
      // The local session is cleared regardless; server-side revocation is
      // best-effort when the network is unavailable.
    } finally {
      setState({ status: 'unauthenticated', user: null, sessionError: null })
    }
  }, [])

  const changePassword = React.useCallback(
    async (currentPassword: string, newPassword: string) => {
      const user = await changePasswordRequest(currentPassword, newPassword)
      applyUser(user)
    },
    [applyUser],
  )

  const hasPermission = React.useCallback(
    (permission: string) => {
      if (isDemoMode) return true
      return state.user?.permissions.includes(permission) ?? false
    },
    [state.user],
  )

  const value = React.useMemo<AuthContextValue>(
    () => ({
      ...state,
      isDemo: isDemoMode,
      signIn,
      signOut,
      changePassword,
      hasPermission,
    }),
    [state, signIn, signOut, changePassword, hasPermission],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
