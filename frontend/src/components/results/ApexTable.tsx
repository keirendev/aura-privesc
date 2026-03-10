import { useState, useMemo } from 'react'
import type { ApexResult, ScanResult } from '../../api/types'
import Badge from '../shared/Badge'
import SearchInput from '../shared/SearchInput'
import { buildFireAuraCurl } from '../../lib/curl'

export default function ApexTable({
  results,
  scanResult,
}: {
  results: ApexResult[]
  scanResult: ScanResult
}) {
  const [search, setSearch] = useState('')

  const callable = useMemo(() => {
    let items = results.filter((r) => r.status === 'callable')
    if (search) {
      const q = search.toLowerCase()
      items = items.filter((r) => r.controller_method.toLowerCase().includes(q))
    }
    return items.sort((a, b) => a.controller_method.localeCompare(b.controller_method))
  }, [results, search])

  if (!callable.length) return null

  return (
    <div className="mb-6">
      <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--cyan)' }}>
        Callable Apex Methods ({callable.length})
      </h3>
      <SearchInput value={search} onChange={setSearch} placeholder="Filter methods..." />
      <div
        className="rounded-lg overflow-hidden"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: 'var(--border)' }}>
              <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Controller.Method</th>
              <th className="text-center px-3 py-2" style={{ color: 'var(--cyan)' }}>Status</th>
              <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Message</th>
              <th className="text-center px-3 py-2" style={{ color: 'var(--cyan)' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {callable.map((r) => {
              const [controller, method] = r.controller_method.split('.', 2)
              const curl = buildFireAuraCurl(
                scanResult,
                'aura://ApexActionController/ACTION$execute',
                {
                  namespace: '',
                  classname: controller || '',
                  method: method || '',
                  params: {},
                  cacheable: false,
                  isContinuation: false,
                },
              )

              return (
                <tr key={r.controller_method} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="px-3 py-2 font-medium">{r.controller_method}</td>
                  <td className="text-center px-3 py-2">
                    <Badge value={r.status} type="status" />
                  </td>
                  <td className="px-3 py-2" style={{ color: 'var(--muted)' }}>
                    {r.message || ''}
                  </td>
                  <td className="text-center px-3 py-2">
                    <button
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(curl)
                        } catch {
                          prompt('Copy curl:', curl)
                        }
                      }}
                      className="px-3 py-1 rounded text-xs font-semibold cursor-pointer"
                      style={{ background: 'var(--purple)', color: '#fff' }}
                    >
                      Fire
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
