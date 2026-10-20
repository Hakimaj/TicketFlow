import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

/**
 * Small dashboard metric card: icon, label, value, optional hint link.
 * Values are always passed in by the dashboard (derived from the dataset) —
 * nothing is hardcoded here.
 */
export function MetricCard({
  label,
  value,
  icon: Icon,
  hint,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  /** Icon component; given an aria-hidden render below. */
  icon: React.ComponentType<{ className?: string }>
  hint?: { text: string; href?: string; onClick?: () => void }
  tone?: 'default' | 'primary' | 'warning' | 'danger' | 'success'
}) {
  const toneClass = {
    default: 'bg-slate-100 text-slate-600',
    primary: 'bg-primary-tint text-primary-strong',
    warning: 'bg-warning-tint text-warning',
    danger: 'bg-danger-tint text-danger',
    success: 'bg-success-tint text-success',
  }[tone]

  const hintClass =
    'shrink-0 rounded px-1.5 py-1 text-xs font-medium text-primary hover:bg-primary-tint focus:outline-none'
  const accessibleLabel =
    typeof value === 'string' || typeof value === 'number'
      ? `${label}: ${value}`
      : label

  return (
    <div
      role="group"
      aria-label={accessibleLabel}
      className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3.5 shadow-card"
    >
      <span
        aria-hidden="true"
        className={cn(
          'flex size-10 shrink-0 items-center justify-center rounded-md [&_svg]:size-5',
          toneClass,
        )}
      >
        <Icon />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-3xl font-semibold leading-8 tracking-tight text-foreground tabular-nums">
          {value}
        </div>
        <div className="truncate text-xs font-medium text-muted-foreground">
          {label}
        </div>
      </div>
      {hint ? (
        hint.href?.startsWith('/') ? (
          <Link to={hint.href} className={hintClass} aria-label={hint.text}>
            {hint.text}
          </Link>
        ) : hint.href ? (
          <a href={hint.href} className={hintClass} aria-label={hint.text}>
            {hint.text}
          </a>
        ) : (
          <button
            type="button"
            onClick={hint.onClick}
            className={hintClass}
            aria-label={hint.text}
          >
            {hint.text}
          </button>
        )
      ) : null}
    </div>
  )
}
