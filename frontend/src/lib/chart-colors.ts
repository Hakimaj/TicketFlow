import type { TicketCategory } from '@/types/ticket'

/**
 * Shared chart palette. One blue-teal family plus neutral support colors —
 * no rainbow charts. Kept outside feature folders so every chart uses the
 * same category colors.
 */

export const TREND_COLORS = {
  received: 'var(--primary)',
  resolved: '#0d9488',
} as const

export const CATEGORY_COLORS: Record<TicketCategory, string> = {
  billing: '#2563eb',
  delivery: '#0d9488',
  technical: '#7c3aed',
  returns: '#d97706',
  general: '#64748b',
}
