import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { usePreferences } from '@/lib/preferences'

/**
 * Applies the locally stored "default landing page" once per app start.
 * Manual navigation to Overview later in the session is never intercepted.
 */
export function DefaultLandingRedirect() {
  const { preferences } = usePreferences()
  const navigate = useNavigate()
  const applied = React.useRef(false)

  React.useEffect(() => {
    if (applied.current) return
    applied.current = true
    if (window.location.pathname === '/' && preferences.defaultLanding !== '/') {
      navigate(preferences.defaultLanding, { replace: true })
    }
  }, [navigate, preferences.defaultLanding])

  return null
}
