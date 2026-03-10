import { Link } from 'react-router-dom'
import { useScans } from '../hooks/useScans'
import Badge from '../components/shared/Badge'
import { Plus, History, Shield } from 'lucide-react'

export default function DashboardPage() {
  const { data: scans } = useScans()
  const recent = scans?.slice(0, 5) || []

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--cyan)' }}>
        Dashboard
      </h1>
      <p className="text-sm mb-8" style={{ color: 'var(--muted)' }}>
        Salesforce Aura/Lightning Privilege Escalation Scanner
      </p>

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <Link
          to="/scan/new"
          className="flex items-center gap-3 p-5 rounded-lg transition-all hover:opacity-90"
          style={{ background: 'var(--card)', border: '2px solid var(--border)' }}
        >
          <Plus size={24} style={{ color: 'var(--cyan)' }} />
          <div>
            <div className="font-semibold">New Scan</div>
            <div className="text-sm" style={{ color: 'var(--muted)' }}>
              Start a new privilege escalation scan
            </div>
          </div>
        </Link>
        <Link
          to="/history"
          className="flex items-center gap-3 p-5 rounded-lg transition-all hover:opacity-90"
          style={{ background: 'var(--card)', border: '2px solid var(--border)' }}
        >
          <History size={24} style={{ color: 'var(--cyan)' }} />
          <div>
            <div className="font-semibold">Scan History</div>
            <div className="text-sm" style={{ color: 'var(--muted)' }}>
              View past scan results ({scans?.length || 0} scans)
            </div>
          </div>
        </Link>
      </div>

      {/* Recent scans */}
      {recent.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--cyan)' }}>
            Recent Scans
          </h2>
          <div className="space-y-2">
            {recent.map((scan) => (
              <Link
                key={scan.id}
                to={`/scan/${scan.id}`}
                className="flex items-center justify-between p-3 rounded-lg hover:opacity-90"
                style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-center gap-3">
                  <Shield size={16} style={{ color: 'var(--cyan)' }} />
                  <div>
                    <div className="text-sm font-medium">{scan.url}</div>
                    <div className="text-xs" style={{ color: 'var(--muted)' }}>
                      {new Date(scan.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
                <Badge value={scan.status} type="status" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {!recent.length && (
        <div className="text-center py-12" style={{ color: 'var(--muted)' }}>
          <Shield size={48} className="mx-auto mb-4 opacity-30" />
          <p>No scans yet. Start your first scan to see results here.</p>
        </div>
      )}
    </div>
  )
}
