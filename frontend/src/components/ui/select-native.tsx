import * as React from 'react'
import { cn } from '@/lib/utils'

/**
 * Native `<select>` styled like `Input`.
 *
 * Forms use the platform control (rather than the Radix popover) so a real
 * `<label htmlFor>` association, keyboard behaviour and mobile pickers work
 * without extra ARIA wiring. Filter toolbars keep using the Radix `Select`.
 */
function NativeSelect({
  className,
  ...props
}: React.ComponentProps<'select'>) {
  return (
    <select
      data-slot="native-select"
      className={cn(
        'flex h-8.5 w-full rounded-md border border-input bg-card px-2.5 py-1 text-sm text-foreground shadow-card transition-colors focus-visible:border-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export { NativeSelect }
