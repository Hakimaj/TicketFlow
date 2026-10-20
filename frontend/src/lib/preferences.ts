import * as React from 'react'

/**
 * Local, presentation-only preferences. Nothing here is sent to a server and
 * no customer, ticket or authentication data is ever stored in localStorage.
 */

export type Density = 'comfortable' | 'compact'

export const LANDING_OPTIONS = [
  { value: '/', label: 'Overview' },
  { value: '/tickets', label: 'All Tickets' },
  { value: '/tickets/mine', label: 'My Tickets' },
  { value: '/tickets/unassigned', label: 'Unassigned' },
  { value: '/tickets/needs-review', label: 'Needs Review' },
  { value: '/approvals', label: 'Reply Approvals' },
  { value: '/analytics', label: 'Analytics' },
  { value: '/activity', label: 'Activity Logs' },
] as const

export type LandingPath = (typeof LANDING_OPTIONS)[number]['value']

export interface Preferences {
  density: Density
  /** Route opened when the app starts at `/` in a new tab or reload. */
  defaultLanding: LandingPath
}

export const DEFAULT_PREFERENCES: Preferences = {
  density: 'comfortable',
  defaultLanding: '/',
}

const STORAGE_KEY = 'ticketflow.preferences.v1'

function isLandingPath(value: unknown): value is LandingPath {
  return LANDING_OPTIONS.some((option) => option.value === value)
}

/** Validate untrusted localStorage content; unknown values fall back safely. */
export function parsePreferences(raw: string | null): Preferences {
  if (!raw) return { ...DEFAULT_PREFERENCES }
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return { ...DEFAULT_PREFERENCES }
    const record = parsed as Record<string, unknown>
    return {
      density: record.density === 'compact' ? 'compact' : 'comfortable',
      defaultLanding: isLandingPath(record.defaultLanding)
        ? record.defaultLanding
        : DEFAULT_PREFERENCES.defaultLanding,
    }
  } catch {
    return { ...DEFAULT_PREFERENCES }
  }
}

export function loadPreferences(): Preferences {
  try {
    return parsePreferences(window.localStorage.getItem(STORAGE_KEY))
  } catch {
    return { ...DEFAULT_PREFERENCES }
  }
}

export function persistPreferences(preferences: Preferences): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
  } catch {
    /* Storage may be unavailable (private mode); preferences remain session-local. */
  }
}

export interface PreferencesContextValue {
  preferences: Preferences
  setDensity: (density: Density) => void
  setDefaultLanding: (path: LandingPath) => void
  resetPreferences: () => void
}

export const PreferencesContext =
  React.createContext<PreferencesContextValue | null>(null)

export function usePreferences(): PreferencesContextValue {
  const context = React.useContext(PreferencesContext)
  if (!context) {
    throw new Error('usePreferences must be used inside PreferencesProvider')
  }
  return context
}
