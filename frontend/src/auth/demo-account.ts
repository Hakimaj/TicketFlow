import { DEMO_USER } from '@/data'
import type { AccountProfile } from '@/types/auth'
import { permissionsForRole } from './permissions'

/**
 * Demonstration identity used only when `VITE_DATA_MODE=demo` is set. The UI
 * labels it as a demo account everywhere it appears.
 */
export const DEMO_ACCOUNT: AccountProfile = {
  id: 'demo-account',
  email: DEMO_USER.email,
  display_name: DEMO_USER.name,
  role: 'admin',
  agent_id: DEMO_USER.id,
  agent_name: DEMO_USER.name,
  must_change_password: false,
  permissions: permissionsForRole('admin'),
}
