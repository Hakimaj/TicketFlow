import * as React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AlertCircle, ArrowLeft, Send } from 'lucide-react'
import type { TicketCategory, TicketChannel, TicketPriority } from '@/types/ticket'
import { PageHeader } from '@/components/shared/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/select-native'
import { Textarea } from '@/components/ui/textarea'
import {
  CATEGORY_LABELS,
  CHANNEL_LABELS,
  PRIORITY_LABELS,
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
  TICKET_CHANNELS,
} from '@/lib/ticket-config'
import { ticketService } from '@/services'
import { ApiClientError } from '@/services/apiClient'

/**
 * Staff ticket intake.
 *
 * Client validation mirrors the API contract so the operator gets immediate,
 * field-level feedback; the server remains the authority and its rejection is
 * shown verbatim. The success path only runs after the API confirms the
 * creation, then opens the new ticket so the queue, counts and audit trail are
 * already consistent.
 */

const SUBJECT_MIN = 3
const SUBJECT_MAX = 300
const DESCRIPTION_MIN = 10
const DESCRIPTION_MAX = 5000
const NAME_MIN = 2

interface FormState {
  requesterName: string
  requesterEmail: string
  subject: string
  description: string
  category: TicketCategory
  priority: TicketPriority
  channel: TicketChannel
}

type FieldErrors = Partial<Record<keyof FormState, string>>

const INITIAL_FORM: FormState = {
  requesterName: '',
  requesterEmail: '',
  subject: '',
  description: '',
  category: 'general',
  priority: 'normal',
  channel: 'web_form',
}

function validate(form: FormState): FieldErrors {
  const errors: FieldErrors = {}
  const name = form.requesterName.trim()
  const email = form.requesterEmail.trim()
  const subject = form.subject.trim()
  const description = form.description.trim()

  if (name.length < NAME_MIN) {
    errors.requesterName = 'Enter the customer name (at least 2 characters).'
  }
  if (!email) {
    errors.requesterEmail = 'Enter the customer email address.'
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.requesterEmail = 'Enter a valid email address.'
  }
  if (subject.length < SUBJECT_MIN) {
    errors.subject = `Enter a subject of at least ${SUBJECT_MIN} characters.`
  } else if (subject.length > SUBJECT_MAX) {
    errors.subject = `Keep the subject under ${SUBJECT_MAX} characters.`
  }
  if (description.length < DESCRIPTION_MIN) {
    errors.description = `Describe the request in at least ${DESCRIPTION_MIN} characters.`
  } else if (description.length > DESCRIPTION_MAX) {
    errors.description = `Keep the description under ${DESCRIPTION_MAX} characters.`
  }
  return errors
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null
  return (
    <p id={id} className="text-xs text-danger">
      {message}
    </p>
  )
}

export function NewTicketPage() {
  const navigate = useNavigate()
  const [form, setForm] = React.useState<FormState>(INITIAL_FORM)
  const [errors, setErrors] = React.useState<FieldErrors>({})
  const [submitError, setSubmitError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)
  const submittingRef = React.useRef(false)

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
    setErrors((current) => {
      if (!current[key]) return current
      const next = { ...current }
      delete next[key]
      return next
    })
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    // Guard against a double submit (double click / Enter while in flight).
    if (submittingRef.current) return

    const validation = validate(form)
    setErrors(validation)
    setSubmitError(null)
    if (Object.keys(validation).length > 0) return

    submittingRef.current = true
    setSubmitting(true)
    try {
      const created = await ticketService.createTicket({
        subject: form.subject.trim(),
        description: form.description.trim(),
        category: form.category,
        priority: form.priority,
        channel: form.channel,
        requesterName: form.requesterName.trim(),
        requesterEmail: form.requesterEmail.trim(),
      })
      // The API confirmed the write; open the persisted ticket.
      navigate(`/tickets/${created.id}`, {
        replace: true,
        state: { returnTo: '/tickets', createdTicketId: created.id },
      })
    } catch (error) {
      setSubmitError(
        error instanceof ApiClientError
          ? error.message
          : 'The ticket could not be created. Check your connection and try again.',
      )
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader
        breadcrumb={
          <Link to="/tickets" className="hover:text-foreground hover:underline">
            Tickets
          </Link>
        }
        title="New Ticket"
        description="Log a support request on behalf of a customer. The ticket is stored immediately and starts unassigned in the New queue."
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to="/tickets">
              <ArrowLeft aria-hidden="true" />
              Back to tickets
            </Link>
          </Button>
        }
      />

      <Card className="max-w-3xl">
        <CardContent className="p-4 sm:p-5">
          <form onSubmit={handleSubmit} noValidate aria-label="Create a ticket">
            {submitError ? (
              <p
                role="alert"
                className="mb-4 flex items-start gap-1.5 rounded-md border border-danger/30 bg-danger-tint px-2.5 py-2 text-xs text-danger"
              >
                <AlertCircle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
                {submitError}
              </p>
            ) : null}

            <fieldset className="space-y-4" disabled={submitting}>
              <legend className="mb-2 text-sm font-semibold text-foreground">
                Customer
              </legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="requester-name">Customer name</Label>
                  <Input
                    id="requester-name"
                    name="requesterName"
                    value={form.requesterName}
                    onChange={(e) => update('requesterName', e.target.value)}
                    autoComplete="off"
                    aria-required="true"
                    aria-invalid={Boolean(errors.requesterName)}
                    aria-describedby={
                      errors.requesterName ? 'requester-name-error' : undefined
                    }
                  />
                  <FieldError id="requester-name-error" message={errors.requesterName} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="requester-email">Customer email</Label>
                  <Input
                    id="requester-email"
                    name="requesterEmail"
                    type="email"
                    value={form.requesterEmail}
                    onChange={(e) => update('requesterEmail', e.target.value)}
                    autoComplete="off"
                    aria-required="true"
                    aria-invalid={Boolean(errors.requesterEmail)}
                    aria-describedby={
                      errors.requesterEmail ? 'requester-email-error' : undefined
                    }
                  />
                  <FieldError
                    id="requester-email-error"
                    message={errors.requesterEmail}
                  />
                </div>
              </div>
              <p className="text-2xs text-muted-foreground">
                An existing customer email is reused, so one customer can own
                several tickets.
              </p>
            </fieldset>

            <fieldset className="mt-5 space-y-3" disabled={submitting}>
              <legend className="mb-2 text-sm font-semibold text-foreground">
                Request
              </legend>
              <div className="space-y-1">
                <Label htmlFor="ticket-subject">Subject</Label>
                <Input
                  id="ticket-subject"
                  name="subject"
                  value={form.subject}
                  onChange={(e) => update('subject', e.target.value)}
                  maxLength={SUBJECT_MAX}
                  aria-required="true"
                  aria-invalid={Boolean(errors.subject)}
                  aria-describedby={errors.subject ? 'ticket-subject-error' : undefined}
                  placeholder="Short summary, e.g. “Refund not received for order #ET-88412”"
                />
                <FieldError id="ticket-subject-error" message={errors.subject} />
              </div>

              <div className="space-y-1">
                <Label htmlFor="ticket-description">Description</Label>
                <Textarea
                  id="ticket-description"
                  name="description"
                  value={form.description}
                  onChange={(e) => update('description', e.target.value)}
                  maxLength={DESCRIPTION_MAX}
                  aria-required="true"
                  aria-invalid={Boolean(errors.description)}
                  aria-describedby={
                    errors.description ? 'ticket-description-error' : undefined
                  }
                  placeholder="What the customer reported, and when."
                />
                <FieldError
                  id="ticket-description-error"
                  message={errors.description}
                />
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1">
                  <Label htmlFor="ticket-category">Category</Label>
                  <NativeSelect
                    id="ticket-category"
                    name="category"
                    value={form.category}
                    onChange={(e) =>
                      update('category', e.target.value as TicketCategory)
                    }
                  >
                    {TICKET_CATEGORIES.map((category) => (
                      <option key={category} value={category}>
                        {CATEGORY_LABELS[category]}
                      </option>
                    ))}
                  </NativeSelect>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="ticket-priority">Priority</Label>
                  <NativeSelect
                    id="ticket-priority"
                    name="priority"
                    value={form.priority}
                    onChange={(e) =>
                      update('priority', e.target.value as TicketPriority)
                    }
                  >
                    {TICKET_PRIORITIES.map((priority) => (
                      <option key={priority} value={priority}>
                        {PRIORITY_LABELS[priority]}
                      </option>
                    ))}
                  </NativeSelect>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="ticket-channel">Channel</Label>
                  <NativeSelect
                    id="ticket-channel"
                    name="channel"
                    value={form.channel}
                    onChange={(e) =>
                      update('channel', e.target.value as TicketChannel)
                    }
                  >
                    {TICKET_CHANNELS.map((channel) => (
                      <option key={channel} value={channel}>
                        {CHANNEL_LABELS[channel]}
                      </option>
                    ))}
                  </NativeSelect>
                </div>
              </div>

              <p className="text-2xs text-muted-foreground">
                New tickets start as <span className="font-medium text-foreground">New</span> and
                are routed to the team that owns the category. Urgent and high
                priority tickets get an 8-hour target.
              </p>
            </fieldset>

            <div className="mt-5 flex flex-wrap items-center justify-end gap-2 border-t border-border pt-3">
              <Button type="button" variant="ghost" size="sm" asChild>
                <Link to="/tickets">Cancel</Link>
              </Button>
              <Button type="submit" size="sm" disabled={submitting}>
                <Send aria-hidden="true" />
                {submitting ? 'Creating ticket…' : 'Create ticket'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
