import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatShortDate } from '@/lib/format'
import { TREND_COLORS, TrendTooltip } from './chart-helpers'
import type { DashboardStats } from '@/types/ticket'

/**
 * Received vs resolved volume over the trailing window. A single legend
 * row lives above the chart; axes use short labels sized for density.
 */
export function VolumeTrendChart({ data }: { data: DashboardStats['receivedTrend'] }) {
  const points = data.map((d) => ({
    ...d,
    label: formatShortDate(`${d.date}T00:00:00`),
  }))

  return (
    <div>
      <ul className="mb-1 flex items-center gap-4 text-xs text-muted-foreground" aria-hidden="false">
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm" style={{ backgroundColor: TREND_COLORS.received }} />
          Received
        </li>
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2.5 rounded-sm" style={{ backgroundColor: TREND_COLORS.resolved }} />
          Resolved
        </li>
      </ul>
      <div className="h-56" role="img" aria-label={`Ticket volume trend: received and resolved per day over the last ${data.length} days`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 6, right: 8, bottom: 0, left: -22 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
              interval="preserveStartEnd"
              minTickGap={28}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
              tickLine={false}
              axisLine={false}
              width={34}
            />
            <Tooltip content={<TrendTooltip />} cursor={{ stroke: 'var(--border-strong)' }} />
            <Area
              type="monotone"
              name="Received"
              dataKey="received"
              stroke={TREND_COLORS.received}
              strokeWidth={2}
              fill="var(--primary-tint)"
              fillOpacity={0.85}
              activeDot={{ r: 3 }}
            />
            <Area
              type="monotone"
              name="Resolved"
              dataKey="resolved"
              stroke={TREND_COLORS.resolved}
              strokeWidth={2}
              fill="transparent"
              activeDot={{ r: 3 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
