import { Link } from 'react-router-dom'
import { AlertOctagon, ChevronRight, CircleSlash, Inbox as InboxIcon, ShieldCheck, UserRoundCheck } from 'lucide-react'
import { PageHeader } from '@/components/shared/page-header'
import { MetricCard } from '@/components/shared/metric-card'
import { EmptyState, ErrorState, PanelSkeleton } from '@/components/shared/states'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { PrioritySummary, RecentActivity, RecentTickets } from './dashboard-panels'
import { VolumeTrendChart } from './volume-trend-chart'
import { CategoryDistributionChart } from './category-distribution-chart'
import { useDashboardStats } from './use-dashboard'

/**
 * Overview dashboard. Every number is derived from the demonstration
 * dataset through the TicketService — nothing on this screen is
 * hardcoded, and nothing pretends to update in real time.
 */
export function DashboardPage() {
  const { stats, loading, error, refetch } = useDashboardStats(30)

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Support operations at a glance. Derived from the demonstration dataset — no external services are connected."
      />

      {loading ? (
        <div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-[74px] rounded-lg border border-border bg-card shadow-card" aria-hidden="true" />
            ))}
          </div>
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2 min-h-[17.5rem]">
              <PanelSkeleton lines={8} />
            </Card>
            <Card className="min-h-[17.5rem]">
              <PanelSkeleton lines={8} />
            </Card>
          </div>
        </div>
      ) : error || !stats ? (
        <Card>
          <ErrorState
            title="Dashboard could not be loaded"
            description={error?.message}
            onRetry={refetch}
          />
        </Card>
      ) : (
        <>
          {/* Metric cards */}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Total open tickets"
              value={stats.openTickets}
              icon={InboxIcon}
              tone="primary"
              hint={{ text: 'View', href: '/tickets' }}
            />
            <MetricCard
              label="Unassigned tickets"
              value={stats.unassignedTickets}
              icon={CircleSlash}
              tone={stats.unassignedTickets > 0 ? 'default' : 'success'}
              hint={stats.unassignedTickets > 0 ? { text: 'Assign', href: '/tickets/unassigned' } : undefined}
            />
            <MetricCard
              label="High / urgent priority"
              value={stats.highPriorityOpen}
              icon={AlertOctagon}
              tone={stats.highPriorityOpen > 0 ? 'warning' : 'success'}
            />
            <MetricCard
              label="Needs review"
              value={stats.needsReviewTickets}
              icon={UserRoundCheck}
              tone={stats.needsReviewTickets > 0 ? 'danger' : 'success'}
              hint={stats.needsReviewTickets > 0 ? { text: 'Review', href: '/tickets/needs-review' } : undefined}
            />
          </div>

          {/* Pending Reply Approvals Banner */}
          {stats.pendingApprovals > 0 ? (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/40 bg-warning-tint/40 px-4 py-2.5 text-xs text-foreground shadow-xs">
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-4 shrink-0 text-warning" aria-hidden="true" />
                <span>
                  <strong className="font-semibold text-foreground">
                    {stats.pendingApprovals} customer {stats.pendingApprovals === 1 ? 'reply' : 'replies'}
                  </strong>{' '}
                  awaiting human supervisor review before sending.
                </span>
              </div>
              <Link
                to="/approvals"
                className="inline-flex items-center gap-1 font-semibold text-primary hover:underline"
              >
                Open Reply Approvals
                <ChevronRight className="size-3.5" aria-hidden="true" />
              </Link>
            </div>
          ) : null}

          {/* Charts row */}
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <div>
                  <CardTitle>Ticket volume</CardTitle>
                  <CardDescription>Received vs resolved per day, last 30 days (demo data)</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <VolumeTrendChart data={stats.receivedTrend} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Category distribution</CardTitle>
                  <CardDescription>Open tickets by category</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <CategoryDistributionChart data={stats.categoryDistribution} />
              </CardContent>
            </Card>
          </div>

          {/* Tables row */}
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <div>
                  <CardTitle>Recent tickets</CardTitle>
                  <CardDescription>Most recently received, across all queues</CardDescription>
                </div>
              </CardHeader>
              {stats.recentTickets.length > 0 ? (
                <>
                  <RecentTickets tickets={stats.recentTickets} />
                  <div className="border-t border-border px-4 py-2">
                    <Link
                      to="/tickets"
                      className="inline-flex items-center gap-1 rounded px-1 text-xs font-medium text-primary hover:underline focus:outline-none"
                    >
                      View all tickets
                      <ChevronRight aria-hidden="true" className="size-3.5" />
                    </Link>
                  </div>
                </>
              ) : (
                <CardContent>
                  <EmptyState
                    title="No recent tickets"
                    description="New tickets appear here as intake runs."
                  />
                </CardContent>
              )}
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <div>
                    <CardTitle>Open by priority</CardTitle>
                    <CardDescription>Active work across statuses</CardDescription>
                  </div>
                </CardHeader>
                <PrioritySummary data={stats.prioritySummary} />
              </Card>
              <Card>
                <CardHeader>
                  <div>
                    <CardTitle>Recent activity</CardTitle>
                    <CardDescription>Latest triage events (demo feed)</CardDescription>
                  </div>
                </CardHeader>
                {stats.recentActivity.length > 0 ? (
                  <RecentActivity activity={stats.recentActivity} />
                ) : (
                  <CardContent>
                    <p className="text-xs text-muted-foreground pb-2">
                      No activity recorded yet.
                    </p>
                  </CardContent>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
