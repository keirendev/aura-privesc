import { useState, useMemo } from 'react'
import type { ObjectResult, ScanResult } from '../../api/types'
import { CrudCell, ReadableIcon } from '../shared/CrudIndicator'
import SearchInput from '../shared/SearchInput'
import CopyButton from '../shared/CopyButton'
import { ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { buildFireAuraCurl } from '../../lib/curl'

const DESCRIPTORS = {
  getObjectInfo: 'aura://RecordUiController/ACTION$getObjectInfo',
  getItems:
    'serviceComponent://ui.force.components.controllers.lists.selectableListDataProvider.SelectableListDataProviderController/ACTION$getItems',
  createRecord:
    'serviceComponent://ui.force.components.controllers.recordGlobalValueProvider.RecordGvpController/ACTION$createRecord',
  updateRecord:
    'serviceComponent://ui.force.components.controllers.recordGlobalValueProvider.RecordGvpController/ACTION$updateRecord',
  deleteRecord:
    'serviceComponent://ui.force.components.controllers.recordGlobalValueProvider.RecordGvpController/ACTION$deleteRecord',
} as const

type CurlTab = 'info' | 'items' | 'create' | 'update' | 'delete'

export default function ObjectsTable({
  objects,
  scanResult,
  scanId,
}: {
  objects: ObjectResult[]
  scanResult: ScanResult
  scanId: string
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
        <table className="w-full text-sm" style={{ tableLayout: 'fixed' }}>
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
              <th className="text-center px-2 py-2" style={{ color: 'var(--cyan)', width: '40px' }}>R</th>
              <th className="text-center px-2 py-2" style={{ color: 'var(--cyan)', width: '40px' }}>C</th>
              <th className="text-center px-2 py-2" style={{ color: 'var(--cyan)', width: '40px' }}>U</th>
              <th className="text-center px-2 py-2" style={{ color: 'var(--cyan)', width: '40px' }}>D</th>
              <th
                className="text-right px-3 py-2 cursor-pointer select-none"
                style={{ color: 'var(--cyan)', width: '100px' }}
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
                  scanId={scanId}
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
  scanId,
}: {
  obj: ObjectResult
  expanded: boolean
  onToggle: () => void
  scanResult: ScanResult
  scanId: string
}) {
  const [activeCurl, setActiveCurl] = useState<CurlTab>('info')
  const count = obj.record_count != null ? obj.record_count.toString() : '-'

  const curls: Record<CurlTab, string> = {
    info: obj.proof || buildFireAuraCurl(scanResult, DESCRIPTORS.getObjectInfo, {
      objectApiName: obj.name,
    }),
    items: obj.proof_records || buildFireAuraCurl(scanResult, DESCRIPTORS.getItems, {
      entityNameOrId: obj.name,
      layoutType: 'FULL',
      pageSize: 100,
      currentPage: 0,
      useTimeout: false,
      getCount: false,
      enableRowActions: false,
    }),
    create: buildFireAuraCurl(scanResult, DESCRIPTORS.createRecord, {
      record: {
        apiName: obj.name,
        fields: { Name: 'TestRecord' },
      },
    }),
    update: buildFireAuraCurl(scanResult, DESCRIPTORS.updateRecord, {
      record: {
        apiName: obj.name,
        id: '<RECORD_ID>',
        fields: { Name: 'UpdatedValue' },
      },
    }),
    delete: buildFireAuraCurl(scanResult, DESCRIPTORS.deleteRecord, {
      recordId: '<RECORD_ID>',
    }),
  }

  const handleActionClick = async (tab: CurlTab, e: React.MouseEvent) => {
    e.stopPropagation()
    setActiveCurl(tab)
    try {
      await navigator.clipboard.writeText(curls[tab])
    } catch {
      prompt('Copy curl:', curls[tab])
    }
  }

  const recordsUrl = `/scan/${scanId}/records/aura/${obj.name}`

  const buttons: { tab: CurlTab; label: string; color: string; show: boolean }[] = [
    { tab: 'info', label: 'getObjectInfo', color: 'var(--cyan)', show: true },
    { tab: 'items', label: 'getItems', color: '#1565c0', show: true },
    { tab: 'create', label: 'createRecord', color: '#2e7d32', show: obj.crud.createable },
    { tab: 'update', label: 'updateRecord', color: '#e65100', show: obj.crud.updateable },
    { tab: 'delete', label: 'deleteRecord', color: '#b71c1c', show: obj.crud.deletable },
  ]

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
              {buttons.filter((b) => b.show).map((b) => (
                <button
                  key={b.tab}
                  onClick={(e) => handleActionClick(b.tab, e)}
                  className="px-3 py-1 rounded text-xs font-semibold cursor-pointer"
                  style={{
                    background: activeCurl === b.tab ? b.color : 'var(--border)',
                    color: activeCurl === b.tab ? '#fff' : 'var(--text)',
                  }}
                >
                  {b.label}
                </button>
              ))}
              <span className="mx-1" style={{ borderLeft: '1px solid var(--border)' }} />
              <a
                href={recordsUrl}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="px-3 py-1 rounded text-xs font-semibold cursor-pointer inline-flex items-center gap-1 no-underline"
                style={{ background: 'var(--border)', color: 'var(--text)' }}
              >
                View Records <ExternalLink size={11} />
              </a>
            </div>

            {/* Active curl display */}
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs" style={{ color: 'var(--muted)' }}>
                  {buttons.find((b) => b.tab === activeCurl)?.label} curl
                </span>
                <CopyButton text={curls[activeCurl]} />
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
                {curls[activeCurl]}
              </pre>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
