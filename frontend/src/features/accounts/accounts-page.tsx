import * as React from 'react'
import { AlertCircle, CheckCircle2, Plus, Search, ShieldCheck } from 'lucide-react'
import type { AccountRole, AdminAccount } from '@/types/auth'
import type { Agent } from '@/types/ticket'
import { useAuth } from '@/auth'
import { PageHeader } from '@/components/shared/page-header'
import { ConfirmDialog } from '@/components/shared/confirm-dialog'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/shared/states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input, SearchInput } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/select-native'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ACCOUNT_ROLE_LABELS } from '@/lib/ticket-config'
import { formatDate } from '@/lib/format'
import { ticketService } from '@/services'
import { createAccount, listAccounts, updateAccount } from '@/services/accountService'
import { ApiClientError } from '@/services/apiClient'

/**
 * Administrator account management.
 *
 * Visibility is gated by the `accounts:manage` permission, but that is only a
 * usability aid: the API re-checks the permission on every request and refuses
 * self-privilege changes and last-administrator lockout. The initial password
 * is sent once, hashed by the server and never displayed again; the new account
 * must replace it before the workspace opens.
 */

const ACCOUNT_ROLES: AccountRole[] = ['agent', 'reviewer', 'admin']
const MIN_PASSWORD_LENGTH = 12

type Feedback = { type: 'success' | 'error'; message: string } | null

const EMPTY_FORM = {
  email: '',
  displayName: '',
  role: 'agent' as AccountRole,
  agentId: '',
  password: '',
  isActive: true,
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiClientError ? error.message : fallback
}

/* --------------------------- Create dialog --------------------------- */

function CreateAccountDialog({
  open,
  onOpenChange,
  agents,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  agents: Agent[]
  onCreated: (account: AdminAccount) => void
}) {
  const [form, setForm] = React.useState(EMPTY_FORM)
  const [error, setError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)
  const submittingRef = React.useRef(false)

  React.useEffect(() => {
    if (!open) {
      setForm(EMPTY_FORM)
      setError(null)
      setSubmitting(false)
      submittingRef.current = false
    }
  }, [open])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (submittingRef.current) return
    setError(null)

    if (!form.email.trim() || !form.displayName.trim()) {
      setError('Email and display name are required.')
      return
    }
    if (form.password.length < MIN_PASSWORD_LENGTH) {
      setError(
        `The initial password must be at least ${MIN_PASSWORD_LENGTH} characters.`,
      )
      return
    }

    submittingRef.current = true
    setSubmitting(true)
    try {
      const account = await createAccount({
        email: form.email.trim(),
        displayName: form.displayName.trim(),
        role: form.role,
        password: form.password,
        agentId: form.agentId || null,
        isActive: form.isActive,
      })
      onCreated(account)
      onOpenChange(false)
    } catch (err) {
      setError(
        errorMessage(
          err,
          'The account could not be created. Check the connection and retry.',
        ),
      )
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Provision an account</DialogTitle>
          <DialogDescription>
            Share the initial password with the person through a secure channel.
            They must replace it at first sign-in before the workspace opens.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate className="space-y-3">
          {error ? (
            <p
              role="alert"
              className="flex items-start gap-1.5 rounded-md border border-danger/30 bg-danger-tint px-2.5 py-2 text-xs text-danger"
            >
              <AlertCircle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              {error}
            </p>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="new-account-name">Display name</Label>
              <Input
                id="new-account-name"
                value={form.displayName}
                onChange={(e) =>
                  setForm((f) => ({ ...f, displayName: e.target.value }))
                }
                autoComplete="off"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="new-account-email">Email</Label>
              <Input
                id="new-account-email"
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                autoComplete="off"
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="new-account-role">Role</Label>
              <NativeSelect
                id="new-account-role"
                value={form.role}
                onChange={(e) =>
                  setForm((f) => ({ ...f, role: e.target.value as AccountRole }))
                }
              >
                {ACCOUNT_ROLES.map((role) => (
                  <option key={role} value={role}>
                    {ACCOUNT_ROLE_LABELS[role]}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1">
              <Label htmlFor="new-account-agent">Linked support agent</Label>
              <NativeSelect
                id="new-account-agent"
                value={form.agentId}
                onChange={(e) =>
                  setForm((f) => ({ ...f, agentId: e.target.value }))
                }
              >
                <option value="">No agent link (admin-only account)</option>
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.id} · {agent.name}
                  </option>
                ))}
              </NativeSelect>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="new-account-password">Initial password</Label>
              <Input
                id="new-account-password"
                type="password"
                value={form.password}
                onChange={(e) =>
                  setForm((f) => ({ ...f, password: e.target.value }))
                }
                autoComplete="new-password"
                minLength={MIN_PASSWORD_LENGTH}
              />
              <p className="text-2xs text-muted-foreground">
                At least {MIN_PASSWORD_LENGTH} characters. Hashed with Argon2id;
                never shown again.
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="new-account-status">Activation</Label>
              <NativeSelect
                id="new-account-status"
                value={form.isActive ? 'active' : 'inactive'}
                onChange={(e) =>
                  setForm((f) => ({ ...f, isActive: e.target.value === 'active' }))
                }
              >
                <option value="active">Active — can sign in</option>
                <option value="inactive">Inactive — cannot sign in</option>
              </NativeSelect>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create account'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ------------------------------ Page ------------------------------ */

export function AccountsPage() {
  const { user } = useAuth()
  const [accounts, setAccounts] = React.useState<AdminAccount[] | null>(null)
  const [agents, setAgents] = React.useState<Agent[]>([])
  const [loading, setLoading] = React.useState(true)
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [feedback, setFeedback] = React.useState<Feedback>(null)
  const [busyId, setBusyId] = React.useState<string | null>(null)
  const [createOpen, setCreateOpen] = React.useState(false)
  const [search, setSearch] = React.useState('')
  const [debouncedSearch, setDebouncedSearch] = React.useState('')
  const [roleFilter, setRoleFilter] = React.useState<AccountRole | 'all'>('all')
  const [statusFilter, setStatusFilter] = React.useState<
    'all' | 'active' | 'inactive'
  >('all')
  const [pendingDeactivate, setPendingDeactivate] =
    React.useState<AdminAccount | null>(null)

  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 250)
    return () => window.clearTimeout(timer)
  }, [search])

  const load = React.useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [list, agentList] = await Promise.all([
        listAccounts({
          search: debouncedSearch,
          role: roleFilter === 'all' ? null : roleFilter,
          isActive: statusFilter === 'all' ? null : statusFilter === 'active',
          pageSize: 100,
        }),
        ticketService.listAgents(),
      ])
      setAccounts(list.items)
      setAgents(agentList)
    } catch (error) {
      setLoadError(
        errorMessage(error, 'Accounts could not be loaded. Check the connection.'),
      )
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, roleFilter, statusFilter])

  React.useEffect(() => {
    void load()
  }, [load])

  async function patchAccount(
    account: AdminAccount,
    patch: Parameters<typeof updateAccount>[1],
    successMessage: string,
  ) {
    setBusyId(account.id)
    setFeedback(null)
    try {
      const updated = await updateAccount(account.id, patch)
      setAccounts((current) =>
        current
          ? current.map((item) => (item.id === updated.id ? updated : item))
          : current,
      )
      setFeedback({ type: 'success', message: successMessage })
    } catch (error) {
      setFeedback({
        type: 'error',
        message: errorMessage(error, 'The account could not be updated.'),
      })
    } finally {
      setBusyId(null)
    }
  }

  const isSelf = (account: AdminAccount) => account.id === user?.id

  return (
    <div>
      <PageHeader
        title="Accounts"
        description="Provision staff accounts, link them to support agents and control access. Deactivating an account ends its sessions immediately."
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden="true" />
            New account
          </Button>
        }
      />

      {feedback ? (
        <p
          role={feedback.type === 'error' ? 'alert' : 'status'}
          className={
            feedback.type === 'error'
              ? 'mb-4 flex items-start gap-1.5 rounded-md border border-danger/30 bg-danger-tint px-2.5 py-2 text-xs text-danger'
              : 'mb-4 flex items-start gap-1.5 rounded-md border border-emerald-200 bg-success-tint px-2.5 py-2 text-xs text-success'
          }
        >
          {feedback.type === 'error' ? (
            <AlertCircle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          ) : (
            <CheckCircle2 aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          )}
          {feedback.message}
        </p>
      ) : null}

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
          <div className="min-w-[200px] flex-1 sm:max-w-xs">
            <SearchInput
              type="search"
              aria-label="Search accounts"
              placeholder="Search name, email or agent…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <NativeSelect
            aria-label="Filter by role"
            className="w-[10rem]"
            value={roleFilter}
            onChange={(e) =>
              setRoleFilter(e.target.value as AccountRole | 'all')
            }
          >
            <option value="all">All roles</option>
            {ACCOUNT_ROLES.map((role) => (
              <option key={role} value={role}>
                {ACCOUNT_ROLE_LABELS[role]}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="Filter by activation"
            className="w-[10rem]"
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')
            }
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </NativeSelect>
          <Button variant="ghost" size="sm" onClick={() => void load()}>
            <Search aria-hidden="true" />
            Refresh
          </Button>
        </div>

        {loading ? (
          <ListSkeleton rows={6} label="Loading accounts" />
        ) : loadError ? (
          <ErrorState
            title="Accounts could not be loaded"
            description={loadError}
            onRetry={() => void load()}
          />
        ) : !accounts || accounts.length === 0 ? (
          <EmptyState
            title="No accounts match"
            description="Adjust the search or filters, or provision a new account."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Account</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Support agent</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map((account) => {
                const self = isSelf(account)
                const busy = busyId === account.id
                return (
                  <TableRow key={account.id}>
                    <TableCell>
                      <span className="block text-sm font-medium text-foreground">
                        {account.display_name}
                      </span>
                      <span className="block text-xs text-muted-foreground">
                        {account.email}
                        {self ? ' · you' : ''}
                      </span>
                    </TableCell>
                    <TableCell>
                      <NativeSelect
                        aria-label={`Role for ${account.email}`}
                        className="w-[9.5rem]"
                        value={account.role}
                        disabled={self || busy}
                        title={
                          self
                            ? 'You cannot change your own role.'
                            : undefined
                        }
                        onChange={(e) => {
                          const role = e.target.value as AccountRole
                          void patchAccount(
                            account,
                            { role },
                            `${account.email} is now ${ACCOUNT_ROLE_LABELS[role]}.`,
                          )
                        }}
                      >
                        {ACCOUNT_ROLES.map((role) => (
                          <option key={role} value={role}>
                            {ACCOUNT_ROLE_LABELS[role]}
                          </option>
                        ))}
                      </NativeSelect>
                    </TableCell>
                    <TableCell>
                      <NativeSelect
                        aria-label={`Support agent for ${account.email}`}
                        className="w-[12rem]"
                        value={account.agent_id ?? ''}
                        disabled={busy}
                        onChange={(e) => {
                          const agentId = e.target.value || null
                          void patchAccount(
                            account,
                            { agent_id: agentId },
                            agentId
                              ? `Linked ${account.email} to ${agentId}.`
                              : `Unlinked the support agent from ${account.email}.`,
                          )
                        }}
                      >
                        <option value="">No agent link</option>
                        {agents.map((agent) => (
                          <option key={agent.id} value={agent.id}>
                            {agent.id} · {agent.name}
                          </option>
                        ))}
                      </NativeSelect>
                    </TableCell>
                    <TableCell>
                      <span className="flex flex-col items-start gap-1">
                        <Badge variant={account.is_active ? 'success' : 'neutral'}>
                          {account.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        {account.must_change_password ? (
                          <Badge variant="warning">Password change pending</Badge>
                        ) : null}
                      </span>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {formatDate(account.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {account.is_active ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={self || busy}
                          title={
                            self
                              ? 'You cannot deactivate your own account.'
                              : undefined
                          }
                          onClick={() => setPendingDeactivate(account)}
                        >
                          Deactivate
                        </Button>
                      ) : (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={busy}
                          onClick={() =>
                            void patchAccount(
                              account,
                              { is_active: true },
                              `${account.email} can sign in again.`,
                            )
                          }
                        >
                          Activate
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </Card>

      <p className="mt-3 flex items-start gap-1.5 text-xs text-muted-foreground">
        <ShieldCheck aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        <span>
          Roles are stored server-side and re-checked on every request. You cannot
          change your own role or activation state, and the last active
          administrator is protected.
        </span>
      </p>

      <CreateAccountDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        agents={agents}
        onCreated={(account) => {
          setAccounts((current) => (current ? [account, ...current] : [account]))
          setFeedback({
            type: 'success',
            message: `${account.email} was provisioned. They must change the initial password at first sign-in.`,
          })
        }}
      />

      <ConfirmDialog
        open={pendingDeactivate !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDeactivate(null)
        }}
        title="Deactivate this account?"
        description={
          pendingDeactivate
            ? `${pendingDeactivate.email} will be signed out immediately and cannot sign in or refresh its session until reactivated.`
            : undefined
        }
        confirmLabel="Deactivate"
        destructive
        onConfirm={() => {
          if (!pendingDeactivate) return
          const target = pendingDeactivate
          setPendingDeactivate(null)
          void patchAccount(
            target,
            { is_active: false },
            `${target.email} was deactivated and its sessions were revoked.`,
          )
        }}
      />
    </div>
  )
}
