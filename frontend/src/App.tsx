import { Routes, Route } from 'react-router-dom'
import { useTheme } from './hooks/useTheme'
import AppShell from './components/layout/AppShell'
import DashboardPage from './pages/DashboardPage'
import NewScanPage from './pages/NewScanPage'
import ScanPage from './pages/ScanPage'
import ScanHistoryPage from './pages/ScanHistoryPage'

export default function App() {
  const { isDark } = useTheme()

  return (
    <div className={isDark ? '' : 'light'}>
      <AppShell>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/scan/new" element={<NewScanPage />} />
          <Route path="/scan/:id" element={<ScanPage />} />
          <Route path="/history" element={<ScanHistoryPage />} />
        </Routes>
      </AppShell>
    </div>
  )
}
