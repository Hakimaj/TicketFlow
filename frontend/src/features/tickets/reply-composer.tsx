import * as React from 'react'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  Edit3,
  FileCheck,
  FileText,
  Mail,
  RotateCcw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import type { CustomerReply, ReplyState } from '@/types/reply'
import type { Ticket } from '@/types/ticket'
import { formatDateTime, formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { ticketService } from '@/services'
import { DEMO_USER } from '@/data'
import { REPLY_TEMPLATES } from '@/lib/reply-templates'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/shared/confirm-dialog'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from '@/components/ui/select'

interface ReplyComposerProps {
  ticket: Ticket
  replies: CustomerReply[]
  onReplyUpdated: () => void
  showFeedback: (message: string, type?: 'success' | 'error') => void
}

function ReplyStateBadge({ state }: { state: ReplyState }) {
  switch (state) {
    case 'draft':
      return (
        <Badge variant="neutral" className="gap-1 font-medium">
          <Edit3 className="size-3" aria-hidden="true" />
          Draft
        </Badge>
      )
    case 'pending_approval':
      return (
        <Badge variant="warning" className="gap-1 font-medium">
          <Clock className="size-3" aria-hidden="true" />
          Pending Approval
        </Badge>
      )
    case 'approved':
      return (
        <Badge variant="success" className="gap-1 font-medium">
          <CheckCircle2 className="size-3" aria-hidden="true" />
          Approved — Ready to Send
        </Badge>
      )
    case 'changes_requested':
      return (
        <Badge variant="danger" className="gap-1 font-medium">
          <AlertTriangle className="size-3" aria-hidden="true" />
          Changes Requested
        </Badge>
      )
    case 'sent':
      return (
        <Badge variant="primary" className="gap-1 font-medium">
          <Send className="size-3" aria-hidden="true" />
          Sent (Demo)
        </Badge>
      )
  }
}

export function ReplyComposer({
  ticket,
  replies,
  onReplyUpdated,
  showFeedback,
}: ReplyComposerProps) {
  // The active reply is the most recently created reply for this ticket.
  // `getReplies` returns newest-first, but sort defensively so the workflow
  // never operates on an older (possibly sent) reply.
  const activeReply = React.useMemo(() => {
    if (replies.length === 0) return null
    return [...replies].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    )[0]
  }, [replies])

  const isSent = activeReply?.state === 'sent'
  const isPending = activeReply?.state === 'pending_approval'
  const isApproved = activeReply?.state === 'approved'
  const isChangesRequested = activeReply?.state === 'changes_requested'
  const isDraft = !activeReply || activeReply.state === 'draft'

  // Composer text state
  const [bodyText, setBodyText] = React.useState('')
  const [validationError, setValidationError] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  // Supervisor review state
  const [showReviewComments, setShowReviewComments] = React.useState(false)
  const [reviewerComment, setReviewerComment] = React.useState('')
  const [reviewError, setReviewError] = React.useState<string | null>(null)

  // Explicit edit mode when reply is in approved or sent state
  const [isForcingEdit, setIsForcingEdit] = React.useState(false)
  const [showSendConfirm, setShowSendConfirm] = React.useState(false)

  // Track which reply revision the editor was last loaded from. A stable key
  // (rather than object identity) prevents unsaved typing from being
  // overwritten when the page refreshes after a service event.
  const syncedReplyKeyRef = React.useRef<string | null>(null)

  React.useEffect(() => {
    if (isForcingEdit) return
    const nextKey = activeReply
      ? `${activeReply.id}:${activeReply.version}:${activeReply.updatedAt}`
      : null
    if (syncedReplyKeyRef.current === nextKey) return
    syncedReplyKeyRef.current = nextKey
    setBodyText(activeReply?.body ?? '')
  }, [activeReply, isForcingEdit])

  // Template insertion
  function handleSelectTemplate(templateId: string) {
    if (templateId === 'none') return
    const template = REPLY_TEMPLATES.find((t) => t.id === templateId)
    if (!template) return
    const generated = template.generate(ticket)
    setBodyText(generated)
    setValidationError(null)
    showFeedback(`Template "${template.label}" applied.`)
  }

  // Word and character count
  const charCount = bodyText.length
  const wordCount = bodyText.trim() ? bodyText.trim().split(/\s+/).length : 0

  // 1. Save Draft
  async function handleSaveDraft() {
    const trimmed = bodyText.trim()
    if (!trimmed) {
      setValidationError('Draft cannot be empty. Please enter your reply text.')
      return
    }

    setValidationError(null)
    setIsSubmitting(true)
    try {
      await ticketService.saveReplyDraft(ticket.id, trimmed, DEMO_USER)
      setIsForcingEdit(false)
      onReplyUpdated()
      showFeedback('Customer reply draft saved.')
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : 'Failed to save draft.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // 2. Submit for Approval
  async function handleSubmitForApproval() {
    const trimmed = bodyText.trim()
    if (!trimmed) {
      setValidationError('Reply text cannot be empty before submitting for approval.')
      return
    }

    setValidationError(null)
    setIsSubmitting(true)
    try {
      // First ensure the latest text is saved
      const saved = await ticketService.saveReplyDraft(ticket.id, trimmed, DEMO_USER)
      // Then submit for approval
      await ticketService.submitReplyForApproval(saved.id, DEMO_USER)
      setIsForcingEdit(false)
      onReplyUpdated()
      showFeedback('Reply submitted for supervisor approval.')
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : 'Failed to submit reply.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // 3. Supervisor: Approve Reply
  async function handleApprove() {
    if (!activeReply) return
    setIsSubmitting(true)
    try {
      await ticketService.approveReply(activeReply.id, DEMO_USER)
      onReplyUpdated()
      showFeedback('Reply approved! It can now be marked as sent.')
    } catch (err) {
      showFeedback(err instanceof Error ? err.message : 'Failed to approve reply.', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  // 4. Supervisor: Request Changes
  async function handleRequestChanges(e: React.FormEvent) {
    e.preventDefault()
    if (!activeReply) return
    const trimmed = reviewerComment.trim()
    if (!trimmed) {
      setReviewError('Reviewer comments explaining the requested revisions are required.')
      return
    }

    setReviewError(null)
    setIsSubmitting(true)
    try {
      await ticketService.requestReplyChanges(activeReply.id, trimmed, DEMO_USER)
      setShowReviewComments(false)
      setReviewerComment('')
      onReplyUpdated()
      showFeedback('Changes requested. The reply is back with its author for revision.')
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : 'Failed to request changes.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // 5. Mark as Sent (Demo) — Approval Gate strictly enforced by the service
  async function handleMarkSent() {
    if (!activeReply) return
    setIsSubmitting(true)
    try {
      await ticketService.markReplySent(activeReply.id, DEMO_USER)
      onReplyUpdated()
      showFeedback('Customer reply marked as sent in demo mode. Ticket status updated to Pending.')
    } catch (err) {
      showFeedback(err instanceof Error ? err.message : 'Failed to send reply.', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleCopySentText() {
    if (!activeReply) return
    try {
      await navigator.clipboard.writeText(activeReply.body)
      showFeedback('Reply text copied to clipboard.')
    } catch {
      showFeedback('Could not copy the reply text in this browser.', 'error')
    }
  }

  return (
    <Card className="border-primary/25 bg-card shadow-xs">
      {/* Header */}
      <CardHeader className="border-b border-primary/15 bg-primary-tint/25 px-5 py-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Mail className="size-4.5 text-primary" aria-hidden="true" />
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-sm font-semibold text-foreground">
                  Customer Reply
                </CardTitle>
                {activeReply && !isForcingEdit ? (
                  <ReplyStateBadge state={activeReply.state} />
                ) : (
                  <Badge variant="neutral" className="gap-1 font-medium text-2xs">
                    Draft (New)
                  </Badge>
                )}
                {activeReply ? (
                  <span className="font-mono text-2xs text-subtle-foreground">
                    v{activeReply.version}
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground">
                To: <span className="font-medium text-foreground">{ticket.requesterName}</span> &lt;{ticket.requesterEmail}&gt;
              </p>
            </div>
          </div>

          {/* Template Selector (only available when editing) */}
          {(isDraft || isChangesRequested || isForcingEdit) && (
            <div className="flex items-center gap-1.5">
              <Select onValueChange={handleSelectTemplate}>
                <SelectTrigger className="h-8 w-44 text-xs" aria-label="Insert response template">
                  <span className="flex items-center gap-1 text-muted-foreground truncate">
                    <Sparkles className="size-3 text-primary shrink-0" aria-hidden="true" />
                    <span>Insert template…</span>
                  </span>
                </SelectTrigger>
                <SelectContent align="end" className="w-64">
                  {REPLY_TEMPLATES.map((tmpl) => (
                    <SelectItem key={tmpl.id} value={tmpl.id}>
                      <div className="py-0.5">
                        <span className="font-medium text-foreground">{tmpl.label}</span>
                        <p className="text-2xs text-muted-foreground">{tmpl.description}</p>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4 p-5">
        {/* ================= WORKFLOW STATUS BANNERS ================= */}

        {/* Changes Requested Banner */}
        {isChangesRequested && !isForcingEdit && activeReply && (
          <div className="rounded-md border border-danger/40 bg-danger-tint/40 p-4 text-xs">
            <div className="flex items-start gap-2.5">
              <ShieldAlert className="mt-0.5 size-4.5 shrink-0 text-danger" aria-hidden="true" />
              <div className="space-y-1.5 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-danger">
                    Supervisor Requested Revisions
                  </span>
                  <span className="text-2xs text-muted-foreground">
                    by {activeReply.reviewerName} · {activeReply.reviewedAt ? formatRelativeTime(activeReply.reviewedAt) : ''}
                  </span>
                </div>
                <div className="rounded bg-background/80 p-2.5 border border-danger/20 font-sans text-xs text-foreground">
                  &ldquo;{activeReply.reviewerFeedback}&rdquo;
                </div>
                <p className="text-2xs text-muted-foreground">
                  Please update the draft text below addressing the supervisor&apos;s feedback and resubmit for approval.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Pending Approval Banner */}
        {isPending && !isForcingEdit && activeReply && (
          <div className="rounded-md border border-warning/40 bg-warning-tint/40 p-4 text-xs">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <Clock className="mt-0.5 size-4.5 shrink-0 text-warning" aria-hidden="true" />
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">
                      Awaiting Supervisor Approval
                    </span>
                    <Badge variant="outline" className="border-warning/50 bg-card text-2xs text-warning">
                      In Review
                    </Badge>
                  </div>
                  <p className="text-muted-foreground leading-relaxed">
                    Submitted by <strong className="text-foreground">{activeReply.authorName}</strong> on{' '}
                    {activeReply.submittedAt ? formatDateTime(activeReply.submittedAt) : 'recently'}.
                    Human review is required before this reply can be sent.
                  </p>
                </div>
              </div>

              {/* Quick actions for supervisor review */}
              <div className="flex shrink-0 items-center gap-2">
                <Button
                  size="sm"
                  variant="default"
                  onClick={handleApprove}
                  disabled={isSubmitting}
                  className="gap-1.5"
                >
                  <ShieldCheck className="size-3.5" aria-hidden="true" />
                  Approve Reply
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowReviewComments((v) => !v)}
                  disabled={isSubmitting}
                  className="gap-1.5 text-danger hover:text-danger"
                >
                  <AlertTriangle className="size-3.5" aria-hidden="true" />
                  Request Changes
                </Button>
              </div>
            </div>

            {/* Changes comment form */}
            {showReviewComments && (
              <form onSubmit={handleRequestChanges} className="mt-3 border-t border-warning/20 pt-3 space-y-2">
                <label htmlFor="reviewer-feedback" className="text-xs font-semibold text-foreground">
                  Revisions required (internal feedback to author):
                </label>
                <Textarea
                  id="reviewer-feedback"
                  value={reviewerComment}
                  onChange={(e) => {
                    setReviewerComment(e.target.value)
                    if (reviewError) setReviewError(null)
                  }}
                  placeholder="Explain clearly what changes are needed before this reply can be approved…"
                  rows={2}
                  className={cn(reviewError && 'border-danger')}
                />
                {reviewError && (
                  <p role="alert" className="text-xs text-danger font-medium">
                    {reviewError}
                  </p>
                )}
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setShowReviewComments(false)
                      setReviewerComment('')
                    }}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" variant="danger" disabled={isSubmitting}>
                    Confirm &amp; Request Changes
                  </Button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* Approved Banner — Ready to Send */}
        {isApproved && !isForcingEdit && activeReply && (
          <div className="rounded-md border border-success/40 bg-success-tint/40 p-4 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="size-5 shrink-0 text-success" aria-hidden="true" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">
                      Reply Approved (v{activeReply.version})
                    </span>
                    <Badge variant="success" className="text-2xs py-0">
                      Approval Gate Cleared
                    </Badge>
                  </div>
                  <p className="text-muted-foreground mt-0.5">
                    Approved by <strong className="text-foreground">{activeReply.reviewerName}</strong>{' '}
                    {activeReply.reviewedAt ? `· ${formatRelativeTime(activeReply.reviewedAt)}` : ''}.
                    This response is authorized for demo sending only after this
                    exact version was approved.
                  </p>
                </div>
              </div>

              {/* Mandatory Action: Mark as Sent (Demo) */}
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="default"
                  onClick={() => setShowSendConfirm(true)}
                  disabled={isSubmitting}
                  className="gap-1.5 bg-success hover:bg-success/90 text-white font-medium shadow-xs"
                >
                  <Send className="size-3.5" aria-hidden="true" />
                  {isSubmitting ? 'Simulating delivery…' : 'Mark as Sent (Demo)'}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setIsForcingEdit(true)}
                  disabled={isSubmitting}
                  title="Editing will invalidate current approval"
                  className="text-xs"
                >
                  <Edit3 className="size-3.5" aria-hidden="true" />
                  Revise Draft
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Sent (Demo) Banner */}
        {isSent && !isForcingEdit && activeReply && (
          <div className="rounded-md border border-primary/30 bg-primary-tint/20 p-4 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="size-5 shrink-0 text-primary" aria-hidden="true" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">
                      Reply Marked as Sent (Demo)
                    </span>
                    <Badge variant="primary" className="text-2xs py-0">
                      Delivered (Simulated)
                    </Badge>
                  </div>
                  <p className="text-muted-foreground mt-0.5">
                    Simulated dispatch on {activeReply.sentAt ? formatDateTime(activeReply.sentAt) : ''} by{' '}
                    {activeReply.sentByActorName}. No external email or messaging API was triggered.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void handleCopySentText()}
                  className="text-xs gap-1"
                >
                  <Copy className="size-3" aria-hidden="true" />
                  Copy Text
                </Button>
                <Button
                  size="sm"
                  variant="default"
                  onClick={() => {
                    setBodyText('')
                    setIsForcingEdit(true)
                  }}
                  className="text-xs gap-1"
                >
                  <RotateCcw className="size-3" aria-hidden="true" />
                  Draft Another Reply
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Warning if agent is revising an approved reply */}
        {isForcingEdit && activeReply && activeReply.state === 'approved' && (
          <div className="rounded-md border border-warning/40 bg-warning-tint/30 p-3 text-xs flex items-center gap-2">
            <AlertTriangle className="size-4 shrink-0 text-warning" aria-hidden="true" />
            <span>
              <strong>Warning:</strong> Saving changes will invalidate the current supervisor approval and bump this reply to version {activeReply.version + 1}. It must be re-submitted for review.
            </span>
          </div>
        )}

        {/* ================= MESSAGE EDITOR / PREVIEW ================= */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <label htmlFor="customer-reply-text" className="font-medium text-foreground">
              {isSent && !isForcingEdit ? 'Sent Message Content' : isPending && !isForcingEdit ? 'Proposed Customer Reply' : 'Reply Draft'}
            </label>
            <span className="text-2xs text-subtle-foreground">
              {wordCount} words · {charCount} characters
            </span>
          </div>

          <Textarea
            id="customer-reply-text"
            value={bodyText}
            onChange={(e) => {
              setBodyText(e.target.value)
              if (validationError) setValidationError(null)
            }}
            rows={7}
            disabled={
              isSubmitting ||
              (!isForcingEdit && (isPending || isApproved || isSent))
            }
            placeholder="Write a clear, respectful, and helpful customer reply…"
            className={cn(
              'font-sans leading-relaxed',
              validationError && 'border-danger focus-visible:border-danger',
              !isForcingEdit && (isPending || isApproved || isSent) && 'bg-muted/40 cursor-not-allowed opacity-90',
            )}
            aria-describedby="reply-composer-help"
          />

          <p id="reply-composer-help" className="text-2xs text-subtle-foreground">
            Customer-facing replies are delivered to {ticket.requesterEmail}. All responses require human approval before demo delivery.
          </p>

          {validationError && (
            <p role="alert" className="text-xs font-medium text-danger flex items-center gap-1.5 mt-1">
              <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
              {validationError}
            </p>
          )}
        </div>

        {/* ================= COMPOSER ACTION BUTTONS ================= */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
          <div className="text-2xs text-subtle-foreground flex items-center gap-1">
            <ShieldCheck className="size-3.5 text-primary" aria-hidden="true" />
            <span>Approval Gate strictly enforced before dispatch</span>
          </div>

          <div className="flex items-center gap-2">
            {/* If currently editing an existing draft or revising */}
            {(isDraft || isChangesRequested || isForcingEdit) && (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleSaveDraft}
                  disabled={isSubmitting}
                  className="gap-1.5"
                >
                  <FileText className="size-3.5" aria-hidden="true" />
                  Save Draft
                </Button>
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  onClick={handleSubmitForApproval}
                  disabled={isSubmitting}
                  className="gap-1.5 font-medium shadow-xs"
                >
                  <FileCheck className="size-3.5" aria-hidden="true" />
                  {isChangesRequested ? 'Resubmit for Approval' : 'Submit for Approval'}
                </Button>
              </>
            )}

            {/* If pending approval and user wants to edit */}
            {isPending && !isForcingEdit && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsForcingEdit(true)}
                disabled={isSubmitting}
                className="gap-1.5 text-xs"
              >
                <Edit3 className="size-3.5" aria-hidden="true" />
                Withdraw to Edit
              </Button>
            )}

            {/* Cancel edit mode */}
            {isForcingEdit && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsForcingEdit(false)
                  if (activeReply) setBodyText(activeReply.body)
                }}
              >
                Cancel Edits
              </Button>
            )}
          </div>
        </div>

        <ConfirmDialog
          open={showSendConfirm}
          onOpenChange={setShowSendConfirm}
          title="Mark this reply as sent?"
          description={
            activeReply
              ? `This records reply v${activeReply.version} for ${ticket.id} as sent by ${DEMO_USER.name} (demo mode). No email is actually delivered.`
              : undefined
          }
          confirmLabel="Mark as Sent (Demo)"
          onConfirm={() => {
            void handleMarkSent()
          }}
        />
      </CardContent>
    </Card>
  )
}
