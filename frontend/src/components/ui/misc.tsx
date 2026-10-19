import * as React from 'react'
import * as AvatarPrimitive from '@radix-ui/react-avatar'
import * as SeparatorPrimitive from '@radix-ui/react-separator'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/* Avatar with initials fallback (no image assets needed in Phase 1). */

const avatarSizes = cva('overflow-hidden rounded-full border border-border', {
  variants: {
    size: {
      sm: 'size-6 text-2xs',
      default: 'size-8 text-xs',
      lg: 'size-9 text-sm',
    },
  },
  defaultVariants: { size: 'default' },
})

interface AvatarProps
  extends React.ComponentProps<typeof AvatarPrimitive.Root>,
    VariantProps<typeof avatarSizes> {
  initials: string
  fallbackClassName?: string
}

const AVATAR_PALETTE = [
  'bg-blue-100 text-blue-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-violet-100 text-violet-700',
  'bg-rose-100 text-rose-700',
  'bg-teal-100 text-teal-700',
] as const

function initialsToIndex(initials: string): number {
  let hash = 0
  for (const ch of initials) hash = (hash * 31 + ch.charCodeAt(0)) % 997
  return hash % AVATAR_PALETTE.length
}

function Avatar({ initials, size, className, ...props }: AvatarProps) {
  return (
    <AvatarPrimitive.Root className={cn(avatarSizes({ size }), className)} {...props}>
      <AvatarPrimitive.Fallback
        className={cn('flex size-full items-center justify-center font-semibold', AVATAR_PALETTE[initialsToIndex(initials)])}
        delayMs={0}
      >
        {initials}
      </AvatarPrimitive.Fallback>
    </AvatarPrimitive.Root>
  )
}

/* Separator */

function Separator({
  className,
  orientation = 'horizontal',
  ...props
}: React.ComponentProps<typeof SeparatorPrimitive.Root>) {
  return (
    <SeparatorPrimitive.Root
      decorative
      orientation={orientation}
      className={cn(
        'shrink-0 bg-border',
        orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px',
        className,
      )}
      {...props}
    />
  )
}

/* Skeleton */

function Skeleton({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-none rounded bg-muted', className)}
      {...props}
    />
  )
}

export { Avatar, Separator, Skeleton }
