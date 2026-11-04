import * as React from 'react'
import type { AccountProfile } from '@/types/auth'

export type AuthStatus = 'demo' | 'loading' | 'authenticated' | 'unauthenticated'

export interface AuthState {
  status: AuthStatus
  user: AccountProfile | null
  /** Present when a stored session could not be validated. */
  sessionError: string | null
}

export interface AuthContextValue extends AuthState {
  isDemo: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  /** Replace this account's password (also clears a forced change). */
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>
  hasPermission: (permission: string) => boolean
}

export const AuthContext = React.createContext<AuthContextValue | null>(null)
