import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { ScanCreateRequest } from '../../api/types'

type FormData = Omit<ScanCreateRequest, 'url'>

export default function AdvancedOptions({
  values,
  onChange,
}: {
  values: FormData
  onChange: (vals: FormData) => void
}) {
  const hasValues = !!(values.sid || values.token || values.objects_list || values.apex_list || values.proxy || values.insecure)
  const [open, setOpen] = useState(hasValues)

  const toggle = (key: keyof FormData) => {
    onChange({ ...values, [key]: !values[key] })
  }

  const setField = (key: keyof FormData, val: unknown) => {
    onChange({ ...values, [key]: val })
  }

  const parseLines = (text: string): string[] | null => {
    const lines = text.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'))
    return lines.length > 0 ? lines : null
  }

  const linesToText = (lines: string[] | null | undefined): string => {
    return lines?.join('\n') || ''
  }

  return (
    <div className="mb-6">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm font-medium cursor-pointer"
        style={{ color: 'var(--cyan)' }}
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        Advanced Options
      </button>

      {open && (
        <div
          className="mt-3 p-4 rounded-lg space-y-4"
          style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}
        >
          {/* Authentication */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium" style={{ color: 'var(--cyan)' }}>
              Authentication
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Session ID (sid)
                <input
                  type="text"
                  value={values.sid || ''}
                  onChange={(e) => setField('sid', e.target.value || null)}
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                  placeholder="Optional"
                />
              </label>
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Aura token
                <input
                  type="text"
                  value={values.token || ''}
                  onChange={(e) => setField('token', e.target.value || null)}
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                  placeholder="Optional"
                />
              </label>
            </div>
          </div>

          {/* Recon Input — custom objects and apex methods */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium" style={{ color: 'var(--cyan)' }}>
              Custom Object &amp; Apex Lists
            </h4>
            <p className="text-xs" style={{ color: 'var(--muted)' }}>
              Paste output from <code>aura-privesc recon</code> or add your own. One per line, # comments ignored.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Object API names
                <textarea
                  value={linesToText(values.objects_list)}
                  onChange={(e) => setField('objects_list', parseLines(e.target.value))}
                  rows={4}
                  className="w-full mt-1 px-2 py-1.5 rounded text-xs font-mono"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)', resize: 'vertical' }}
                  placeholder={"Account\nContact\nCustomObject__c"}
                />
              </label>
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Apex controller.method pairs
                <textarea
                  value={linesToText(values.apex_list)}
                  onChange={(e) => setField('apex_list', parseLines(e.target.value))}
                  rows={4}
                  className="w-full mt-1 px-2 py-1.5 rounded text-xs font-mono"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)', resize: 'vertical' }}
                  placeholder={"MyController.getRecords\nAdminCtrl.doAction"}
                />
              </label>
            </div>
          </div>

          {/* Skip flags */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium" style={{ color: 'var(--cyan)' }}>
              Skip Phases
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {[
                { key: 'skip_crud' as const, label: 'CRUD checks' },
                { key: 'skip_records' as const, label: 'Record enumeration' },
                { key: 'skip_apex' as const, label: 'Apex testing' },
                { key: 'skip_validation' as const, label: 'Validation' },
                { key: 'skip_crud_test' as const, label: 'CRUD write test' },
                { key: 'skip_graphql' as const, label: 'GraphQL enumeration' },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!values[key]}
                    onChange={() => toggle(key)}
                    className="accent-[var(--cyan)]"
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>

          {/* Performance */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium" style={{ color: 'var(--cyan)' }}>
              Performance
            </h4>
            <div className="grid grid-cols-3 gap-3">
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Timeout (s)
                <input
                  type="number"
                  value={values.timeout || 30}
                  onChange={(e) => setField('timeout', parseInt(e.target.value) || 30)}
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                />
              </label>
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Delay (ms)
                <input
                  type="number"
                  value={values.delay || 0}
                  onChange={(e) => setField('delay', parseInt(e.target.value) || 0)}
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                />
              </label>
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Concurrency
                <input
                  type="number"
                  value={values.concurrency || 5}
                  onChange={(e) => setField('concurrency', parseInt(e.target.value) || 5)}
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                />
              </label>
            </div>
          </div>

          {/* Network */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium" style={{ color: 'var(--cyan)' }}>
              Network
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Proxy URL
                <input
                  type="text"
                  value={values.proxy || ''}
                  onChange={(e) => setField('proxy', e.target.value || null)}
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                  placeholder="http://127.0.0.1:8080"
                />
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer self-end pb-1">
                <input
                  type="checkbox"
                  checked={!!values.insecure}
                  onChange={() => toggle('insecure')}
                  className="accent-[var(--cyan)]"
                />
                Disable TLS verification
              </label>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
