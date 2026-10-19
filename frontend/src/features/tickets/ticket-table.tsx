import * as React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowDown, ArrowUpDown, ArrowUp } from 'lucide-react'
import type { Ticket, TicketSortField } from '@/types/ticket'
import { CATEGORY_LABELS, SORT_FIELD_LABELS, TEAM_LABELS } from '@/lib/ticket-config'
import { formatRelativeTime, formatDate } from '@/lib/format'
import { DEMO_AGENTS_BY_ID } from '@/data'
import { CategoryBadge, PriorityBadge, StatusBadge } from '@/components/shared/ticket-badges'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'

/**
 * Ticket list table: compact rows, sortable headers, page-level selection,
 * and navigation to the (Phase 2) ticket detail placeholder. Columns hide
 * progressively on smaller screens instead of shrinking to unreadable.
 */

function assigneeLabel(ticket: Ticket): { text: string; muted: boolean } {
  if (ticket.assignedAgentId) {
    const name = DEMO_AGENTS_BY_ID.get(ticket.assignedAgentId)?.name
    if (name) return { text: name, muted: false }
  }
  if (ticket.assignedTeam) {
    return { text: TEAM_LABELS[ticket.assignedTeam], muted: true }
  }
  return { text: 'Unassigned', muted: true }
}

function SortArrow({ state }: { state: 'none' | 'asc' | 'desc' }) {
  if (state === 'none') {
    return <ArrowUpDown aria-hidden="true" className="size-3 opacity-40" />
  }
  return state === 'asc'
    ? <ArrowUp aria-hidden="true" className="size-3" />
    : <ArrowDown aria-hidden="true" className="size-3" />
}

function SortHeader({
  field,
  sortBy,
  sortDir,
  onSort,
  className,
  children,
}: {
  field: TicketSortField
  sortBy: TicketSortField
  sortDir: 'asc' | 'desc'
  onSort: (field: TicketSortField) => void
  className?: string
  children: React.ReactNode
}) {
  const active = sortBy === field
  const ariaSort: 'ascending' | 'descending' | 'none' = active
    ? sortDir === 'asc'
      ? 'ascending'
      : 'descending'
    : 'none'
  return (
    <TableHead className={cn('pl-0', className)} aria-sort={ariaSort}>
      <button
        type="button"
        onClick={() => onSort(field)}
        className={cn(
          'inline-flex items-center gap-1 rounded px-0.5 py-0.5 text-xs font-medium focus-visible:outline-none',
          active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
        )}
        aria-label={`Sort by ${SORT_FIELD_LABELS[field]}`}
      >
        {children}
        <SortArrow state={active ? sortDir : 'none'} />
      </button>
    </TableHead>
  )
}

export function TicketTable({
  tickets,
  sortBy,
  sortDir,
  onSort,
}: {
  tickets: Ticket[]
  sortBy: TicketSortField
  sortDir: 'asc' | 'desc'
  onSort: (field: TicketSortField) => void
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const [selected, setSelected] = React.useState<ReadonlySet<string>>(new Set())

  const allSelected = tickets.length > 0 && tickets.every((t) => selected.has(t.id))
  const someSelected = selected.size > 0 && !allSelected

  function openTicket(ticket: Ticket) {
    navigate(`/tickets/${ticket.id}`, {
      state: { returnTo: `${location.pathname}${location.search}` },
    })
  }

  function toggleRow(id: string) {
    setSelected((prev) => {
      const next = prev.has(id)
        ? [...prev].filter((x) => x !== id)
        : [...prev, id]
      return new Set(next)
    })
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-card-muted">
          <TableHead className="w-10 pl-4">
            <Checkbox
              aria-label="Select all visible rows"
              checked={allSelected ? true : someSelected ? 'indeterminate' : false}
              onCheckedChange={() =>
                setSelected(allSelected ? new Set() : new Set(tickets.map((t) => t.id)))
              }
            />
          </TableHead>
          <TableHead className="w-20 pl-0">Ticket ID</TableHead>
          <SortHeader field="subject" sortBy={sortBy} sortDir={sortDir} onSort={onSort}>
            Subject
          </SortHeader>
          <TableHead className="hidden pl-0 lg:table-cell">Requester</TableHead>
          <SortHeader
            field="category"
            sortBy={sortBy}
            sortDir={sortDir}
            onSort={onSort}
            className="hidden sm:table-cell pl-0"
          >
            Category
          </SortHeader>
          <SortHeader
            field="priority"
            sortBy={sortBy}
            sortDir={sortDir}
            onSort={onSort}
            className="hidden md:table-cell pl-0"
          >
            Priority
          </SortHeader>
          <SortHeader field="status" sortBy={sortBy} sortDir={sortDir} onSort={onSort} className="pl-0">
            Status
          </SortHeader>
          <TableHead className="hidden md:table-cell pl-0">Assignee</TableHead>
          <SortHeader
            field="createdAt"
            sortBy={sortBy}
            sortDir={sortDir}
            onSort={onSort}
            className="pl-0 pr-4"
          >
            Received
          </SortHeader>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tickets.map((ticket) => {
          const isSelected = selected.has(ticket.id)
          const assignee = assigneeLabel(ticket)
          return (
            <TableRow
              key={ticket.id}
              className={cn('cursor-pointer', isSelected && 'bg-primary-tint/60')}
              onClick={() => openTicket(ticket)}
              onKeyDown={(event) => {
                if (event.target !== event.currentTarget) return
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  openTicket(ticket)
                }
              }}
            >
              <TableCell className="pl-4">
                <Checkbox
                  aria-label={`Select ${ticket.id}`}
                  checked={isSelected}
                  onClick={(e) => e.stopPropagation()}
                  onCheckedChange={() => toggleRow(ticket.id)}
                />
              </TableCell>
              <TableCell className="pl-0 text-xs font-medium text-muted-foreground tabular-nums">
                {ticket.id}
              </TableCell>
              <TableCell className="max-w-[230px] md:max-w-xs sm:max-w-[180px]">
                <span className="block truncate font-medium text-foreground">
                  {ticket.subject}
                </span>
                <span className="block truncate text-xs text-muted-foreground lg:hidden">
                  {ticket.requesterName} · {CATEGORY_LABELS[ticket.category]}
                </span>
              </TableCell>
              <TableCell className="hidden max-w-[160px] whitespace-nowrap lg:table-cell pl-0">
                <span className="block truncate">{ticket.requesterName}</span>
              </TableCell>
              <TableCell className="hidden sm:table-cell pl-0">
                <CategoryBadge category={ticket.category} />
              </TableCell>
              <TableCell className="hidden md:table-cell pl-0">
                <PriorityBadge priority={ticket.priority} />
              </TableCell>
              <TableCell className="pl-0">
                <StatusBadge status={ticket.status} />
              </TableCell>
              <TableCell className="hidden whitespace-nowrap md:table-cell pl-0">
                <span className={cn('text-xs', assignee.muted ? 'text-muted-foreground' : 'text-foreground')}>
                  {assignee.text}
                </span>
              </TableCell>
              <TableCell className="whitespace-nowrap pl-0 pr-4 text-xs text-muted-foreground" title={formatDate(ticket.createdAt)}>
                {formatRelativeTime(ticket.createdAt)}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
