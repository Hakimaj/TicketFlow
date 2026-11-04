import { AppRouter } from './router'
import { DefaultLandingRedirect } from './default-landing'
import { PreferencesProvider } from './preferences-provider'
import { AuthProvider } from '@/auth'

export default function App() {
  return (
    <PreferencesProvider>
      <AuthProvider>
        <DefaultLandingRedirect />
        <AppRouter />
      </AuthProvider>
    </PreferencesProvider>
  )
}
