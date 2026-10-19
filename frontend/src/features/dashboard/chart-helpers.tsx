import { formatShortDate } from '@/lib/format'
import { CATEGORY_LABELS, CATEGORY_TEAM, TEAM_LABELS } from '@/lib/ticket-config'
import type { DashboardStats, TicketCategory } from '@/types/ticket'

/**
 * Shared chart palette and tooltip helpers. Original TicketFlow palette:
 * one blue-teal family plus neutral support colors — no rainbow charts.
 */

export const TREND_COLORS = {
  received: 'var(--primary)',
  resolved: '#0d9488', // teal-600, restrained complement
} as const

// eslint-disable-next-line react-refresh/only-export-components -- palette constants are only used with these chart components
export const CATEGORY_COLORS: Record<TicketCategory, string> = {
  billing: '#2563eb', // primary blue
  delivery: '#0d9488', // teal
  technical: '#7c3aed', // muted violet
  returns: '#d97706', // amber
  general: '#64748b', // slate
}

export function TrendTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{
    name?: string
    value?: number | string
    color?: string
  }>
  label?: string | number
}) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-md border border-border bg-card px-2.5 py-1.5 text-xs shadow-pop">
      <p className="font-medium text-foreground">{formatShortDate(String(label))}</p>
      {payload.map((entry) => (
        <p key={String(entry.name)} className="flex items-center gap-1.5 text-muted-foreground">
          <span
            aria-hidden="true"
            className="inline-block size-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          {entry.name}: <span className="font-medium text-foreground">{entry.value}</span>
        </p>
      ))}
    </div>
  )
}

export function CategoryLegend({
  data,
  total,
}: {
  data: DashboardStats['categoryDistribution']
  total: number
}) {
  return (
    <ul className="mt-1 space-y-1.5 text-xs">
      {data.map((entry) => {
        const pct = total > 0 ? Math.round((entry.count / total) * 100) : 0
        return (
          <li key={entry.category} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="inline-block size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: CATEGORY_COLORS[entry.category] }}
            />
            <span className="min-w-0 flex-1 truncate text-muted-foreground">
              {CATEGORY_LABELS[entry.category]}
              <span className="ml-1 text-2xs text-subtle-foreground">
                ({TEAM_LABELS[CATEGORY_TEAM[entry.category]]})
              </span>
            </span>
            <span className="tabular-nums text-foreground">
              {entry.count}
              <span className="ml-1 text-subtle-foreground">{pct}%</span>
            </span>
          </li>
        )
      })}
    </ul>
  )
}
