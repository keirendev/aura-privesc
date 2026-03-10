import { Search } from 'lucide-react'

export default function SearchInput({
  value,
  onChange,
  placeholder = 'Filter...',
}: {
  value: string
  onChange: (val: string) => void
  placeholder?: string
}) {
  return (
    <div className="relative mb-3">
      <Search
        size={16}
        className="absolute left-3 top-1/2 -translate-y-1/2"
        style={{ color: 'var(--muted)' }}
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-3 py-2 rounded-lg text-sm outline-none"
        style={{
          background: 'var(--bg)',
          color: 'var(--text)',
          border: '1px solid var(--border)',
        }}
      />
    </div>
  )
}
