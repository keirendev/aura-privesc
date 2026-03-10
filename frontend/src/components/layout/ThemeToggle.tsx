import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../../hooks/useTheme'

export default function ThemeToggle() {
  const { isDark, toggle } = useTheme()

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors cursor-pointer"
      style={{
        background: 'var(--bg)',
        color: 'var(--muted)',
        border: '1px solid var(--border)',
      }}
    >
      {isDark ? <Sun size={14} /> : <Moon size={14} />}
      {isDark ? 'Light mode' : 'Dark mode'}
    </button>
  )
}
