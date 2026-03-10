import { useLocation } from 'react-router-dom'
import ScanForm from '../components/scan-form/ScanForm'

export default function NewScanPage() {
  const location = useLocation()
  const state = location.state as {
    url?: string
    config?: Record<string, unknown>
    recon_id?: string
    recon_label?: string
  } | null

  const subtitle = state?.url
    ? `Pre-filled from previous scan of ${state.url}. Adjust settings and launch.`
    : state?.recon_id
    ? `Using recon data: ${state.recon_label || state.recon_id}`
    : 'Configure and launch a new Aura privilege escalation scan.'

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--cyan)' }}>
        {state?.url ? 'Re-scan' : 'New Scan'}
      </h1>
      <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
        {subtitle}
      </p>
      <div
        className="p-6 rounded-lg"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <ScanForm
          initialUrl={state?.url}
          initialOptions={state?.config}
          initialReconId={state?.recon_id}
        />
      </div>
    </div>
  )
}
