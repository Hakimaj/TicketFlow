/** Authenticated account as returned by `GET /auth/me` and the auth endpoints. */

export type AccountRole = 'agent' | 'reviewer' | 'admin'

export interface AccountProfile {
  id: string
  email: string
  display_name: string
  role: AccountRole
  /** Linked support agent, used for assignment ("my tickets") attribution. */
  agent_id: string | null
  agent_name: string | null
  /**
   * True while a provisioned account still uses the initial password an
   * administrator set. Operational endpoints are blocked until it is changed.
   */
  must_change_password: boolean
  /** Server-derived permission strings; the server enforces them. */
  permissions: string[]
}

/** Account record returned by the administrator-only `/accounts` API. */
export interface AdminAccount {
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

export interface AdminAccountList {
  items: AdminAccount[]
  pagination: {
    page: number
    page_size: number
    total: number
    page_count: number
  }
}

/** Fields an administrator may change. Omitted fields stay untouched. */
export interface AdminAccountUpdate {
  display_name?: string
  role?: AccountRole
  /** `null` unlinks the agent. */
  agent_id?: string | null
  is_active?: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: AccountProfile
}
