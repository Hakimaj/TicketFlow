import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EmptyState } from '@/components/shared/states'
import type { BarDatum } from './analytics-chart-data'

/**
 * Accessible horizontal count chart used for every categorical analytics
 * breakdown. Every bar has a text label, the tooltip repeats the number, and
 * the wrapper exposes a full text summary for screen readers.
 */

function CountTooltip({
  active,
  payload,
  label,
  valueLabel,
}: {
  active?: boolean
  payload?: Array<{ value?: number | string }>
  label?: string | number
  valueLabel: string
}) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-md border border-border bg-card px-2.5 py-1.5 text-xs shadow-pop">
      <p className="font-medium text-foreground">{label}</p>
      <p className="text-muted-foreground">
        {valueLabel}:{' '}
        <span className="font-medium tabular-nums text-foreground">
          {payload[0]?.value}
        </span>
      </p>
    </div>
  )
}

export function HorizontalBarChart({
  data,
  ariaLabel,
  valueLabel,
  emptyTitle,
  emptyDescription,
  labelWidth = 108,
}: {
  data: BarDatum[]
  ariaLabel: string
  valueLabel: string
  emptyTitle: string
  emptyDescription: string
  labelWidth?: number
}) {
  const total = data.reduce((sum, row) => sum + row.value, 0)

  if (total === 0) {
    return (
      <EmptyState
        className="h-40"
        title={emptyTitle}
        description={emptyDescription}
      />
    )
  }

  const height = Math.max(150, data.length * 34 + 24)
  const description = data
    .map((row) => `${row.label}: ${row.value}`)
    .join('; ')

  return (
    <div role="img" aria-label={`${ariaLabel}. ${description}`}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 18, bottom: 4, left: 0 }}
          barCategoryGap={8}
        >
          <CartesianGrid horizontal={false} stroke="var(--border)" />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={labelWidth}
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: 'var(--muted)' }}
            content={<CountTooltip valueLabel={valueLabel} />}
          />
          <Bar dataKey="value" name={valueLabel} radius={[0, 3, 3, 0]} barSize={14}>
            {data.map((row) => (
              <Cell key={row.key} fill={row.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
