import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * Compact numeric pagination used under the ticket table. Renders a short
 * page-number window so long lists stay out of the way of the data.
 */
export function Pagination({
  page,
  pageCount,
  total,
  pageSize,
  onPageChange,
  className,
}: {
  page: number
  pageCount: number
  total: number
  pageSize: number
  onPageChange: (page: number) => void
  className?: string
}) {
  if (total === 0) return null

  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)

  const pages: Array<number | 'ellipsis'> = []
  const window = 1
  for (let p = 1; p <= pageCount; p++) {
    if (p === 1 || p === pageCount || Math.abs(p - page) <= window) {
      pages.push(p)
    } else if (pages[pages.length - 1] !== 'ellipsis') {
      pages.push('ellipsis')
    }
  }

  return (
    <nav
      aria-label="Ticket pages"
      className={cn(
        'flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-2.5',
        className,
      )}
    >
      <p aria-live="polite" className="text-xs text-muted-foreground">
        Showing <span className="font-medium text-foreground">{from}–{to}</span> of{' '}
        <span className="font-medium text-foreground">{total}</span> tickets
      </p>
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="icon-sm"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft aria-hidden="true" />
        </Button>
        {pages.map((p, i) =>
          p === 'ellipsis' ? (
            <span key={`e${i}`} aria-hidden="true" className="px-1 text-xs text-subtle-foreground">
              …
            </span>
          ) : (
            <Button
              key={p}
              variant={p === page ? 'secondary' : 'ghost'}
              size="icon-sm"
              aria-current={p === page ? 'page' : undefined}
              aria-label={`Page ${p}`}
              onClick={() => p !== page && onPageChange(p)}
              className="text-xs"
            >
              {p}
            </Button>
          ),
        )}
        <Button
          variant="outline"
          size="icon-sm"
          aria-label="Next page"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight aria-hidden="true" />
        </Button>
      </div>
    </nav>
  )
}
