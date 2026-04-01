import { AppProvider } from './contexts/AppContext'
import { AppShell } from './components/layout/AppShell'
import { Modals } from './components/layout/Modals'

function App() {
  return (
    <AppProvider>
      <AppShell />
      <Modals />
    </AppProvider>
  )
}

export default App
