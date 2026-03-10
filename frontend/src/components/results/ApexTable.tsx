import { useState, useMemo } from 'react'
import type { ApexResult, ScanResult } from '../../api/types'
import CopyButton from '../shared/CopyButton'
import SearchInput from '../shared/SearchInput'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { buildFireAuraCurl, type CurlOptions } from '../../lib/curl'

export default function ApexTable({
  results,
  scanResult,
  curlOptions,
}: {
  results: ApexResult[]
  scanResult: ScanResult
  curlOptions?: CurlOptions
}) {
  const [search, setSearch] = useState('')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  const callable = useMemo(() => {
    let items = results.filter((r) => r.status === 'callable')
    if (search) {
      const q = search.toLowerCase()
      items = items.filter((r) => r.controller_method.toLowerCase().includes(q))
    }
    return items.sort((a, b) => a.controller_method.localeCompare(b.controller_method))
  }, [results, search])

  const toggleExpand = (name: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

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
              <th className="w-8 px-3 py-2"></th>
              <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Controller.Method</th>
              <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Message</th>
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
                curlOptions,
              )
              const expanded = expandedRows.has(r.controller_method)

              return (
                <ApexExpandableRow
                  key={r.controller_method}
                  result={r}
                  curl={curl}
                  expanded={expanded}
                  onToggle={() => toggleExpand(r.controller_method)}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ApexExpandableRow({
  result,
  curl,
  expanded,
  onToggle,
}: {
  result: ApexResult
  curl: string
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr
        className="cursor-pointer hover:opacity-80"
        onClick={onToggle}
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <td className="px-3 py-2">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </td>
        <td className="px-3 py-2 font-medium">{result.controller_method}</td>
        <td className="px-3 py-2" style={{ color: 'var(--muted)' }}>
          {result.message || ''}
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: 'var(--bg)' }}>
          <td colSpan={3} className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs" style={{ color: 'var(--muted)' }}>
                execute curl
              </span>
              <CopyButton text={curl} />
            </div>
            <pre
              className="text-xs p-2 rounded"
              style={{
                background: 'var(--card)',
                color: 'var(--green)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {curl}
            </pre>
          </td>
        </tr>
      )}
    </>
  )
}
