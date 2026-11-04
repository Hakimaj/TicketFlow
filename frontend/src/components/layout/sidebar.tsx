import { NavLink, useNavigate } from 'react-router-dom'
import { CircleUserRound, LogOut, Settings, UserRound } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar } from '@/components/ui/misc'
import { ACCOUNT_ROLE_LABELS } from '@/lib/ticket-config'
import { useAuth } from '@/auth'
import { NAV_ITEMS, type NavCounts } from './nav-config'
import { cn } from '@/lib/utils'

/* ------------------------------------------------------------------ */
/* Shared pieces                                                       */
/* ------------------------------------------------------------------ */

function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

/** Optional sidebar badge counters (re-exported from nav-config). */
export type { NavCounts } from './nav-config'

export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-2', className)}>
      <svg
        aria-hidden="true"
        viewBox="0 0 32 32"
        className="size-7 shrink-0"
      >
        <rect x="2" y="6" width="28" height="20" rx="4" fill="#2563eb" />
        <circle cx="2.5" cy="16" r="2.5" fill="#ffffff" />
        <circle cx="29.5" cy="16" r="2.5" fill="#ffffff" />
        <rect x="8" y="11" width="16" height="2.5" rx="1.25" fill="#ffffff" opacity="0.95" />
        <rect x="8" y="16" width="11" height="2.5" rx="1.25" fill="#ffffff" opacity="0.8" />
        <rect x="8" y="21" width="14" height="2.5" rx="1.25" fill="#ffffff" opacity="0.6" />
      </svg>
      <span className="text-base font-semibold tracking-tight text-foreground">
        TicketFlow
      </span>
    </span>
  )
}

/** The bottom user card also acts as the user menu trigger on desktop. */
function UserMenu({ side = 'sidebar' }: { side?: 'sidebar' | 'header' }) {
  const navigate = useNavigate()
  const { user, isDemo, signOut } = useAuth()
  const signedInName = user?.display_name ?? 'Signed out'
  const roleLabel = user ? ACCOUNT_ROLE_LABELS[user.role] : 'No session'

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
  }

  const trigger = (
    <button
      type="button"
      className={cn(
        'flex items-center gap-2.5 rounded-md text-left transition-colors hover:bg-muted focus:outline-none',
        side === 'sidebar'
          ? 'w-full border-t border-border p-1.5 pt-3'
          : 'p-0.5',
      )}
      aria-label="Account menu"
    >
      <Avatar initials={initials(signedInName)} size="lg" />
      {side === 'sidebar' ? (
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium leading-tight text-foreground">
            {signedInName}
          </span>
          <span className="block truncate text-xs leading-tight text-muted-foreground">
            {roleLabel} · {isDemo ? 'Demo mode' : 'Signed in'}
          </span>
        </span>
      ) : null}
    </button>
  )

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-56">
        <DropdownMenuLabel className="flex items-center gap-2 px-2 py-2">
          <CircleUserRound aria-hidden="true" className="size-4 text-muted-foreground" />
          <span>
            <span className="block text-sm font-medium text-foreground">
              {signedInName}
            </span>
            <span className="block text-xs text-muted-foreground">
              {isDemo ? 'Demo account — no server session' : user?.email}
            </span>
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate('/settings')}>
          <UserRound aria-hidden="true" />
          Profile settings
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate('/settings')}>
          <Settings aria-hidden="true" />
          Workspace settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {isDemo ? (
          <DropdownMenuItem disabled>
            <LogOut aria-hidden="true" />
            Sign out (demo mode)
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onSelect={() => void handleSignOut()}>
            <LogOut aria-hidden="true" />
            Sign out
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Sidebar content, shared between the desktop rail and the mobile drawer. */
function SidebarContent({
  counts = {},
  onNavigate,
}: {
  counts?: NavCounts
  onNavigate?: () => void
}) {
  const { hasPermission, isDemo } = useAuth()

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-full grow flex-col px-3 pt-0">
        <nav aria-label="Main navigation" className="flex-1 space-y-0.5 py-0">
          {NAV_ITEMS.filter(
            (item) =>
              item.key !== 'settings' &&
              (!item.apiOnly || !isDemo) &&
              (!item.permission || hasPermission(item.permission)),
          ).map((item) => {
            const Icon = item.icon
            const counter = item.counter
            const count =
              counter !== undefined &&
              typeof counts[counter] === 'number' &&
              counts[counter] !== undefined &&
              counts[counter] > 0
                ? counts[counter]
                : null
            return (
              <NavLink
                key={item.key}
                to={item.path}
                end={item.path === '/' || item.path === '/tickets'}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors focus:outline-none',
                    isActive
                      ? 'bg-primary-tint text-primary-strong'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )
                }
                title={item.description}
              >
                {({ isActive }) => (
                  <>
                    <span
                      aria-hidden="true"
                      className={cn(
                        'absolute inset-y-1.5 left-0 w-0.5 rounded-full',
                        isActive ? 'bg-primary' : 'bg-transparent',
                      )}
                    />
                    <Icon
                      aria-hidden="true"
                      className={cn('size-4 shrink-0', !isActive && 'text-subtle-foreground')}
                    />
                    <span className="flex-1 truncate">{item.label}</span>
                    {count ? (
                      <span
                        aria-label={`${count} ${item.label}`}
                        className="rounded-full bg-danger-tint px-1.5 py-0.5 text-2xs font-semibold text-danger tabular-nums"
                      >
                        {count}
                      </span>
                    ) : null}
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>
        <div className="space-y-0.5 pb-2">
          <NavLink
            to="/settings"
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-tint text-primary-strong'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )
            }
          >
            <Settings aria-hidden="true" className="size-4 shrink-0 text-subtle-foreground" />
            Settings
          </NavLink>
        </div>
        <div className="pb-3">
          <UserMenu side="sidebar" />
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Desktop sidebar rail                                                */
/* ------------------------------------------------------------------ */

export function Sidebar({ counts }: { counts?: NavCounts }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-card lg:flex">
      <div className="flex h-14 items-center border-b border-border px-4">
        <NavLink to="/" aria-label="TicketFlow home">
          <BrandMark />
        </NavLink>
      </div>
      <SidebarContent counts={counts} />
    </aside>
  )
}

/* ------------------------------------------------------------------ */
/* Mobile drawer (< lg)                                                */
/* ------------------------------------------------------------------ */

export function MobileSidebar({
  open,
  onOpenChange,
  counts,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  counts?: NavCounts
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="left-0 top-0 h-full w-72 max-w-[85vw] translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 p-0 sm:left-0 sm:top-0"
        style={{ transform: 'none' }}
        aria-describedby={undefined}
      >
        <DialogTitle className="sr-only">Navigation menu</DialogTitle>
        <div className="flex h-14 items-center border-b border-border px-4">
          <BrandMark />
        </div>
        <div className="h-[calc(100%-3.5rem)] overflow-y-auto">
          <SidebarContent counts={counts} onNavigate={() => onOpenChange(false)} />
        </div>
      </DialogContent>
    </Dialog>
  )
}

/* ------------------------------------------------------------------ */
/* Header user menu variant                                            */
/* ------------------------------------------------------------------ */

export { UserMenu }
