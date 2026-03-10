import { Link, useNavigate } from 'react-router-dom'
import { useScans, useDeleteScan } from '../../hooks/useScans'
import Badge from '../shared/Badge'
import { Trash2, ExternalLink, RotateCw } from 'lucide-react'
import { toast } from 'sonner'

export default function ScanHistory() {
  const { data: scans, isLoading } = useScans()
  const deleteScan = useDeleteScan()
  const navigate = useNavigate()

  if (isLoading) {
    return <p style={{ color: 'var(--muted)' }}>Loading...</p>
  }

  if (!scans?.length) {
    return (
      <p style={{ color: 'var(--muted)' }}>
        No scans yet. <Link to="/scan/new" style={{ color: 'var(--cyan)' }}>Start one</Link>.
      </p>
    )
  }

  const handleRescan = async (scan: { id: string; url: string }, e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      const detail = await (await fetch(`/api/scans/${scan.id}`)).json()
      navigate('/scan/new', {
        state: { url: scan.url, config: detail.config || {} },
      })
    } catch {
      // Fall back to just URL if detail fetch fails
      navigate('/scan/new', { state: { url: scan.url, config: {} } })
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('Delete this scan?')) return
    try {
      await deleteScan.mutateAsync(id)
      toast.success('Scan deleted')
    } catch {
      toast.error('Failed to delete scan')
    }
  }

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: 'var(--border)' }}>
            <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Target</th>
            <th className="text-center px-3 py-2" style={{ color: 'var(--cyan)' }}>Status</th>
            <th className="text-center px-3 py-2" style={{ color: 'var(--cyan)' }}>Findings</th>
            <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Date</th>
            <th className="text-center px-3 py-2" style={{ color: 'var(--cyan)' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((scan) => {
            const summary = scan.summary
            const findings = summary
              ? `${summary.accessible} obj, ${summary.callable_apex} apex`
              : '-'

            return (
              <tr key={scan.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td className="px-3 py-2">
                  <Link
                    to={`/scan/${scan.id}`}
                    className="font-medium hover:underline"
                    style={{ color: 'var(--text)' }}
                  >
                    {scan.url}
                  </Link>
                </td>
                <td className="text-center px-3 py-2">
                  <Badge value={scan.status} type="status" />
                </td>
                <td className="text-center px-3 py-2" style={{ color: 'var(--muted)' }}>
                  {findings}
                </td>
                <td className="px-3 py-2" style={{ color: 'var(--muted)' }}>
                  {new Date(scan.created_at).toLocaleDateString()}
                </td>
                <td className="text-center px-3 py-2">
                  <div className="flex items-center justify-center gap-2">
                    <Link to={`/scan/${scan.id}`} style={{ color: 'var(--cyan)' }} title="View">
                      <ExternalLink size={14} />
                    </Link>
                    <button
                      type="button"
                      onClick={(e) => handleRescan(scan, e)}
                      className="cursor-pointer"
                      style={{ color: 'var(--green)' }}
                      title="Re-scan with settings"
                    >
                      <RotateCw size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleDelete(scan.id, e)}
                      className="cursor-pointer"
                      style={{ color: 'var(--red)' }}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
