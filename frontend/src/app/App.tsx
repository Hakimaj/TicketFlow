import { AppRouter } from './router'
import { DefaultLandingRedirect } from './default-landing'
import { PreferencesProvider } from './preferences-provider'

export default function App() {
  return (
    <PreferencesProvider>
      <DefaultLandingRedirect />
      <AppRouter />
    </PreferencesProvider>
  )
}
