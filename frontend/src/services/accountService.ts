/**
 * Administrator account-management API calls (`/api/v1/accounts`).
 *
 * The server enforces `accounts:manage`; hiding the navigation entry is only a
 * usability aid. No credential material is ever returned by these endpoints, so
 * nothing here can persist a password beyond the create request.
 */
import type {
  AccountRole,
  AdminAccount,
  AdminAccountList,
  AdminAccountUpdate,
} from '@/types/auth'
import { api } from './apiClient'

/* ------------------------------------------------------------------ */
/* Raw API shapes (snake_case)                                         */
/* ------------------------------------------------------------------ */

interface RawAdminAccount {
  id: string
  email: string
  display_name: string
  role: AccountRole
  is_active: boolean
  must_change_password: boolean
  agent_id: string | null
  agent_name: string | null
  created_at: string
  updated_at: string
}

interface RawAdminAccountList {
  items: RawAdminAccount[]
  pagination: {
    page: number
    page_size: number
    total: number
    page_count: number
  }
}

export interface AccountQuery {
  search?: string
  role?: AccountRole | null
  isActive?: boolean | null
  page?: number
  pageSize?: number
}

export interface CreateAccountInput {
  email: string
  displayName: string
  role: AccountRole
  /** Initial password; hashed by the server and never echoed back. */
  password: string
  agentId?: string | null
  isActive?: boolean
}

function mapAccount(raw: RawAdminAccount): AdminAccount {
  return {
    id: raw.id,
    email: raw.email,
    display_name: raw.display_name,
    role: raw.role,
    is_active: raw.is_active,
    must_change_password: raw.must_change_password,
    agent_id: raw.agent_id,
    agent_name: raw.agent_name,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
  }
}

function toQueryString(query: AccountQuery): string {
  const params = new URLSearchParams()
  if (query.search?.trim()) params.set('search', query.search.trim())
  if (query.role) params.set('role', query.role)
  if (query.isActive !== undefined && query.isActive !== null) {
    params.set('is_active', String(query.isActive))
  }
  if (query.page) params.set('page', String(query.page))
  if (query.pageSize) params.set('page_size', String(query.pageSize))
  const serialized = params.toString()
  return serialized ? `?${serialized}` : ''
}

export async function listAccounts(
  query: AccountQuery = {},
): Promise<AdminAccountList> {
  const response = await api.get<RawAdminAccountList>(
    `/accounts${toQueryString(query)}`,
  )
  return {
    items: response.items.map(mapAccount),
    pagination: response.pagination,
  }
}

export async function createAccount(
  input: CreateAccountInput,
): Promise<AdminAccount> {
  const created = await api.post<RawAdminAccount>('/accounts', {
    email: input.email,
    display_name: input.displayName,
    role: input.role,
    password: input.password,
    agent_id: input.agentId ?? undefined,
    is_active: input.isActive ?? true,
  })
  return mapAccount(created)
}

export async function updateAccount(
  accountId: string,
  patch: AdminAccountUpdate,
): Promise<AdminAccount> {
  const updated = await api.patch<RawAdminAccount>(
    `/accounts/${encodeURIComponent(accountId)}`,
    {
      display_name: patch.display_name,
      role: patch.role,
      // `undefined` omits the field; `null` explicitly unlinks the agent.
      agent_id: patch.agent_id,
      is_active: patch.is_active,
    },
  )
  return mapAccount(updated)
}
