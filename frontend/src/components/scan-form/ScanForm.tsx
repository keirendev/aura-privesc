import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useCreateScan } from '../../hooks/useScans'
import type { PresetConfig, ScanCreateRequest } from '../../api/types'
import PresetSelector from './PresetSelector'
import AdvancedOptions from './AdvancedOptions'
import { Play } from 'lucide-react'

interface ScanFormProps {
  initialUrl?: string
  initialOptions?: Omit<ScanCreateRequest, 'url'>
}

export default function ScanForm({ initialUrl, initialOptions }: ScanFormProps = {}) {
  const navigate = useNavigate()
  const createScan = useCreateScan()
  const [url, setUrl] = useState(initialUrl || '')
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null)
  const [options, setOptions] = useState<Omit<ScanCreateRequest, 'url'>>(initialOptions || {})

  const handlePreset = (preset: PresetConfig) => {
    setSelectedPreset(preset.id)
    const { token, sid, manual_context, manual_endpoint, proxy, insecure, crm_domain } = options
    setOptions({ token, sid, manual_context, manual_endpoint, proxy, insecure, crm_domain, ...preset.config })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) {
      toast.error('URL is required')
      return
    }

    try {
      const result = await createScan.mutateAsync({ url: url.trim(), ...options })
      toast.success('Scan started')
      navigate(`/scan/${result.id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start scan'
      toast.error(msg)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <PresetSelector selected={selectedPreset} onSelect={handlePreset} />

      <div className="mb-4">
        <label className="block text-sm font-medium mb-1">Target URL</label>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://target.force.com"
          className="w-full px-3 py-2 rounded-lg text-sm outline-none"
          style={{
            background: 'var(--bg)',
            color: 'var(--text)',
            border: '1px solid var(--border)',
          }}
          required
        />
      </div>

      <AdvancedOptions values={options} onChange={setOptions} />

      <button
        type="submit"
        disabled={createScan.isPending}
        className="flex items-center gap-2 px-6 py-2.5 rounded-lg font-semibold text-sm transition-opacity cursor-pointer disabled:opacity-50"
        style={{ background: 'var(--cyan)', color: '#000' }}
      >
        <Play size={16} />
        {createScan.isPending ? 'Starting...' : 'Start Scan'}
      </button>
    </form>
  )
}
