/**
 * Authentication API calls.
 *
 * The access token never leaves module memory (`apiClient` keeps it out of
 * storage); the refresh token is an HttpOnly cookie the browser manages for
 * `/api/v1/auth`. No credential is ever persisted by this module.
 */
import type { AccountProfile, AuthResponse } from '@/types/auth'
import { request, setAccessToken } from './apiClient'

/** Cookie endpoints must always be same-request retried only by this layer. */
const AUTH_OPTIONS = { withCredentials: true, skipAuthRetry: true } as const

export async function signInWithPassword(
  email: string,
  password: string,
): Promise<AccountProfile> {
  const payload = await request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
    ...AUTH_OPTIONS,
  })
  setAccessToken(payload.access_token)
  return payload.user
}

/** Rotates the refresh cookie and stores the new short-lived access token. */
export async function restoreSession(): Promise<AccountProfile> {
  const payload = await request<AuthResponse>('/auth/refresh', {
    method: 'POST',
    ...AUTH_OPTIONS,
  })
  setAccessToken(payload.access_token)
  return payload.user
}

/** Revokes the refresh session server-side and clears the in-memory token. */
export async function endSession(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST', ...AUTH_OPTIONS })
  } finally {
    setAccessToken(null)
  }
}

/**
 * Replaces the signed-in account's password.
 *
 * Used both for a normal password change and to clear the forced change on an
 * account an administrator provisioned. The server revokes every existing
 * refresh session and returns a fresh rotated one.
 */
export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<AccountProfile> {
  const payload = await request<AuthResponse>('/auth/password', {
    method: 'POST',
    body: {
      current_password: currentPassword,
      new_password: newPassword,
    },
    ...AUTH_OPTIONS,
  })
  setAccessToken(payload.access_token)
  return payload.user
}

/** Re-reads the account from the server for the current access token. */
export async function fetchCurrentAccount(): Promise<AccountProfile> {
  return request<AccountProfile>('/auth/me', { method: 'GET' })
}
