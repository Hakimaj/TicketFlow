import * as React from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'
import { CheckIcon, ChevronDownIcon, ChevronUpIcon, X } from 'lucide-react'
import { cn } from '@/lib/utils'

/*
 * Radix-based select for filter controls. Values are string tokens; an
 * optional `clearValue` renders a "clear" choice used by the ticket filters.
 */

const Select = SelectPrimitive.Root
const SelectGroup = SelectPrimitive.Group
const SelectValue = SelectPrimitive.Value

function SelectTrigger({
  className,
  children,
  withReset,
  onReset,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Trigger> & {
  withReset?: boolean
  onReset?: () => void
}) {
  return (
    <div className="relative inline-flex w-full">
      <SelectPrimitive.Trigger
        data-slot="select-trigger"
        className={cn(
          'flex h-8.5 w-full items-center justify-between gap-1.5 rounded-md border border-input bg-card px-2.5 py-1 text-sm text-foreground shadow-card transition-colors hover:bg-muted focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 aria-[expanded=true]:border-primary [&_span]:truncate',
          className,
        )}
        {...props}
      >
        {children}
        <SelectPrimitive.Icon asChild>
          <ChevronDownIcon aria-hidden="true" className="size-3.5 shrink-0 text-subtle-foreground" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      {withReset && onReset ? (
        <button
          type="button"
          aria-label="Clear selection"
          onClick={(event) => {
            event.stopPropagation()
            onReset()
          }}
          className="absolute right-6 top-1/2 -translate-y-1/2 rounded p-0.5 text-subtle-foreground hover:bg-muted hover:text-foreground focus:outline-none"
        >
          <X aria-hidden="true" className="size-3" />
        </button>
      ) : null}
    </div>
  )
}

function SelectContent({
  className,
  children,
  position = 'popper',
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        data-slot="select-content"
        position={position}
        className={cn(
          'relative z-50 max-h-[22rem] min-w-[9rem] overflow-hidden rounded-md border border-border bg-card text-sm shadow-pop',
          position === 'popper' && 'max-h-[min(22rem,var(--radix-select-content-available-height))]',
          className,
        )}
        {...props}
      >
        <SelectPrimitive.ScrollUpButton className="flex h-6 items-center justify-center text-subtle-foreground">
          <ChevronUpIcon className="size-3.5" />
        </SelectPrimitive.ScrollUpButton>
        <SelectPrimitive.Viewport
          className={cn('p-1', position === 'popper' && 'w-full min-w-[var(--radix-select-trigger-width)]')}
        >
          {children}
        </SelectPrimitive.Viewport>
        <SelectPrimitive.ScrollDownButton className="flex h-6 items-center justify-center text-subtle-foreground">
          <ChevronDownIcon className="size-3.5" />
        </SelectPrimitive.ScrollDownButton>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  )
}

function SelectItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        'relative flex w-full cursor-default items-center gap-2 rounded-sm py-1.5 pl-7 pr-2.5 text-sm outline-none select-none focus:bg-primary-tint data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        className,
      )}
      {...props}
    >
      <span className="absolute left-2 flex size-3.5 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <CheckIcon aria-hidden="true" className="size-3.5 text-primary" />
        </SelectPrimitive.ItemIndicator>
      </span>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  )
}

function SelectLabel({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.Label>) {
  return (
    <SelectPrimitive.Label
      className={cn('px-2 py-1.5 text-2xs font-semibold text-subtle-foreground uppercase tracking-wide', className)}
      {...props}
    />
  )
}

function SelectSeparator({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.Separator>) {
  return <SelectPrimitive.Separator className={cn('-mx-1 my-1 h-px bg-border', className)} {...props} />
}

export {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectLabel,
  SelectSeparator,
  SelectItem,
}
