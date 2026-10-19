import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'
import { EmptyState } from '@/components/shared/states'
import { CATEGORY_COLORS, CategoryLegend } from './chart-helpers'
import type { DashboardStats } from '@/types/ticket'

/**
 * Open-ticket distribution by category as a restrained donut, paired with
 * an accessible legend that repeats the numbers in text (color is never
 * the only channel).
 */
export function CategoryDistributionChart({
  data,
}: {
  data: DashboardStats['categoryDistribution']
}) {
  const total = data.reduce((sum, entry) => sum + entry.count, 0)

  if (total === 0) {
    return (
      <EmptyState
        className="h-56"
        title="No open tickets by category"
        description="When active tickets exist, their category mix is shown here."
      />
    )
  }

  const chartData = data
    .filter((entry) => entry.count > 0)
    .map((entry) => ({
      name: entry.category,
      value: entry.count,
      fill: CATEGORY_COLORS[entry.category],
    }))

  return (
    <div className="flex flex-col items-center gap-2 sm:flex-row sm:items-center sm:gap-4">
      <div
        className="h-44 w-44 shrink-0"
        role="img"
        aria-label={`Distribution of ${total} open tickets by category`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius={48}
              outerRadius={72}
              paddingAngle={2}
              stroke="var(--card)"
              strokeWidth={1}
            >
              {chartData.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="w-full min-w-0">
        <p className="text-center text-xs text-muted-foreground sm:text-left">
          <span className="text-xl font-semibold text-foreground tabular-nums">{total}</span>{' '}
          open tickets by category
        </p>
        <CategoryLegend data={data} total={total} />
      </div>
    </div>
  )
}
