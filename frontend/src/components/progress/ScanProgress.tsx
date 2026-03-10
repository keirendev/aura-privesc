import type { ScanStatus } from '../../api/types'
import PhaseIndicator from './PhaseIndicator'

const phases = [
  { key: 'discovery', label: 'Discovery' },
  { key: 'user_context', label: 'User Context' },
  { key: 'enumeration', label: 'Object Enumeration' },
  { key: 'crud_test', label: 'CRUD Testing' },
  { key: 'apex', label: 'Apex Testing' },
  { key: 'graphql', label: 'GraphQL Enumeration' },
  { key: 'complete', label: 'Complete' },
]

export default function ScanProgress({ status }: { status: ScanStatus }) {
  const currentPhaseIdx = phases.findIndex((p) => p.key === status.phase)

  return (
    <div className="space-y-6">
      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-sm mb-2">
          <span style={{ color: 'var(--muted)' }}>Progress</span>
          <span style={{ color: 'var(--cyan)' }}>{status.progress}%</span>
        </div>
        <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${status.progress}%`,
              background: 'var(--cyan)',
            }}
          />
        </div>
      </div>

      {/* Phase timeline */}
      <div className="space-y-2">
        {phases.map((phase, idx) => (
          <PhaseIndicator
            key={phase.key}
            label={phase.label}
            state={
              idx < currentPhaseIdx
                ? 'done'
                : idx === currentPhaseIdx
                ? 'active'
                : 'pending'
            }
            detail={idx === currentPhaseIdx ? status.phase_detail : undefined}
          />
        ))}
      </div>
    </div>
  )
}
