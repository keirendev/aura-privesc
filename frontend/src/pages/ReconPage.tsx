import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Search,
  Terminal,
  CheckCircle,
  XCircle,
  Loader2,
  Trash2,
  ArrowRight,
} from 'lucide-react'
import { useSfCliCheck, useRecons, useReconStatus, useCreateRecon, useCancelRecon, useDeleteRecon } from '../hooks/useRecons'
import type { ReconSummary } from '../api/types'

const PHASE_STEPS = ['sf_check', 'login', 'objects', 'apex', 'complete'] as const

function PhaseProgress({ phase, detail, status }: { phase: string; detail: string; status: string }) {
  const labels: Record<string, string> = {
    sf_check: 'CLI Check',
    login: 'Login',
    objects: 'Objects',
    apex: 'Apex',
    complete: 'Done',
  }

  const currentIdx = PHASE_STEPS.indexOf(phase as typeof PHASE_STEPS[number])

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {PHASE_STEPS.map((step, idx) => {
          let color = 'var(--muted)'
          if (status === 'failed') {
            if (idx < currentIdx) color = 'var(--cyan)'
            else if (idx === currentIdx) color = '#ef4444'
          } else if (idx < currentIdx || status === 'completed') {
            color = 'var(--cyan)'
          } else if (idx === currentIdx) {
            color = 'var(--yellow, #eab308)'
          }

          return (
            <div key={step} className="flex items-center gap-1">
              {idx > 0 && (
                <div
                  className="w-6 h-px"
                  style={{ background: idx <= currentIdx ? 'var(--cyan)' : 'var(--border)' }}
                />
              )}
              <div className="flex items-center gap-1.5">
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ background: color }}
                />
                <span className="text-xs" style={{ color }}>{labels[step]}</span>
              </div>
            </div>
          )
        })}
      </div>
      {detail && (
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          {detail}
        </p>
      )}
    </div>
  )
}

function ReconHistoryRow({ recon, onDelete }: { recon: ReconSummary; onDelete: (id: string) => void }) {
  const navigate = useNavigate()
  const delMut = useDeleteRecon()

  const handleDelete = () => {
    if (!confirm('Delete this recon?')) return
    delMut.mutate(recon.id, {
      onSuccess: () => {
        onDelete(recon.id)
        toast.success('Recon deleted')
      },
    })
  }

  const statusColor =
    recon.status === 'completed' ? 'var(--cyan)' :
    recon.status === 'failed' ? '#ef4444' :
    recon.status === 'running' ? 'var(--yellow, #eab308)' :
    'var(--muted)'

  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}>
      <td className="py-2 px-3 text-sm">{recon.instance_url}</td>
      <td className="py-2 px-3 text-sm" style={{ color: 'var(--muted)' }}>{recon.username || '-'}</td>
      <td className="py-2 px-3 text-sm" style={{ color: statusColor }}>{recon.status}</td>
      <td className="py-2 px-3 text-sm">{recon.object_count ?? '-'}</td>
      <td className="py-2 px-3 text-sm">{recon.apex_count ?? '-'}</td>
      <td className="py-2 px-3 text-sm" style={{ color: 'var(--muted)' }}>
        {new Date(recon.created_at).toLocaleDateString()}
      </td>
      <td className="py-2 px-3 text-sm">
        <div className="flex items-center gap-2">
          {recon.status === 'completed' && (
            <button
              onClick={() =>
                navigate('/scan/new', { state: { recon_id: recon.id, recon_label: `${recon.instance_url} (${recon.object_count ?? 0} objects, ${recon.apex_count ?? 0} apex)` } })
              }
              className="flex items-center gap-1 px-2 py-1 rounded text-xs cursor-pointer"
              style={{ background: 'var(--cyan)', color: '#000' }}
              title="Use in Scan"
            >
              <ArrowRight size={12} />
              Use in Scan
            </button>
          )}
          <button
            onClick={handleDelete}
            className="cursor-pointer"
            style={{ color: 'var(--muted)' }}
            title="Delete"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  )
}

export default function ReconPage() {
  const cliCheck = useSfCliCheck()
  const reconsQuery = useRecons()
  const createRecon = useCreateRecon()
  const cancelReconMut = useCancelRecon()

  const [instanceUrl, setInstanceUrl] = useState('')
  const [alias, setAlias] = useState('')
  const [accessToken, setAccessToken] = useState('')
  const [skipObjects, setSkipObjects] = useState(false)
  const [skipApex, setSkipApex] = useState(false)
  const [activeReconId, setActiveReconId] = useState<string | null>(null)

  const isRunning = activeReconId !== null
  const reconStatus = useReconStatus(activeReconId, isRunning)

  const [lastError, setLastError] = useState<string | null>(null)

  // Clear active recon when it finishes
  useEffect(() => {
    if (reconStatus.data && (reconStatus.data.status === 'completed' || reconStatus.data.status === 'failed')) {
      if (reconStatus.data.status === 'completed') {
        toast.success('Recon completed')
        setLastError(null)
      } else {
        const errMsg = reconStatus.data.error || 'Unknown error'
        toast.error('Recon failed')
        setLastError(errMsg)
      }
      setActiveReconId(null)
      reconsQuery.refetch()
    }
  }, [reconStatus.data?.status])

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!instanceUrl.trim()) {
      toast.error('Instance URL is required')
      return
    }
    if (!alias.trim()) {
      toast.error('Alias is required')
      return
    }
    if (!accessToken.trim()) {
      toast.error('Session ID is required')
      return
    }
    try {
      const result = await createRecon.mutateAsync({
        instance_url: instanceUrl.trim(),
        alias: alias.trim(),
        access_token: accessToken.trim(),
        skip_objects: skipObjects,
        skip_apex: skipApex,
      })
      setActiveReconId(result.id)
      toast.success('Recon started')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start recon'
      toast.error(msg)
    }
  }

  const cliInstalled = cliCheck.data?.installed ?? false

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--cyan)' }}>
          SFDX Recon
        </h1>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Authenticate to a Salesforce org with a session ID, then enumerate objects and @AuraEnabled Apex methods via the sf CLI.
        </p>
      </div>

      {/* SF CLI status banner */}
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-lg"
        style={{
          background: cliCheck.isLoading ? 'var(--card)' : cliInstalled ? 'rgba(0, 200, 150, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          border: `1px solid ${cliCheck.isLoading ? 'var(--border)' : cliInstalled ? 'var(--cyan)' : '#ef4444'}`,
        }}
      >
        {cliCheck.isLoading ? (
          <Loader2 size={18} className="animate-spin" style={{ color: 'var(--muted)' }} />
        ) : cliInstalled ? (
          <CheckCircle size={18} style={{ color: 'var(--cyan)' }} />
        ) : (
          <XCircle size={18} style={{ color: '#ef4444' }} />
        )}
        <div>
          <span className="text-sm font-medium">
            {cliCheck.isLoading
              ? 'Checking Salesforce CLI...'
              : cliInstalled
              ? 'Salesforce CLI detected'
              : 'Salesforce CLI not found'}
          </span>
          {!cliCheck.isLoading && !cliInstalled && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
              Install it from{' '}
              <a
                href="https://developer.salesforce.com/tools/salesforcecli"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
                style={{ color: 'var(--cyan)' }}
              >
                developer.salesforce.com
              </a>
            </p>
          )}
        </div>
      </div>

      {/* Launch form */}
      <div
        className="p-5 rounded-lg"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <form onSubmit={handleStart} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm">
              <span className="font-medium">Instance URL</span>
              <input
                type="text"
                value={instanceUrl}
                onChange={(e) => setInstanceUrl(e.target.value)}
                placeholder="https://myorg.sandbox.my.salesforce.com"
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                style={{
                  background: 'var(--bg)',
                  color: 'var(--text)',
                  border: '1px solid var(--border)',
                }}
                required
              />
            </label>
            <label className="text-sm">
              <span className="font-medium">Alias</span>
              <input
                type="text"
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
                placeholder="my-org"
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                style={{
                  background: 'var(--bg)',
                  color: 'var(--text)',
                  border: '1px solid var(--border)',
                }}
                required
              />
            </label>
          </div>
          <label className="text-sm block">
            <span className="font-medium">Session ID</span>
            <input
              type="password"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
              placeholder="00D..."
              className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none font-mono"
              style={{
                background: 'var(--bg)',
                color: 'var(--text)',
                border: '1px solid var(--border)',
              }}
              required
            />
          </label>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={skipObjects}
                onChange={() => setSkipObjects(!skipObjects)}
                className="accent-[var(--cyan)]"
              />
              Skip objects
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={skipApex}
                onChange={() => setSkipApex(!skipApex)}
                className="accent-[var(--cyan)]"
              />
              Skip Apex
            </label>
          </div>
          <button
            type="submit"
            disabled={!cliInstalled || isRunning || createRecon.isPending}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm transition-opacity cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ background: 'var(--cyan)', color: '#000' }}
          >
            {isRunning ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Terminal size={16} />
                Start Recon
              </>
            )}
          </button>
        </form>
      </div>

      {/* Active recon progress */}
      {isRunning && reconStatus.data && (
        <div
          className="p-5 rounded-lg"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium" style={{ color: 'var(--cyan)' }}>
              Active Recon
            </h3>
            <button
              onClick={() => {
                cancelReconMut.mutate(activeReconId!, {
                  onSuccess: () => {
                    setActiveReconId(null)
                    setLastError(null)
                    reconsQuery.refetch()
                    toast.success('Recon cancelled')
                  },
                  onError: () => {
                    toast.error('Failed to cancel')
                  },
                })
              }}
              disabled={cancelReconMut.isPending}
              className="flex items-center gap-1 px-3 py-1 rounded text-xs cursor-pointer"
              style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid #ef4444' }}
            >
              <XCircle size={12} />
              Cancel
            </button>
          </div>
          <PhaseProgress
            phase={reconStatus.data.phase}
            detail={reconStatus.data.phase_detail}
            status={reconStatus.data.status}
          />
        </div>
      )}

      {/* Error display */}
      {lastError && (
        <div
          className="p-4 rounded-lg text-sm"
          style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', color: '#ef4444' }}
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="font-medium">Recon failed: </span>
              <span style={{ color: 'var(--text)' }}>{lastError}</span>
            </div>
            <button
              onClick={() => setLastError(null)}
              className="shrink-0 cursor-pointer text-xs underline"
              style={{ color: 'var(--muted)' }}
            >
              dismiss
            </button>
          </div>
        </div>
      )}

      {/* History */}
      <div>
        <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
          <Search size={18} style={{ color: 'var(--cyan)' }} />
          Recon History
        </h2>
        {reconsQuery.isLoading ? (
          <p className="text-sm" style={{ color: 'var(--muted)' }}>Loading...</p>
        ) : !reconsQuery.data?.length ? (
          <p className="text-sm" style={{ color: 'var(--muted)' }}>No recon runs yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--border)' }}>
            <table className="w-full text-left" style={{ background: 'var(--card)' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th className="py-2 px-3 text-xs font-medium" style={{ color: 'var(--muted)' }}>Instance</th>
                  <th className="py-2 px-3 text-xs font-medium" style={{ color: 'var(--muted)' }}>User</th>
                  <th className="py-2 px-3 text-xs font-medium" style={{ color: 'var(--muted)' }}>Status</th>
                  <th className="py-2 px-3 text-xs font-medium" style={{ color: 'var(--muted)' }}>Objects</th>
                  <th className="py-2 px-3 text-xs font-medium" style={{ color: 'var(--muted)' }}>Apex</th>
                  <th className="py-2 px-3 text-xs font-medium" style={{ color: 'var(--muted)' }}>Date</th>
                  <th className="py-2 px-3 text-xs font-medium" style={{ color: 'var(--muted)' }}></th>
                </tr>
              </thead>
              <tbody>
                {reconsQuery.data.map((r) => (
                  <ReconHistoryRow
                    key={r.id}
                    recon={r}
                    onDelete={() => reconsQuery.refetch()}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
