import type { Agent } from '@/types/ticket'
import { DEMO_AGENTS } from './demo-agents'
import { DEMO_AGENTS_BY_ID } from './demo-agents'

/**
 * The demo identity shown in the header and sidebar. Phase 1 has no
 * authentication — this profile is intentionally hard-coded and labelled as
 * a demo user in the UI.
 */
export const DEMO_USER: Agent = DEMO_AGENTS_BY_ID.get('AG-01') ?? DEMO_AGENTS[0]
