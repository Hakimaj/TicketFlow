import * as React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Bell, Menu, Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { MobileSidebar, UserMenu } from './sidebar'
import type { NavCounts, NavScope } from './nav-config'
import { cn } from '@/lib/utils'
/** Route → header title. Placeholder routes included so none is blank. */
const TITLES: Record<NavScope, { title: string; crumb?: string }> = {
  overview: { title: 'Overview' },
  all: { title: 'All Tickets' },
  mine: { title: 'My Tickets', crumb: 'Tickets' },
  unassigned: { title: 'Unassigned', crumb: 'Tickets' },
  needs_review: { title: 'Needs Review', crumb: 'Tickets' },
  analytics: { title: 'Analytics' },
  activity: { title: 'Activity Logs' },
  settings: { title: 'Settings' },
  ticket_detail: { title: 'Ticket details', crumb: 'Tickets' },
}

function resolveRoute(pathname: string): NavScope {
  if (pathname === '/') return 'overview'
  if (pathname === '/analytics') return 'analytics'
  if (pathname === '/activity') return 'activity'
  if (pathname.startsWith('/settings')) return 'settings'
  if (pathname === '/tickets/mine') return 'mine'
  if (pathname === '/tickets/unassigned') return 'unassigned'
  if (pathname === '/tickets/needs-review') return 'needs_review'
  if (/^\/tickets\/[^/]+$/.test(pathname)) return 'ticket_detail'
  return 'all'
}

/* --------------------------- New ticket dialog --------------------------- */

function NewTicketDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create a new ticket</DialogTitle>
          <DialogDescription>
            Ticket intake opens in Phase 2, when the TicketFlow API is
            connected. The form below is a preview — nothing is submitted in
            this phase.
          </DialogDescription>
        </DialogHeader>
        <div aria-hidden="true" className="space-y-3 opacity-50">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Requester</Label>
              <Input disabled placeholder="Customer name or email" />
            </div>
            <div className="space-y-1">
              <Label>Channel</Label>
              <Input disabled placeholder="Email / web form / chat" />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Subject</Label>
            <Input disabled placeholder="Short summary of the issue" />
          </div>
          <div className="space-y-1">
            <Label>Description</Label>
            <Input disabled placeholder="What went wrong, and when?" />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Demo environment — no data is stored or sent anywhere.
        </p>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Got it</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ------------------------------ Header core ------------------------------ */

export function TopHeader({ counts }: { counts?: NavCounts }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  const [newTicketOpen, setNewTicketOpen] = React.useState(false)
  const [search, setSearch] = React.useState('')

  const resolved = resolveRoute(pathname)
  const info = TITLES[resolved]

  function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    const params = new URLSearchParams()
    if (search.trim()) params.set('q', search.trim())
    navigate(`/tickets${params.toString() ? `?${params.toString()}` : ''}`)
  }

  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4 lg:px-6">
      {/* Mobile menu */}
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        aria-label="Open navigation menu"
        aria-expanded={drawerOpen}
        onClick={() => setDrawerOpen(true)}
      >
        <Menu aria-hidden="true" />
      </Button>
      <MobileSidebar open={drawerOpen} onOpenChange={setDrawerOpen} counts={counts} />

      {/* Title / breadcrumb */}
      <div className="min-w-0">
        {info.crumb ? (
          <p className="truncate text-2xs uppercase tracking-wide text-subtle-foreground">
            {info.crumb}
          </p>
        ) : null}
        <h1 className={cn('truncate font-semibold text-foreground', info.crumb ? 'text-sm' : 'text-base')}>
          {info.title}
        </h1>
      </div>

      {/* Search */}
      <form
        role="search"
        onSubmit={submitSearch}
        className="ml-auto hidden max-w-md flex-1 md:block"
      >
        <SearchInput
          type="search"
          name="global-search"
          placeholder="Search tickets by number, subject or requester…"
          aria-label="Search tickets"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </form>
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Search tickets"
        onClick={() => navigate('/tickets')}
      >
        <Search aria-hidden="true" />
      </Button>

      {/* Actions */}
      <div className="flex items-center gap-1.5">
        <Button
          size="sm"
          className="hidden sm:inline-flex"
          onClick={() => setNewTicketOpen(true)}
        >
          <Plus aria-hidden="true" />
          New Ticket
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="sm:hidden"
          aria-label="New ticket (preview)"
          onClick={() => setNewTicketOpen(true)}
        >
          <Plus aria-hidden="true" />
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="relative rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none"
              aria-label="Notifications (no new notifications)"
            >
              <Bell aria-hidden="true" className="size-4" />
              <span
                aria-hidden="true"
                className="absolute right-1.5 top-1.5 size-2 rounded-full border border-card bg-warning"
              />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72">
            <DropdownMenuLabel>Notifications</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled>
              <span className="flex flex-col items-start gap-0.5">
                <span className="text-sm font-medium text-foreground">
                  Demo environment
                </span>
                <span className="text-xs text-muted-foreground">
                  Live notification rules arrive with the backend integration.
                </span>
              </span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="lg:hidden">
          <UserMenu side="header" />
        </div>
      </div>

      <NewTicketDialog open={newTicketOpen} onOpenChange={setNewTicketOpen} />
    </header>
  )
}
