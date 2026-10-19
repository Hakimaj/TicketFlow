import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-2xs font-medium [&_svg]:size-3 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'border-border bg-muted text-foreground',
        outline: 'border-border bg-transparent text-muted-foreground',
        primary: 'border-primary-soft bg-primary-tint text-primary-strong',
        success: 'border-emerald-200 bg-success-tint text-success',
        warning: 'border-amber-200 bg-warning-tint text-warning',
        danger: 'border-red-200 bg-danger-tint text-danger',
        neutral: 'border-slate-200 bg-slate-100 text-slate-600',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- shadcn/ui convention: variants ship next to the component
export { Badge, badgeVariants }
