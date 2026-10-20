import * as React from 'react'
import {
  DEFAULT_PREFERENCES,
  loadPreferences,
  persistPreferences,
  PreferencesContext,
  type Density,
  type LandingPath,
  type Preferences,
  type PreferencesContextValue,
} from '@/lib/preferences'

/** Applies density to the document and persists harmless UI preferences. */
export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const [preferences, setPreferences] = React.useState<Preferences>(loadPreferences)

  React.useEffect(() => {
    document.documentElement.dataset.density = preferences.density
  }, [preferences.density])

  const update = React.useCallback((next: Preferences) => {
    setPreferences(next)
    persistPreferences(next)
  }, [])

  const value = React.useMemo<PreferencesContextValue>(
    () => ({
      preferences,
      setDensity: (density: Density) => update({ ...preferences, density }),
      setDefaultLanding: (defaultLanding: LandingPath) =>
        update({ ...preferences, defaultLanding }),
      resetPreferences: () => update({ ...DEFAULT_PREFERENCES }),
    }),
    [preferences, update],
  )

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  )
}
