import type { ReactNode } from 'react'

/**
 * Page header with breadcrumb and primary action slot. Kebpt deliberately
 * compact: title + description + one action row.
 */
export function PageHeader({
  breadcrumb,
  title,
  description,
  actions,
}: {
  breadcrumb?: ReactNode
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="mb-5">
      {breadcrumb ? (
        <nav aria-label="Breadcrumb" className="mb-1 text-xs text-muted-foreground">
          {breadcrumb}
        </nav>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {description ? (
            <p className="mt-0.5 max-w-2xl text-sm text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  )
}
