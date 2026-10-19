/**
 * Date/time display helpers. All formatting is done with the standard
 * library so no date library is needed for Phase 1.
 */

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

const shortDateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
})

const timeFormatter = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** "12 Oct 2026" */
export function formatDate(iso: string | Date): string {
  return dateFormatter.format(new Date(iso))
}

/** "12 Oct" */
export function formatShortDate(iso: string | Date): string {
  return shortDateFormatter.format(new Date(iso))
}

/** "14:32" (24h) */
export function formatTime(iso: string | Date): string {
  return timeFormatter.format(new Date(iso))
}

/** "12 Oct 2026, 14:32" */
export function formatDateTime(iso: string | Date): string {
  return `${formatDate(iso)}, ${formatTime(iso)}`
}

/**
 * Coarse relative time ("just now", "25m ago", "3h ago", "2d ago",
 * "12 Oct"). Used in tables and activity feeds. Computed on demand —
 * nothing refreshes on a timer or pretends to be live.
 */
export function formatRelativeTime(iso: string | Date, now = new Date()): string {
  const then = new Date(iso).getTime()
  const diffMs = now.getTime() - then
  const minutes = Math.round(diffMs / 60_000)

  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`

  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`

  const days = Math.round(hours / 24)
  if (days <= 30) return `${days}d ago`

  return formatShortDate(iso)
}

/** Key used to bucket tickets per day in trend charts: "2026-10-12". */
export function dayKey(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}
