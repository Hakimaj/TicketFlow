import * as React from 'react'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'

function Input({ className, type = 'text', ...props }: React.ComponentProps<'input'>) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        'flex h-8.5 w-full rounded-md border border-input bg-card px-2.5 py-1 text-sm text-foreground shadow-card transition-colors placeholder:text-subtle-foreground focus-visible:border-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

/** Search input with a leading icon; label comes from aria-label or <label>. */
function SearchInput({
  className,
  ...props
}: React.ComponentProps<typeof Input> & { 'aria-label': string }) {
  return (
    <div className={cn('relative w-full', className)}>
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-subtle-foreground"
      />
      <Input className="pl-8" {...props} />
    </div>
  )
}

export { Input, SearchInput }
