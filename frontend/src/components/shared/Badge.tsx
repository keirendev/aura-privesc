const riskColors: Record<string, { bg: string; text: string }> = {
  critical: { bg: '#b71c1c', text: '#fff' },
  high: { bg: '#e65100', text: '#fff' },
  medium: { bg: '#f57f17', text: '#000' },
  low: { bg: '#1b5e20', text: '#fff' },
  info: { bg: '#37474f', text: '#ccc' },
}

export default function Badge({ value, type = 'risk' }: { value: string; type?: 'risk' | 'status' }) {
  if (type === 'status') {
    const statusColors: Record<string, { bg: string; text: string }> = {
      callable: { bg: 'var(--green)', text: '#000' },
      denied: { bg: 'var(--red)', text: '#fff' },
      not_found: { bg: 'var(--muted)', text: '#fff' },
      error: { bg: 'var(--yellow)', text: '#000' },
      queued: { bg: 'var(--muted)', text: '#fff' },
      running: { bg: 'var(--cyan)', text: '#000' },
      completed: { bg: 'var(--green)', text: '#000' },
      failed: { bg: 'var(--red)', text: '#fff' },
    }
    const c = statusColors[value] || { bg: 'var(--muted)', text: '#fff' }
    return (
      <span
        className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase"
        style={{ background: c.bg, color: c.text }}
      >
        {value}
      </span>
    )
  }

  const c = riskColors[value] || riskColors.info
  return (
    <span
      className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase"
      style={{ background: c.bg, color: c.text }}
    >
      {value}
    </span>
  )
}
