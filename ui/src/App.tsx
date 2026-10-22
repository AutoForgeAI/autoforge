import { AppProvider } from './contexts/AppContext'
import { AppShell } from './components/layout/AppShell'
import { Modals } from './components/layout/Modals'
import { AuthGate } from './components/AuthGate'

function App() {
  return (
    <AuthGate>
      <AppProvider>
        <AppShell />
        <Modals />
      </AppProvider>
    </AuthGate>
  )
}

export default App
