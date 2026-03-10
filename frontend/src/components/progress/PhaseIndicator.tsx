import { Check, Loader2, Circle } from 'lucide-react'

export default function PhaseIndicator({
  label,
  state,
  detail,
}: {
  label: string
  state: 'done' | 'active' | 'pending'
  detail?: string
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex-shrink-0">
        {state === 'done' && <Check size={18} style={{ color: 'var(--green)' }} />}
        {state === 'active' && <Loader2 size={18} className="animate-spin" style={{ color: 'var(--cyan)' }} />}
        {state === 'pending' && <Circle size={18} style={{ color: 'var(--muted)' }} />}
      </div>
      <div>
        <span
          className="text-sm"
          style={{
            color: state === 'active' ? 'var(--cyan)' : state === 'done' ? 'var(--text)' : 'var(--muted)',
            fontWeight: state === 'active' ? 600 : 400,
          }}
        >
          {label}
        </span>
        {detail && (
          <p className="text-xs" style={{ color: 'var(--muted)' }}>
            {detail}
          </p>
        )}
      </div>
    </div>
  )
}
