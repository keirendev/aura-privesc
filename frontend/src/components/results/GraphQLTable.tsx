import { useState, useMemo } from 'react'
import type { GraphQLResult, ScanResult } from '../../api/types'
import SearchInput from '../shared/SearchInput'
import CopyButton from '../shared/CopyButton'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { buildFireAuraCurl } from '../../lib/curl'

export default function GraphQLTable({
  results,
  scanResult,
}: {
  results: GraphQLResult[]
  scanResult: ScanResult
}) {
  const [search, setSearch] = useState('')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  const filtered = useMemo(() => {
    let items = [...results]
    if (search) {
      const q = search.toLowerCase()
      items = items.filter((r) => r.object_name.toLowerCase().includes(q))
    }
    return items.sort((a, b) => a.object_name.localeCompare(b.object_name))
  }, [results, search])

  if (!results.length) return null

  const toggleExpand = (name: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  return (
    <div className="mb-6">
      <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--cyan)' }}>
        GraphQL Enumeration ({results.length} objects)
      </h3>
      <SearchInput value={search} onChange={setSearch} placeholder="Filter objects..." />
      <div
        className="rounded-lg overflow-hidden"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: 'var(--border)' }}>
              <th className="w-8 px-3 py-2"></th>
              <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Object</th>
              <th className="text-right px-3 py-2" style={{ color: 'var(--cyan)' }}>Record Count</th>
              <th className="text-right px-3 py-2" style={{ color: 'var(--cyan)' }}>Fields</th>
              <th className="text-center px-3 py-2" style={{ color: 'var(--cyan)' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => {
              const expanded = expandedRows.has(r.object_name)
              const countQuery = `query getCount{uiapi{query{${r.object_name}{totalCount}}}}`
              const curl = buildFireAuraCurl(
                scanResult,
                'aura://RecordUiController/ACTION$executeGraphQL',
                {
                  queryInput: {
                    operationName: 'getCount',
                    query: countQuery,
                    variables: {},
                  },
                },
              )

              return (
                <GraphQLRow
                  key={r.object_name}
                  result={r}
                  expanded={expanded}
                  onToggle={() => toggleExpand(r.object_name)}
                  curl={curl}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function GraphQLRow({
  result,
  expanded,
  onToggle,
  curl,
}: {
  result: GraphQLResult
  expanded: boolean
  onToggle: () => void
  curl: string
}) {
  const count = result.total_count != null ? result.total_count.toString() : '-'
  const nFields = result.fields.length || '-'

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
        <td className="px-3 py-2 font-medium">{result.object_name}</td>
        <td className="text-right px-3 py-2">{count}</td>
        <td className="text-right px-3 py-2">{nFields}</td>
        <td className="text-center px-3 py-2">
          <button
            onClick={async (e) => {
              e.stopPropagation()
              try {
                await navigator.clipboard.writeText(curl)
              } catch {
                prompt('Copy curl:', curl)
              }
            }}
            className="px-3 py-1 rounded text-xs font-semibold cursor-pointer"
            style={{ background: 'var(--purple)', color: '#fff' }}
          >
            Count
          </button>
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: 'var(--bg)' }}>
          <td colSpan={5} className="p-4">
            {/* Fields table */}
            {result.fields.length > 0 ? (
              <table className="w-full text-xs mb-3">
                <thead>
                  <tr style={{ background: 'var(--border)' }}>
                    <th className="text-left px-2 py-1" style={{ color: 'var(--cyan)' }}>Field</th>
                    <th className="text-left px-2 py-1" style={{ color: 'var(--cyan)' }}>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {[...result.fields]
                    .sort((a, b) => a.name.localeCompare(b.name))
                    .map((f) => (
                      <tr key={f.name} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="px-2 py-1">{f.name}</td>
                        <td className="px-2 py-1" style={{ color: 'var(--muted)' }}>{f.data_type}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            ) : (
              <p className="text-xs mb-3" style={{ color: 'var(--muted)' }}>
                No field data available.
              </p>
            )}

            {/* Proof curls */}
            {result.proof_count && (
              <div className="mb-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs" style={{ color: 'var(--muted)' }}>Count query curl</span>
                  <CopyButton text={result.proof_count} />
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
                  {result.proof_count}
                </pre>
              </div>
            )}
            {result.proof_fields && (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs" style={{ color: 'var(--muted)' }}>Fields query curl</span>
                  <CopyButton text={result.proof_fields} />
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
                  {result.proof_fields}
                </pre>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}
