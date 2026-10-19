import type { ReactNode } from 'react'
import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/misc'
import { cn } from '@/lib/utils'

/**
 * Loading, empty and error states, shared by ticket lists and dashboard
 * panels so future API integration gets consistent behaviour for free.
 */

/* ------------------------------ Loading ------------------------------ */

export function ListSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div role="status" aria-live="polite" aria-label="Loading tickets">
      <span className="sr-only">Loading…</span>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 flex-1 max-w-[38%]" />
            <Skeleton className="hidden h-4 w-24 sm:block" />
            <Skeleton className="hidden h-4 w-20 md:block" />
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-5 w-16" />
            <Skeleton className="hidden h-4 w-20 lg:block" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function PanelSkeleton({ lines = 6, className }: { lines?: number; className?: string }) {
  return (
    <div role="status" aria-busy="true" className={cn('space-y-2 p-4', className)}>
      <span className="sr-only">Loading…</span>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-4 w-full" style={{ maxWidth: `${58 + ((i * 17) % 42)}%` }} />
      ))}
    </div>
  )
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <span role="status" aria-live="polite" className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
      {label}
    </span>
  )
}

/* ------------------------------- Empty ------------------------------- */

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string
  description?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center px-6 py-10 text-center',
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="mb-3 flex size-10 items-center justify-center rounded-full bg-muted text-subtle-foreground"
      >
        <Inbox className="size-5" />
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? (
        <p className="mt-1 max-w-sm text-xs text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  )
}

/* ------------------------------- Error ------------------------------- */

export function ErrorState({
  title = 'Something went wrong',
  description = 'The data could not be loaded. Check your connection and try again.',
  onRetry,
  className,
}: {
  title?: string
  description?: string
  onRetry?: () => void
  className?: string
}) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center px-6 py-10 text-center',
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="mb-3 flex size-10 items-center justify-center rounded-full bg-danger-tint text-danger"
      >
        <AlertTriangle className="size-5" />
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-sm text-xs text-muted-foreground">{description}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  )
}
