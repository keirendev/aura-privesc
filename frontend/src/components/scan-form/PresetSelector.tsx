import { useQuery } from '@tanstack/react-query'
import { getPresets } from '../../api/client'
import type { PresetConfig } from '../../api/types'
import { Zap, Shield, Eye } from 'lucide-react'

const presetIcons: Record<string, typeof Zap> = {
  quick: Zap,
  full: Shield,
  stealth: Eye,
}

export default function PresetSelector({
  selected,
  onSelect,
}: {
  selected: string | null
  onSelect: (preset: PresetConfig) => void
}) {
  const { data: presets } = useQuery({
    queryKey: ['presets'],
    queryFn: getPresets,
  })

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {presets?.map((preset) => {
        const Icon = presetIcons[preset.id] || Shield
        const isSelected = selected === preset.id
        return (
          <button
            key={preset.id}
            onClick={() => onSelect(preset)}
            className="p-4 rounded-lg text-left transition-all cursor-pointer"
            style={{
              background: isSelected ? 'var(--border)' : 'var(--card)',
              border: `2px solid ${isSelected ? 'var(--cyan)' : 'var(--border)'}`,
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon size={20} style={{ color: 'var(--cyan)' }} />
              <span className="font-semibold">{preset.label}</span>
            </div>
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              {preset.description}
            </p>
          </button>
        )
      })}
    </div>
  )
}
