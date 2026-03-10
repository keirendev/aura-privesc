import { useState, useMemo } from 'react'
import type { ObjectResult, ScanResult } from '../../api/types'
import { CrudCell, ReadableIcon } from '../shared/CrudIndicator'
import SearchInput from '../shared/SearchInput'
import CopyButton from '../shared/CopyButton'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { buildFireAuraCurl } from '../../lib/curl'

export default function ObjectsTable({
  objects,
  scanResult,
}: {
  objects: ObjectResult[]
  scanResult: ScanResult
}) {
  const [search, setSearch] = useState('')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [sortKey, setSortKey] = useState<'name' | 'record_count'>('name')
  const [sortAsc, setSortAsc] = useState(true)

  const filtered = useMemo(() => {
    let items = objects.filter((o) => o.accessible)
    if (search) {
      const q = search.toLowerCase()
      items = items.filter((o) => o.name.toLowerCase().includes(q))
    }
    items.sort((a, b) => {
      if (sortKey === 'name') {
        return sortAsc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)
      }
      const ca = a.record_count ?? -1
      const cb = b.record_count ?? -1
      return sortAsc ? ca - cb : cb - ca
    })
    return items
  }, [objects, search, sortKey, sortAsc])

  const toggleSort = (key: 'name' | 'record_count') => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  const toggleExpand = (name: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  if (!filtered.length) {
    return (
      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--cyan)' }}>
          Object Findings
        </h3>
        <p style={{ color: 'var(--muted)' }}>No accessible objects found.</p>
      </div>
    )
  }

  return (
    <div className="mb-6">
      <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--cyan)' }}>
        Object Findings ({filtered.length})
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
              <th
                className="text-left px-3 py-2 cursor-pointer select-none"
                style={{ color: 'var(--cyan)' }}
                onClick={() => toggleSort('name')}
              >
                Object {sortKey === 'name' ? (sortAsc ? '\u25B2' : '\u25BC') : ''}
              </th>
              <th className="text-center px-2 py-2" style={{ color: 'var(--cyan)' }}>R</th>
              <th className="text-center px-2 py-2" style={{ color: 'var(--cyan)' }}>C</th>
              <th className="text-center px-2 py-2" style={{ color: 'var(--cyan)' }}>U</th>
              <th className="text-center px-2 py-2" style={{ color: 'var(--cyan)' }}>D</th>
              <th
                className="text-right px-3 py-2 cursor-pointer select-none"
                style={{ color: 'var(--cyan)' }}
                onClick={() => toggleSort('record_count')}
              >
                Records {sortKey === 'record_count' ? (sortAsc ? '\u25B2' : '\u25BC') : ''}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((obj) => {
              const expanded = expandedRows.has(obj.name)
              return (
                <ExpandableObjectRow
                  key={obj.name}
                  obj={obj}
                  expanded={expanded}
                  onToggle={() => toggleExpand(obj.name)}
                  scanResult={scanResult}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ExpandableObjectRow({
  obj,
  expanded,
  onToggle,
  scanResult,
}: {
  obj: ObjectResult
  expanded: boolean
  onToggle: () => void
  scanResult: ScanResult
}) {
  const count = obj.record_count != null ? obj.record_count.toString() : '-'

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
        <td className="px-3 py-2 font-medium">{obj.name}</td>
        <td className="text-center px-2 py-2"><ReadableIcon readable={obj.crud.readable} /></td>
        <td className="text-center px-2 py-2"><CrudCell crud_validation={obj.crud_validation} op="create" /></td>
        <td className="text-center px-2 py-2"><CrudCell crud_validation={obj.crud_validation} op="update" /></td>
        <td className="text-center px-2 py-2"><CrudCell crud_validation={obj.crud_validation} op="delete" /></td>
        <td className="text-right px-3 py-2">{count}</td>
      </tr>
      {expanded && (
        <tr style={{ background: 'var(--bg)' }}>
          <td colSpan={7} className="p-4">
            {/* Action buttons */}
            <div className="flex gap-2 mb-3 flex-wrap">
              <ActionButton
                label="getObjectInfo"
                color="var(--cyan)"
                curl={buildFireAuraCurl(scanResult, 'aura://RecordUiController/ACTION$getObjectInfo', {
                  objectApiName: obj.name,
                })}
              />
              <ActionButton
                label="getItems"
                color="#1565c0"
                curl={buildFireAuraCurl(
                  scanResult,
                  'serviceComponent://ui.force.components.controllers.lists.selectableListDataProvider.SelectableListDataProviderController/ACTION$getItems',
                  {
                    entityNameOrId: obj.name,
                    layoutType: 'FULL',
                    pageSize: 100,
                    currentPage: 0,
                    useTimeout: false,
                    getCount: false,
                    enableRowActions: false,
                  },
                )}
              />
            </div>

            {/* Sample records */}
            {obj.sample_records && obj.sample_records.length > 0 && (
              <div>
                <h4 className="text-xs font-medium mb-2" style={{ color: 'var(--muted)' }}>
                  Sample Records
                </h4>
                <div className="overflow-x-auto">
                  <SampleRecordsTable records={obj.sample_records} />
                </div>
              </div>
            )}

            {/* Proof curl */}
            {obj.proof && (
              <div className="mt-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs" style={{ color: 'var(--muted)' }}>
                    Proof curl
                  </span>
                  <CopyButton text={obj.proof} />
                </div>
                <pre
                  className="text-xs p-2 rounded overflow-x-auto"
                  style={{ background: 'var(--card)', color: 'var(--green)' }}
                >
                  {obj.proof}
                </pre>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

function ActionButton({ label, color, curl }: { label: string; color: string; curl: string }) {
  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(curl)
    } catch {
      prompt('Copy curl:', curl)
    }
  }

  return (
    <button
      onClick={handleClick}
      className="px-3 py-1 rounded text-xs font-semibold cursor-pointer"
      style={{ background: color, color: '#fff' }}
    >
      {label}
    </button>
  )
}

function SampleRecordsTable({ records }: { records: Record<string, unknown>[] }) {
  const fields = useMemo(() => {
    const seen = new Set<string>()
    const result: string[] = []
    for (const rec of records) {
      for (const key of Object.keys(rec)) {
        if (!seen.has(key)) {
          seen.add(key)
          result.push(key)
        }
      }
    }
    return result
  }, [records])

  return (
    <table className="w-full text-xs">
      <thead>
        <tr style={{ background: 'var(--border)' }}>
          {fields.map((f) => (
            <th key={f} className="text-left px-2 py-1" style={{ color: 'var(--cyan)' }}>
              {f}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {records.slice(0, 10).map((rec, i) => (
          <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
            {fields.map((f) => (
              <td
                key={f}
                className="px-2 py-1 max-w-[200px] truncate"
                title={String(rec[f] ?? '')}
              >
                {String(rec[f] ?? '')}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
