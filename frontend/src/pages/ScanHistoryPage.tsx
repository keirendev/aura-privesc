import ScanHistory from '../components/history/ScanHistory'

export default function ScanHistoryPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--cyan)' }}>
        Scan History
      </h1>
      <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
        All past scans and their results.
      </p>
      <ScanHistory />
    </div>
  )
}
