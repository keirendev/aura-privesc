import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Plus, Search, History, Shield } from 'lucide-react'
import ThemeToggle from './ThemeToggle'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/scan/new', icon: Plus, label: 'New Scan' },
  { to: '/recon', icon: Search, label: 'Recon' },
  { to: '/history', icon: History, label: 'History' },
]

export default function Sidebar() {
  const { pathname } = useLocation()

  return (
    <aside
      className="w-56 flex flex-col border-r shrink-0"
      style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
    >
      <div className="p-4 flex items-center gap-2 border-b" style={{ borderColor: 'var(--border)' }}>
        <Shield size={24} style={{ color: 'var(--cyan)' }} />
        <span className="font-bold text-lg" style={{ color: 'var(--cyan)' }}>
          aura-privesc
        </span>
      </div>

      <nav className="flex-1 p-2 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => {
          const active = pathname === to
          return (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors"
              style={{
                background: active ? 'var(--border)' : 'transparent',
                color: active ? 'var(--cyan)' : 'var(--text)',
              }}
            >
              <Icon size={18} />
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t" style={{ borderColor: 'var(--border)' }}>
        <ThemeToggle />
      </div>
    </aside>
  )
}
