import {
  ArrowRight,
  CheckCircle2,
  Database,
  LockKeyhole,
  MailX,
  Monitor,
  RotateCcw,
  ServerOff,
  ShieldCheck,
  UserRound,
  Workflow,
} from 'lucide-react'
import { PageHeader } from '@/components/shared/page-header'
import { Avatar } from '@/components/ui/misc'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '@/auth'
import {
  ACCOUNT_ROLE_LABELS,
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
  TICKET_STATUSES,
} from '@/lib/ticket-config'
import { REPLY_STATE_LABELS, REPLY_STATES } from '@/types/reply'
import { cn } from '@/lib/utils'
import {
  LANDING_OPTIONS,
  usePreferences,
  type Density,
  type LandingPath,
} from '@/lib/preferences'

function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

const DENSITY_OPTIONS: Array<{
  value: Density
  title: string
  description: string
}> = [
  {
    value: 'comfortable',
    title: 'Comfortable',
    description: 'Default row spacing across all tables.',
  },
  {
    value: 'compact',
    title: 'Compact',
    description: 'Tighter rows for scanning long queues.',
  },
]

const WORKING_NOW = [
  {
    title: 'Session & role checks',
    detail: 'Sign-in, refresh rotation, sign-out and server-side role enforcement run through the TicketFlow API.',
  },
  {
    title: 'Persistent ticket & reply workflow',
    detail: 'Triage, internal notes, reply revisions, approvals and demo sends are stored in PostgreSQL.',
  },
  {
    title: 'Human approval gate',
    detail: 'The API rejects sending unless the exact current reply version was approved by a different account.',
  },
  {
    title: 'Local interface preferences',
    detail: 'Density and start page are stored only in this browser and never leave this device.',
  },
]

const LIMITATIONS = [
  {
    title: 'No real message delivery',
    detail: '“Send” records a simulated demo action. No customer is contacted and no messaging provider is configured.',
  },
  {
    title: 'Sign-in throttling is per process',
    detail: 'Failed sign-in attempts are limited in API memory. A multi-instance deployment needs a shared limiter.',
  },
  {
    title: 'New-ticket intake',
    detail: 'Creating tickets from the workspace is not implemented; tickets arrive through the seeded intake.',
  },
  {
    title: 'Notification rules',
    detail: 'There is no email or push notification service; workflow changes are visible in Activity Logs.',
  },
]

export function SettingsPage() {
  const { user, isDemo } = useAuth()
  const displayName = user?.display_name ?? 'Signed out'
  const { preferences, setDensity, setDefaultLanding, resetPreferences } =
    usePreferences()
  const isDefault =
    preferences.density === 'comfortable' && preferences.defaultLanding === '/'

  return (
    <div className="space-y-5">
      <PageHeader
        title="Settings"
        description="Your session, local interface preferences, and an honest view of what this workspace does and does not do."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* ------------------------------ Profile ------------------------------ */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <div>
              <CardTitle>Signed-in account</CardTitle>
              <CardDescription>
                {isDemo ? 'Local demonstration identity' : 'Verified by the API session'}
              </CardDescription>
            </div>
            <UserRound aria-hidden="true" className="size-4 text-subtle-foreground" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <Avatar initials={initials(displayName)} size="lg" />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">
                  {displayName}
                </p>
                <p className="text-xs text-muted-foreground">
                  {user ? ACCOUNT_ROLE_LABELS[user.role] : 'No session'} ·{' '}
                  {user?.agent_name ?? 'No linked agent'}
                </p>
              </div>
            </div>
            <dl className="space-y-2 border-t border-border pt-3 text-xs">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted-foreground">Agent ID</dt>
                <dd className="font-medium tabular-nums text-foreground">
                  {user?.agent_id ?? '—'}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="truncate font-medium text-foreground">
                  {user?.email ?? '—'}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted-foreground">Session</dt>
                <dd>
                  <Badge variant={isDemo ? 'warning' : 'success'}>
                    {isDemo ? 'Demo mode' : 'Authenticated'}
                  </Badge>
                </dd>
              </div>
            </dl>
            <p className="rounded-md bg-card-muted px-3 py-2 text-xs text-muted-foreground">
              {isDemo
                ? 'Demo mode runs entirely in the browser with sample data and never contacts a backend.'
                : 'Access tokens stay in this tab’s memory. The refresh session is an HttpOnly cookie, and roles are enforced by the API on every request.'}
            </p>
          </CardContent>
        </Card>

        {/* --------------------------- Preferences --------------------------- */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Interface preferences</CardTitle>
              <CardDescription>
                Saved in this browser only — they are never sent to a server.
              </CardDescription>
            </div>
            <Monitor aria-hidden="true" className="size-4 text-subtle-foreground" />
          </CardHeader>
          <CardContent className="space-y-5">
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-foreground">
                Table density
              </legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {DENSITY_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={cn(
                      'flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors',
                      preferences.density === option.value
                        ? 'border-primary bg-primary-tint/60'
                        : 'border-border bg-card hover:bg-muted/60',
                    )}
                  >
                    <input
                      type="radio"
                      name="density"
                      value={option.value}
                      checked={preferences.density === option.value}
                      onChange={() => setDensity(option.value)}
                      className="mt-0.5 size-3.5 accent-primary"
                    />
                    <span>
                      <span className="block text-sm font-medium text-foreground">
                        {option.title}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {option.description}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="grid gap-2">
              <Label htmlFor="default-landing">Default landing page</Label>
              <Select
                value={preferences.defaultLanding}
                onValueChange={(value) => setDefaultLanding(value as LandingPath)}
              >
                <SelectTrigger id="default-landing" className="w-full sm:max-w-xs">
                  <SelectValue placeholder="Choose a start page" />
                </SelectTrigger>
                <SelectContent>
                  {LANDING_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Applied the next time the app starts at <code>/</code> in a new
                tab or reload. Sidebar links always navigate normally.
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
              <Badge variant="success" className="gap-1">
                <CheckCircle2 aria-hidden="true" />
                Saved locally in this browser
              </Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={resetPreferences}
                disabled={isDefault}
              >
                <RotateCcw aria-hidden="true" />
                Reset preferences
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* ----------------------------- Workflow ----------------------------- */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Configured workflow</CardTitle>
              <CardDescription>
                Read-only values derived from the application&apos;s domain types.
              </CardDescription>
            </div>
            <Workflow aria-hidden="true" className="size-4 text-subtle-foreground" />
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <h3 className="mb-1.5 text-xs font-medium text-foreground">
                Ticket statuses
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {TICKET_STATUSES.map((status) => (
                  <Badge key={status} variant="outline">
                    {STATUS_LABELS[status]}
                  </Badge>
                ))}
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground">
                <strong className="font-medium text-foreground">Needs Review</strong>{' '}
                is ticket-level triage. It is separate from reply approval and is
                never counted as a pending reply.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <h3 className="mb-1.5 text-xs font-medium text-foreground">
                  Priority levels
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {TICKET_PRIORITIES.map((priority) => (
                    <Badge key={priority} variant="outline">
                      {PRIORITY_LABELS[priority]}
                    </Badge>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="mb-1.5 text-xs font-medium text-foreground">
                  Ticket categories
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {TICKET_CATEGORIES.map((category) => (
                    <Badge key={category} variant="outline">
                      {CATEGORY_LABELS[category]}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <h3 className="mb-1.5 text-xs font-medium text-foreground">
                Reply approval states
              </h3>
              <ol className="flex flex-wrap items-center gap-1.5">
                {REPLY_STATES.map((state, index) => (
                  <li key={state} className="flex items-center gap-1.5">
                    {index > 0 ? (
                      <ArrowRight
                        aria-hidden="true"
                        className="size-3 text-subtle-foreground"
                      />
                    ) : null}
                    <Badge variant={state === 'sent' ? 'success' : 'outline'}>
                      {REPLY_STATE_LABELS[state]}
                    </Badge>
                  </li>
                ))}
              </ol>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Editing an approved or pending reply increments its version and
                invalidates prior approval. Resubmission and a new reviewer
                decision are required.
              </p>
            </div>

            <div className="rounded-md border border-primary-soft bg-primary-tint/60 px-3 py-2.5 text-xs text-muted-foreground">
              <p className="flex items-center gap-1.5 font-medium text-foreground">
                <ShieldCheck aria-hidden="true" className="size-3.5 text-primary" />
                Human approval is mandatory before demo sending
              </p>
              <p className="mt-1">
                Approval never sends automatically. A separate, explicit demo-send
                action is required; the service rejects the transition when the
                current version is not approved. No message leaves TicketFlow.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* ------------------------ Integration status ------------------------ */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Integration status</CardTitle>
              <CardDescription>What works today</CardDescription>
            </div>
            <ServerOff aria-hidden="true" className="size-4 text-subtle-foreground" />
          </CardHeader>
          <CardContent className="space-y-4">
            <section aria-labelledby="working-now-heading">
              <h3
                id="working-now-heading"
                className="mb-2 flex items-center gap-1.5 text-xs font-medium text-foreground"
              >
                <CheckCircle2 aria-hidden="true" className="size-3.5 text-success" />
                Working now
              </h3>
              <ul className="space-y-2">
                {WORKING_NOW.map((item) => (
                  <li key={item.title} className="text-xs">
                    <p className="font-medium text-foreground">{item.title}</p>
                    <p className="text-muted-foreground">{item.detail}</p>
                  </li>
                ))}
              </ul>
            </section>

            <section aria-labelledby="needs-backend-heading" className="border-t border-border pt-3">
              <h3
                id="needs-backend-heading"
                className="mb-2 flex items-center gap-1.5 text-xs font-medium text-foreground"
              >
                <Database aria-hidden="true" className="size-3.5 text-warning" />
                Deliberate limitations
              </h3>
              <ul className="space-y-2">
                {LIMITATIONS.map((item) => (
                  <li key={item.title} className="text-xs">
                    <p className="font-medium text-foreground">{item.title}</p>
                    <p className="text-muted-foreground">{item.detail}</p>
                  </li>
                ))}
              </ul>
            </section>

            <p className="flex items-start gap-1.5 rounded-md bg-card-muted px-3 py-2 text-xs text-muted-foreground">
              <LockKeyhole aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              No credential is ever stored in the browser, and this page has no
              Connect or Test Connection controls.
            </p>
            <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
              <MailX aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              Sending is simulated for demonstration only.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
