import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/shared/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * Placeholder pages make future areas explicit instead of showing blank
 * screens. Each describes exactly which phase delivers the feature.
 */

type Area =
  | 'analytics'
  | 'activity'
  | 'settings'
  | 'ticket_detail'

// eslint-disable-next-line react-refresh/only-export-components -- copy map is consumed only by the PlaceholderPage component
export const PLACEHOLDER_CONTENT: Record<
  Area,
  { title: string; phase: string; description: string; bullets: string[]; homeLabel: string; homeTo: string; backLabel?: string; backTo?: string }
> = {
  analytics: {
    title: 'Analytics',
    phase: 'Phase 3',
    description:
      'Team performance, response-time and resolution trends will live here.',
    bullets: [
      'Agent-level resolution and first-reply metrics',
      'Category and volume breakdowns over custom windows',
      'SLA attainment and escalation reports',
    ],
    homeLabel: 'Back to Overview',
    homeTo: '/',
  },
  activity: {
    title: 'Activity Logs',
    phase: 'Phase 2',
    description:
      'A searchable audit trail of every triage decision, reply and system action.',
    bullets: [
      'Filter by agent, ticket, action type and date range',
      'Automation events (classification, routing, escalations)',
      'Export for compliance review',
    ],
    homeLabel: 'Back to Overview',
    homeTo: '/',
  },
  settings: {
    title: 'Settings',
    phase: 'Phase 2',
    description:
      'Workspace configuration will be available once authentication ships.',
    bullets: [
      'Agents, roles and teams',
      'Routing rules and SLA targets',
      'Notification channels (email / messenger)',
    ],
    homeLabel: 'Back to Overview',
    homeTo: '/',
  },
  ticket_detail: {
    title: 'Ticket details',
    phase: 'Phase 2',
    description: 'The full conversation view, reply drafts and approvals.',
    bullets: [
      'Conversation timeline with internal notes',
      'AI-drafted customer replies with human approval flow',
      'Assignment, priority and category editing',
    ],
    homeLabel: 'Back to Overview',
    homeTo: '/',
    backLabel: 'Back to tickets',
    backTo: '/tickets',
  },
}

export function PlaceholderPage({ area }: { area: Area }) {
  const content = PLACEHOLDER_CONTENT[area]
  return (
    <div>
      <PageHeader
        title={content.title}
        description={`Planned for ${content.phase} — this area is intentionally not implemented yet.`}
      />
      <Card>
        <CardContent className="pt-4">
          <p className="text-sm text-foreground">{content.description}</p>
          <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground">
            {content.bullets.map((b) => (
              <li key={b} className="flex gap-2">
                <span aria-hidden="true" className="mt-2 size-1 shrink-0 rounded-full bg-border-strong" />
                {b}
              </li>
            ))}
          </ul>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to={content.homeTo} className={cn(buttonVariants({ variant: 'default', size: 'sm' }))}>
              {content.homeLabel}
            </Link>
            {content.backTo ? (
              <Link to={content.backTo} className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
                {content.backLabel}
              </Link>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
