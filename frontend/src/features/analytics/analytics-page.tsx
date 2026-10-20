import * as React from 'react'
import {
  AlertTriangle,
  BellRing,
  CheckCircle2,
  Clock,
  Inbox,
  ShieldCheck,
  Ticket,
  UserRoundX,
} from 'lucide-react'
import { PageHeader } from '@/components/shared/page-header'
import { MetricCard } from '@/components/shared/metric-card'
import { ErrorState, PanelSkeleton, Spinner } from '@/components/shared/states'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { CategoryDistributionChart } from '@/features/dashboard/category-distribution-chart'
import { VolumeTrendChart } from '@/features/dashboard/volume-trend-chart'
import { CATEGORY_COLORS } from '@/lib/chart-colors'
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
} from '@/lib/ticket-config'
import { formatDate, formatDateTime } from '@/lib/format'
import { REPLY_STATE_LABELS } from '@/types/reply'
import type { AnalyticsRange } from '@/types/analytics'
import { cn } from '@/lib/utils'
import { HorizontalBarChart } from './analytics-charts'
import {
  priorityBarData,
  replyStateBarData,
  statusBarData,
} from './analytics-chart-data'
import { useAnalytics } from './use-analytics'

const RANGE_OPTIONS: Array<{ value: AnalyticsRange; label: string }> = [
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 'all', label: 'All data' },
]

function rangeLabel(range: AnalyticsRange): string {
  return range === 'all' ? 'all data' : `last ${range} days`
}

/**
 * Support-operations analytics. Every figure is derived by the shared service
 * from the current in-memory tickets/replies; there are no invented
 * historical snapshots, SLA or CSAT values.
 */
export function AnalyticsPage() {
  const [range, setRange] = React.useState<AnalyticsRange>(30)
  const { stats, loading, error, reload } = useAnalytics(range)

  return (
    <div className="space-y-5">
      <PageHeader
        title="Analytics"
        description="Operational metrics derived from the current TicketFlow demo tickets and customer replies."
        actions={
          <div
            className="flex items-center gap-1 rounded-md border border-border bg-card p-0.5 shadow-card"
            role="group"
            aria-label="Analytics date range"
          >
            {RANGE_OPTIONS.map((option) => (
              <Button
                key={String(option.value)}
                type="button"
                size="sm"
                variant={range === option.value ? 'secondary' : 'ghost'}
                aria-pressed={range === option.value}
                onClick={() => setRange(option.value)}
                className={cn(
                  'rounded-sm',
                  range === option.value && 'text-primary-strong',
                )}
              >
                {option.label}
              </Button>
            ))}
          </div>
        }
      />

      {error && !stats ? (
        <Card>
          <CardContent className="pt-4">
            <ErrorState
              title="Analytics could not be loaded"
              description="The shared demo service did not return analytics data."
              onRetry={reload}
            />
          </CardContent>
        </Card>
      ) : loading && !stats ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Card key={index}>
              <PanelSkeleton lines={2} className="py-4" />
            </Card>
          ))}
        </div>
      ) : stats ? (
        <>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Clock aria-hidden="true" className="size-3.5" />
              Creation window: {formatDate(stats.rangeStart)} – {formatDate(stats.generatedAt)}
            </span>
            <span aria-hidden="true">·</span>
            <span>
              {stats.totalTickets} tickets and {stats.totalReplies} customer replies in the demo dataset
            </span>
            {loading ? <Spinner label="Updating…" /> : null}
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <MetricCard
              label={`Tickets created · ${rangeLabel(range)}`}
              value={stats.ticketsCreatedInRange}
              icon={Ticket}
              tone="primary"
              hint={{ text: 'All tickets', href: '/tickets' }}
            />
            <MetricCard
              label="Active workload · current"
              value={stats.activeTickets}
              icon={Inbox}
              hint={{
                text: 'Queue',
                href: '/tickets?status=new,open,pending',
              }}
            />
            <MetricCard
              label="Unassigned active · current"
              value={stats.unassignedTickets}
              icon={UserRoundX}
              tone={stats.unassignedTickets > 0 ? 'warning' : 'success'}
              hint={
                stats.unassignedTickets > 0
                  ? { text: 'Assign', href: '/tickets/unassigned' }
                  : undefined
              }
            />
            <MetricCard
              label="Urgent & high active · current"
              value={stats.urgentHighTickets}
              icon={AlertTriangle}
              tone={stats.urgentHighTickets > 0 ? 'danger' : 'success'}
              hint={{ text: 'Filter', href: '/tickets?priority=urgent,high' }}
            />
            <MetricCard
              label="Needs review (ticket-level) · current"
              value={stats.needsReviewTickets}
              icon={BellRing}
              tone={stats.needsReviewTickets > 0 ? 'warning' : 'success'}
              hint={
                stats.needsReviewTickets > 0
                  ? { text: 'Review', href: '/tickets/needs-review' }
                  : undefined
              }
            />
            <MetricCard
              label="Replies awaiting approval · current"
              value={stats.pendingReplyApprovals}
              icon={ShieldCheck}
              tone={stats.pendingReplyApprovals > 0 ? 'warning' : 'success'}
              hint={
                stats.pendingReplyApprovals > 0
                  ? { text: 'Approve', href: '/approvals' }
                  : undefined
              }
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <div>
                  <CardTitle>Ticket volume</CardTitle>
                  <CardDescription>
                    Created by ticket timestamp; resolved/closed by latest update
                    timestamp (the dataset has no separate resolution event time).
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <VolumeTrendChart
                  data={stats.volumeTrend.map((point) => ({
                    date: point.date,
                    received: point.created,
                    resolved: point.resolved,
                  }))}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Reply approval workflow</CardTitle>
                  <CardDescription>
                    Current state of every customer reply record.
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <HorizontalBarChart
                  data={replyStateBarData(
                    stats.replyStateDistribution,
                    REPLY_STATE_LABELS,
                  )}
                  ariaLabel="Customer replies by approval state"
                  valueLabel="Replies"
                  emptyTitle="No customer replies yet"
                  emptyDescription="Reply drafts and approvals will appear here once agents start composing."
                  labelWidth={112}
                />
                <p className="border-t border-border pt-2 text-xs text-muted-foreground">
                  {stats.repliesCreatedInRange} created in this window ·{' '}
                  {stats.sentRepliesInRange} demo-sent in this window
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Status distribution</CardTitle>
                  <CardDescription>All tickets, current status.</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <HorizontalBarChart
                  data={statusBarData(stats.statusDistribution, STATUS_LABELS)}
                  ariaLabel="All tickets by current status"
                  valueLabel="Tickets"
                  emptyTitle="No tickets"
                  emptyDescription="Status distribution appears when tickets exist."
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Priority mix</CardTitle>
                  <CardDescription>
                    Active tickets (New, Open, Pending).
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <HorizontalBarChart
                  data={priorityBarData(
                    stats.priorityDistribution,
                    PRIORITY_LABELS,
                  )}
                  ariaLabel="Active tickets by priority"
                  valueLabel="Tickets"
                  emptyTitle="No active tickets"
                  emptyDescription="Priority distribution appears when active tickets exist."
                  labelWidth={84}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Category mix</CardTitle>
                  <CardDescription>Active tickets by support category.</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <CategoryDistributionChart data={stats.categoryDistribution} />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <div>
                  <CardTitle>Workload by assignee</CardTitle>
                  <CardDescription>
                    Current active tickets per agent, including the unassigned
                    bucket. A zero-workload agent has no bar.
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <HorizontalBarChart
                  data={stats.agentWorkload.map((row) => ({
                    key: row.agentId ?? '__unassigned',
                    label: row.agentName,
                    value: row.count,
                    color:
                      row.agentId === null ? '#94a3b8' : 'var(--primary)',
                  }))}
                  ariaLabel="Active tickets by assigned agent"
                  valueLabel="Active tickets"
                  emptyTitle="No active tickets"
                  emptyDescription="When tickets are active, their assignment split is shown here."
                  labelWidth={132}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Definitions &amp; limits</CardTitle>
                  <CardDescription>How to read these figures honestly.</CardDescription>
                </div>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs text-muted-foreground">
                <p>
                  <span className="font-medium text-foreground">Date range</span>{' '}
                  filters ticket creation, reply creation and demo-send timestamps.
                  Status, priority, category, workload and reply-state charts show
                  current state, not historical snapshots.
                </p>
                <p>
                  <span className="font-medium text-foreground">Needs Review</span>{' '}
                  counts ticket triage status only. Reply approvals are counted
                  separately and are never mixed into that number.
                </p>
                <p>
                  <span className="font-medium text-foreground">No invented KPIs.</span>{' '}
                  The demo has no SLA, resolution-duration, CSAT or revenue history,
                  so none is shown.
                </p>
                <p>
                  Data is in-memory and resets on reload. Figures update live from
                  the shared service when tickets or replies change.
                </p>
                <p className="flex items-center gap-1.5 border-t border-border pt-2 text-success">
                  <CheckCircle2 aria-hidden="true" className="size-3.5" />
                  Derived from {stats.totalTickets} tickets · last updated{' '}
                  {formatDateTime(stats.generatedAt)}
                </p>
                <p className="flex items-center gap-1.5 text-2xs text-subtle-foreground">
                  <span
                    aria-hidden="true"
                    className="inline-block size-2 rounded-full"
                    style={{ backgroundColor: CATEGORY_COLORS.billing }}
                  />
                  Chart colors mirror ticket badges; labels repeat every value.
                </p>
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  )
}
