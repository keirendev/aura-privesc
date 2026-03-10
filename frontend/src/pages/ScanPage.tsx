import { useParams, useNavigate } from 'react-router-dom'
import { useJob } from '../hooks/useJob'
import { useScanResult } from '../hooks/useScanResult'
import ScanProgress from '../components/progress/ScanProgress'
import ExecutiveSummary from '../components/results/ExecutiveSummary'
import ObjectsTable from '../components/results/ObjectsTable'
import ApexTable from '../components/results/ApexTable'
import GraphQLTable from '../components/results/GraphQLTable'
import Badge from '../components/shared/Badge'
import { RotateCw } from 'lucide-react'
import { useEffect, useState } from 'react'

export default function ScanPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: status } = useJob(id)
  const { data: scanDetail, refetch } = useScanResult(id)

  // Refetch full scan when status changes to completed
  useEffect(() => {
    if (status?.status === 'completed' || status?.status === 'failed') {
      refetch()
    }
  }, [status?.status, refetch])

  if (!status && !scanDetail) {
    return <p style={{ color: 'var(--muted)' }}>Loading...</p>
  }

  const isRunning = status?.status === 'running' || status?.status === 'queued'
  const isFailed = status?.status === 'failed'
  const isComplete = status?.status === 'completed'

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--cyan)' }}>
            Scan Results
          </h1>
          {scanDetail && (
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              {scanDetail.url}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {status && <Badge value={status.status} type="status" />}
          {(isComplete || isFailed) && scanDetail && (
            <button
              type="button"
              onClick={() => navigate('/scan/new', {
                state: { url: scanDetail.url, config: scanDetail.config || {} },
              })}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium cursor-pointer"
              style={{ background: 'var(--bg)', color: 'var(--cyan)', border: '1px solid var(--border)' }}
            >
              <RotateCw size={12} />
              Re-scan
            </button>
          )}
        </div>
      </div>

      {/* Progress while running */}
      {isRunning && status && (
        <div
          className="p-6 rounded-lg mb-6"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <ScanProgress status={status} />
        </div>
      )}

      {/* Error state */}
      {isFailed && scanDetail?.error && (
        <div
          className="p-4 rounded-lg mb-6"
          style={{ background: 'var(--card)', border: '1px solid var(--red)' }}
        >
          <p className="font-semibold" style={{ color: 'var(--red)' }}>
            Scan Failed
          </p>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            {scanDetail.error}
          </p>
          {scanDetail.logs && <ScanLogs logs={scanDetail.logs} defaultOpen={true} />}
        </div>
      )}

      {/* Results when complete */}
      {isComplete && scanDetail?.result && scanDetail.summary && (
        <>
          <ExecutiveSummary stats={scanDetail.summary} />
          <ObjectsTable
            objects={scanDetail.result.objects}
            scanResult={scanDetail.result}
            scanId={id!}
          />
          {scanDetail.result.apex_results.length > 0 && (
            <ApexTable
              results={scanDetail.result.apex_results}
              scanResult={scanDetail.result}
            />
          )}
          {scanDetail.result.graphql_available && scanDetail.result.graphql_results.length > 0 && (
            <GraphQLTable
              results={scanDetail.result.graphql_results}
              scanResult={scanDetail.result}
            />
          )}

          {/* Discovery info */}
          {scanDetail.result.discovery && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--cyan)' }}>
                Discovery Info
              </h3>
              <div
                className="p-4 rounded-lg space-y-1 text-sm"
                style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
              >
                <div>
                  <span style={{ color: 'var(--muted)' }}>Endpoint:</span>{' '}
                  {scanDetail.result.discovery.endpoint}
                </div>
                <div>
                  <span style={{ color: 'var(--muted)' }}>Mode:</span>{' '}
                  {scanDetail.result.discovery.mode}
                </div>
                {scanDetail.result.discovery.fwuid && (
                  <div>
                    <span style={{ color: 'var(--muted)' }}>fwuid:</span>{' '}
                    <span className="text-xs">{scanDetail.result.discovery.fwuid}</span>
                  </div>
                )}
                {scanDetail.result.user_info && (
                  <>
                    {scanDetail.result.user_info.display_name && (
                      <div>
                        <span style={{ color: 'var(--muted)' }}>User:</span>{' '}
                        {scanDetail.result.user_info.display_name}
                      </div>
                    )}
                    <div>
                      <span style={{ color: 'var(--muted)' }}>Guest:</span>{' '}
                      {scanDetail.result.user_info.is_guest ? 'Yes' : 'No'}
                    </div>
                  </>
                )}
                <div>
                  <span style={{ color: 'var(--muted)' }}>SOQL:</span>{' '}
                  {scanDetail.result.soql_capable ? (
                    <span style={{ color: 'var(--green)' }}>Available</span>
                  ) : (
                    <span style={{ color: 'var(--red)' }}>Not available</span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Logs for completed scans */}
          {scanDetail.logs && <ScanLogs logs={scanDetail.logs} />}
        </>
      )}
    </div>
  )
}

function ScanLogs({ logs, defaultOpen = false }: { logs: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="mt-4">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs cursor-pointer"
        style={{ color: 'var(--cyan)' }}
      >
        {open ? 'Hide' : 'Show'} scan logs ({logs.split('\n').filter(Boolean).length} lines)
      </button>
      {open && (
        <pre
          className="mt-2 p-3 rounded text-xs overflow-x-auto max-h-96 overflow-y-auto"
          style={{
            background: 'var(--bg)',
            color: 'var(--muted)',
            border: '1px solid var(--border)',
          }}
        >
          {logs}
        </pre>
      )}
    </div>
  )
}
