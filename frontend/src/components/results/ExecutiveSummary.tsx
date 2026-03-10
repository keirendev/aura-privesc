import type { ScanSummaryStats } from '../../api/types'

export default function ExecutiveSummary({ stats }: { stats: ScanSummaryStats }) {
  const cards = [
    { label: 'Objects Scanned', value: stats.objects_scanned, color: 'var(--cyan)' },
    { label: 'Accessible', value: stats.accessible, color: 'var(--cyan)' },
    { label: 'Writable', value: stats.writable, color: 'var(--yellow)' },
    { label: 'Proven Writes', value: stats.proven_writes, color: 'var(--red)' },
    { label: 'Callable Apex', value: stats.callable_apex, color: 'var(--cyan)' },
    ...(stats.graphql_available
      ? [{ label: 'GraphQL Counted', value: stats.graphql_counted, color: 'var(--purple)' }]
      : []),
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
      {cards.map((card) => (
        <div
          key={card.label}
          className="text-center p-4 rounded-lg"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="text-2xl font-bold" style={{ color: card.color }}>
            {card.value}
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
            {card.label}
          </div>
        </div>
      ))}
    </div>
  )
}
