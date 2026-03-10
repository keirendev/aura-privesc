import { useRef, useState } from 'react'
import { ChevronDown, ChevronRight, Upload, X } from 'lucide-react'
import type { ScanCreateRequest } from '../../api/types'
import { useRecons } from '../../hooks/useRecons'

type FormData = Omit<ScanCreateRequest, 'url'>

export default function AdvancedOptions({
  values,
  onChange,
}: {
  values: FormData
  onChange: (vals: FormData) => void
}) {
  const reconsQuery = useRecons()
  const completedRecons = (reconsQuery.data ?? []).filter((r) => r.status === 'completed')
  const hasValues = !!(values.sid || values.token || values.objects_list || values.apex_list || values.proxy || values.insecure || values.crm_domain || values.recon_id)
  const [open, setOpen] = useState(hasValues)
  const [objectsFileName, setObjectsFileName] = useState<string | null>(null)
  const [apexFileName, setApexFileName] = useState<string | null>(null)
  const objectsInputRef = useRef<HTMLInputElement>(null)
  const apexInputRef = useRef<HTMLInputElement>(null)

  const toggle = (key: keyof FormData) => {
    onChange({ ...values, [key]: !values[key] })
  }

  const setField = (key: keyof FormData, val: unknown) => {
    onChange({ ...values, [key]: val })
  }

  const handleFileUpload = (
    key: 'objects_list' | 'apex_list',
    setFileName: (name: string | null) => void,
  ) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = () => {
      const text = reader.result as string
      const lines = text.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'))
      setField(key, lines.length > 0 ? lines : null)
    }
    reader.readAsText(file)
  }

  const clearFile = (
    key: 'objects_list' | 'apex_list',
    setFileName: (name: string | null) => void,
    inputRef: React.RefObject<HTMLInputElement | null>,
  ) => {
    setField(key, null)
    setFileName(null)
    if (inputRef.current) inputRef.current.value = ''
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

          {/* Recon Input — custom objects and apex files */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium" style={{ color: 'var(--cyan)' }}>
              Recon Files
            </h4>
            {completedRecons.length > 0 && (
              <div>
                <label className="text-xs" style={{ color: 'var(--muted)' }}>
                  Use recon run
                  <select
                    value={values.recon_id || ''}
                    onChange={(e) => {
                      const rid = e.target.value || null
                      if (rid) {
                        // Set recon_id and clear file uploads in one update
                        onChange({ ...values, recon_id: rid, objects_list: null, apex_list: null })
                        setObjectsFileName(null)
                        setApexFileName(null)
                        if (objectsInputRef.current) objectsInputRef.current.value = ''
                        if (apexInputRef.current) apexInputRef.current.value = ''
                      } else {
                        setField('recon_id', null)
                      }
                    }}
                    className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                    style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                  >
                    <option value="">None — use file upload</option>
                    {completedRecons.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.instance_url} — {r.username || 'unknown'} ({r.object_count ?? 0} objects, {r.apex_count ?? 0} apex)
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            <p className="text-xs" style={{ color: 'var(--muted)' }}>
              {values.recon_id
                ? 'Recon data will be used. File uploads are disabled.'
                : 'Upload files from \'aura-privesc recon\' — one entry per line, # comments ignored.'}
            </p>
            <div className="grid grid-cols-2 gap-3" style={{ opacity: values.recon_id ? 0.4 : 1, pointerEvents: values.recon_id ? 'none' : 'auto' }}>
              <div className="text-xs" style={{ color: 'var(--muted)' }}>
                Objects file
                <div className="flex items-center gap-2 mt-1">
                  <input
                    ref={objectsInputRef}
                    type="file"
                    accept=".txt,.csv,.list"
                    onChange={handleFileUpload('objects_list', setObjectsFileName)}
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => objectsInputRef.current?.click()}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs cursor-pointer"
                    style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                  >
                    <Upload size={12} />
                    {objectsFileName || (values.objects_list ? `${values.objects_list.length} objects loaded` : 'Choose file')}
                  </button>
                  {(objectsFileName || values.objects_list) && (
                    <button
                      type="button"
                      onClick={() => clearFile('objects_list', setObjectsFileName, objectsInputRef)}
                      className="cursor-pointer"
                      style={{ color: 'var(--muted)' }}
                      title="Clear"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>
              <div className="text-xs" style={{ color: 'var(--muted)' }}>
                Apex methods file
                <div className="flex items-center gap-2 mt-1">
                  <input
                    ref={apexInputRef}
                    type="file"
                    accept=".txt,.csv,.list"
                    onChange={handleFileUpload('apex_list', setApexFileName)}
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => apexInputRef.current?.click()}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs cursor-pointer"
                    style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                  >
                    <Upload size={12} />
                    {apexFileName || (values.apex_list ? `${values.apex_list.length} methods loaded` : 'Choose file')}
                  </button>
                  {(apexFileName || values.apex_list) && (
                    <button
                      type="button"
                      onClick={() => clearFile('apex_list', setApexFileName, apexInputRef)}
                      className="cursor-pointer"
                      style={{ color: 'var(--muted)' }}
                      title="Clear"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>
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
                  value={values.timeout ?? ''}
                  onChange={(e) => setField('timeout', e.target.value === '' ? undefined : parseInt(e.target.value))}
                  onBlur={() => { if (values.timeout == null) setField('timeout', 30) }}
                  placeholder="30"
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                />
              </label>
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Delay (ms)
                <input
                  type="number"
                  value={values.delay ?? ''}
                  onChange={(e) => setField('delay', e.target.value === '' ? undefined : parseInt(e.target.value))}
                  onBlur={() => { if (values.delay == null) setField('delay', 0) }}
                  placeholder="0"
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                />
              </label>
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                Concurrency
                <input
                  type="number"
                  value={values.concurrency ?? ''}
                  onChange={(e) => setField('concurrency', e.target.value === '' ? undefined : parseInt(e.target.value))}
                  onBlur={() => { if (values.concurrency == null) setField('concurrency', 5) }}
                  placeholder="5"
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
              <label className="text-xs" style={{ color: 'var(--muted)' }}>
                CRM Domain
                <input
                  type="text"
                  value={values.crm_domain || ''}
                  onChange={(e) => setField('crm_domain', e.target.value || null)}
                  className="w-full mt-1 px-2 py-1.5 rounded text-sm"
                  style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--text)' }}
                  placeholder="acme.my.salesforce.com"
                />
              </label>
            </div>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
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
      )}
    </div>
  )
}
