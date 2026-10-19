import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default:
          'bg-primary text-primary-foreground hover:bg-primary-strong shadow-card',
        outline:
          'border border-input bg-card text-foreground hover:bg-muted shadow-card',
        secondary:
          'bg-primary-tint text-primary-strong hover:bg-primary-soft',
        ghost: 'text-muted-foreground hover:bg-muted hover:text-foreground',
        danger:
          'bg-danger text-white hover:bg-red-800 shadow-card',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-7 px-2.5 text-xs [&_svg]:size-3.5',
        default: 'h-8.5 px-3',
        lg: 'h-10 px-4',
        icon: 'size-8.5 p-0 [&_svg]:size-4',
        'icon-sm': 'size-7 p-0 [&_svg]:size-3.5',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'button'
  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- shadcn/ui convention: variants ship next to the component
export { Button, buttonVariants }
