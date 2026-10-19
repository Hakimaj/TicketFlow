import type { Agent } from '@/types/ticket'

/**
 * Fictional support team roster for the demonstration dataset.
 * `AG-01` is the explicitly-labelled demo identity used for this phase —
 * there is no real authentication in Phase 1.
 */
export const DEMO_AGENTS: Agent[] = [
  {
    id: 'AG-01',
    name: 'Abebe Kebede',
    role: 'supervisor',
    team: 'customer_support',
    email: 'abebe.k@ticketflow.example',
    isDemoUser: true,
  },
  {
    id: 'AG-02',
    name: 'Hana Tesfaye',
    role: 'agent',
    team: 'billing_team',
    email: 'hana.t@ticketflow.example',
  },
  {
    id: 'AG-03',
    name: 'Dawit Mengistu',
    role: 'agent',
    team: 'logistics_team',
    email: 'dawit.m@ticketflow.example',
  },
  {
    id: 'AG-04',
    name: 'Selam Girma',
    role: 'agent',
    team: 'technical_support',
    email: 'selam.g@ticketflow.example',
  },
  {
    id: 'AG-05',
    name: 'Yonas Abate',
    role: 'agent',
    team: 'returns_team',
    email: 'yonas.a@ticketflow.example',
  },
  {
    id: 'AG-06',
    name: 'Meron Haile',
    role: 'agent',
    team: 'customer_support',
    email: 'meron.h@ticketflow.example',
  },
  {
    id: 'AG-07',
    name: 'Liya Tadesse',
    role: 'agent',
    team: 'customer_support',
    email: 'liya.t@ticketflow.example',
  },
  {
    id: 'AG-08',
    name: 'Bereket Solomon',
    role: 'admin',
    team: null,
    email: 'bereket.s@ticketflow.example',
  },
]

export const DEMO_AGENTS_BY_ID: ReadonlyMap<string, Agent> = new Map(
  DEMO_AGENTS.map((agent) => [agent.id, agent]),
)
