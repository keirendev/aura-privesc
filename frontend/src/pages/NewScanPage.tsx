import ScanForm from '../components/scan-form/ScanForm'

export default function NewScanPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--cyan)' }}>
        New Scan
      </h1>
      <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
        Configure and launch a new Aura privilege escalation scan.
      </p>
      <div
        className="p-6 rounded-lg"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <ScanForm />
      </div>
    </div>
  )
}
