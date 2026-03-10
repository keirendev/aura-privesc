import { Routes, Route } from 'react-router-dom'
import { ThemeContext, useThemeProvider } from './hooks/useTheme'
import AppShell from './components/layout/AppShell'
import DashboardPage from './pages/DashboardPage'
import NewScanPage from './pages/NewScanPage'
import ScanPage from './pages/ScanPage'
import ScanHistoryPage from './pages/ScanHistoryPage'
import RecordsPage from './pages/RecordsPage'

export default function App() {
  const theme = useThemeProvider()

  return (
    <ThemeContext.Provider value={theme}>
      <div className={theme.isDark ? '' : 'light'}>
        <AppShell>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/scan/new" element={<NewScanPage />} />
            <Route path="/scan/:id" element={<ScanPage />} />
            <Route path="/scan/:id/records/:source/:objectName" element={<RecordsPage />} />
            <Route path="/history" element={<ScanHistoryPage />} />
          </Routes>
        </AppShell>
      </div>
    </ThemeContext.Provider>
  )
}
