import type { Ticket } from '@/types/ticket'

export interface ReplyTemplate {
  id: string
  label: string
  description: string
  generate: (ticket: Ticket) => string
}

export const REPLY_TEMPLATES: ReplyTemplate[] = [
  {
    id: 'billing_payment',
    label: 'Billing / Payment Issue',
    description: 'Investigating charge discrepancy or transaction delay',
    generate: (ticket: Ticket) =>
      `Dear ${ticket.requesterName},\n\n` +
      `Thank you for contacting TicketFlow support regarding your payment inquiry for ticket ${ticket.id}.\n\n` +
      `Our billing team is currently reviewing the transaction details with our payment processing partner. We are verifying the transaction reference to ensure accurate reconciliation.\n\n` +
      `We will follow up with an update as soon as the verification is finalized. If you have any additional receipts or transaction IDs to share, please reply directly to this ticket.\n\n` +
      `Best regards,\n` +
      `Billing Support Team`,
  },
  {
    id: 'delayed_delivery',
    label: 'Delayed Delivery Update',
    description: 'Checking dispatch status with courier network',
    generate: (ticket: Ticket) =>
      `Dear ${ticket.requesterName},\n\n` +
      `Thank you for checking in regarding the delivery status for ticket ${ticket.id}.\n\n` +
      `We have contacted our dispatch coordinator and regional courier partner to verify the current transit status of your package. We are tracking the consignment to confirm an updated delivery window.\n\n` +
      `We understand the importance of receiving your order on time and will provide the courier update as soon as received.\n\n` +
      `Best regards,\n` +
      `Logistics Support Team`,
  },
  {
    id: 'technical_troubleshooting',
    label: 'Technical Troubleshooting',
    description: 'Guidance and steps to isolate website/app technical issues',
    generate: (ticket: Ticket) =>
      `Dear ${ticket.requesterName},\n\n` +
      `Thank you for reporting the technical issue you experienced regarding ticket ${ticket.id}.\n\n` +
      `Our engineering team has received your report. In the meantime, to help us pinpoint the problem:\n` +
      `1. Please try clearing your browser cache and cookies, or test using a private/incognito window.\n` +
      `2. If you are using a mobile browser, check whether refreshing the page resolves the display.\n\n` +
      `Please let us know if the issue persists and share any error messages that appear.\n\n` +
      `Best regards,\n` +
      `Technical Support Team`,
  },
  {
    id: 'return_refund',
    label: 'Return / Refund Inquiry',
    description: 'Instructions for return inspection and replacement steps',
    generate: (ticket: Ticket) =>
      `Dear ${ticket.requesterName},\n\n` +
      `Thank you for submitting your return inquiry for ticket ${ticket.id}.\n\n` +
      `Our returns team is reviewing your request against our store return policy. Please ensure the item remains in its original packaging with all tags, accessories, and documentation intact.\n\n` +
      `We will follow up shortly with specific instructions regarding return package pickup or drop-off.\n\n` +
      `Best regards,\n` +
      `Returns & Exchanges Team`,
  },
  {
    id: 'general_acknowledgement',
    label: 'General Acknowledgement',
    description: 'Confirming receipt of ticket while investigation is underway',
    generate: (ticket: Ticket) =>
      `Dear ${ticket.requesterName},\n\n` +
      `Thank you for reaching out to TicketFlow support regarding ticket ${ticket.id}.\n\n` +
      `We have received your message and an agent is currently reviewing your details. We strive to provide a comprehensive response as quickly as possible.\n\n` +
      `If you have any further details to add in the meantime, please reply directly to this thread.\n\n` +
      `Best regards,\n` +
      `Customer Support Team`,
  },
]

