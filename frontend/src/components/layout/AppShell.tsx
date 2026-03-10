import { type ReactNode } from 'react'
import Sidebar from './Sidebar'

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto" style={{ background: 'var(--bg)' }}>
        {children}
      </main>
    </div>
  )
}
