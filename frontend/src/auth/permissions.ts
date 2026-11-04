/**
 * Client-side mirror of the server permission matrix.
 *
 * These strings only decide which affordances the UI shows; the backend
 * re-checks every action against the account's database role. Demo mode has
 * no server, so it uses this matrix for the local demonstration identity.
 */
import type { AccountRole } from '@/types/auth'

const BASE_PERMISSIONS = [
  'tickets:read',
  'tickets:write',
  'notes:write',
  'replies:write',
  'replies:send',
  'analytics:read',
] as const

const REVIEW_PERMISSIONS = ['replies:review'] as const

export const ROLE_PERMISSIONS: Record<AccountRole, string[]> = {
  agent: [...BASE_PERMISSIONS],
  reviewer: [...BASE_PERMISSIONS, ...REVIEW_PERMISSIONS],
  admin: [...BASE_PERMISSIONS, ...REVIEW_PERMISSIONS, 'accounts:manage'],
}

export function permissionsForRole(role: AccountRole): string[] {
  return [...ROLE_PERMISSIONS[role]]
}
