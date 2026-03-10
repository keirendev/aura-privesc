import { useParams, Link } from 'react-router-dom'
import { useState, useEffect, useMemo } from 'react'
import { getObjectRecords, getObjectFields, graphqlRecords } from '../api/client'
import CopyButton from '../components/shared/CopyButton'
import { Loader2, ArrowLeft } from 'lucide-react'

export default function RecordsPage() {
  const { id: scanId, source, objectName } = useParams<{
    id: string
    source: string
    objectName: string
  }>()

  const [records, setRecords] = useState<Record<string, unknown>[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!scanId || !objectName || !source) return

    const fetchRecords = async () => {
      setLoading(true)
      setError(null)
      try {
        if (source === 'aura') {
          const data = await getObjectRecords(scanId, objectName)
          setRecords(data.records)
        } else {
          // GraphQL — need fields first
          const fieldsData = await getObjectFields(scanId, objectName)
          const fieldNames = fieldsData.fields.map((f) => f.name)
          if (!fieldNames.length) {
            setError('No fields available to query')
            setRecords([])
            return
          }
          const data = await graphqlRecords({
            scan_id: scanId,
            object_name: objectName,
            fields: fieldNames,
            first: 100,
          })
          setRecords((data.records as Record<string, unknown>[]) || [])
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setLoading(false)
      }
    }

    fetchRecords()
  }, [scanId, objectName, source])

  return (
    <div className="p-4">
      <div className="flex items-center gap-3 mb-4">
        <Link
          to={`/scan/${scanId}`}
          className="inline-flex items-center gap-1 text-sm"
          style={{ color: 'var(--cyan)' }}
        >
          <ArrowLeft size={14} />
          Back to scan
        </Link>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cyan)' }}>
          {objectName}
          <span className="ml-2 text-sm font-normal" style={{ color: 'var(--muted)' }}>
            via {source === 'aura' ? 'getItems' : 'GraphQL'}
          </span>
        </h2>
      </div>

      {loading && (
        <div className="flex items-center gap-2" style={{ color: 'var(--muted)' }}>
          <Loader2 size={16} className="animate-spin" />
          Fetching records...
        </div>
      )}

      {error && (
        <div className="p-3 rounded text-sm" style={{ background: 'var(--card)', color: 'var(--red, #ef4444)' }}>
          {error}
        </div>
      )}

      {records && records.length === 0 && !loading && (
        <p style={{ color: 'var(--muted)' }}>No records returned.</p>
      )}

      {records && records.length > 0 && (
        <FullRecordsTable records={records} />
      )}
    </div>
  )
}

function FullRecordsTable({ records }: { records: Record<string, unknown>[] }) {
  const allFields = useMemo(() => {
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
    // Priority fields first
    const priority = ['Id', 'Name', 'Email', 'Username', 'CreatedDate']
    return [
      ...priority.filter((f) => result.includes(f)),
      ...result.filter((f) => !priority.includes(f)),
    ]
  }, [records])

  const [selectedRecord, setSelectedRecord] = useState<Record<string, unknown> | null>(null)

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <span className="text-sm" style={{ color: 'var(--muted)' }}>
          {records.length} records, {allFields.length} fields
        </span>
      </div>

      {/* Horizontal scrollable table */}
      <div
        className="overflow-x-auto rounded-lg mb-4"
        style={{ border: '1px solid var(--border)', background: 'var(--card)' }}
      >
        <table className="text-xs" style={{ minWidth: 'max-content' }}>
          <thead>
            <tr style={{ background: 'var(--border)' }}>
              <th className="px-2 py-1.5 text-left sticky left-0" style={{ background: 'var(--border)', color: 'var(--cyan)' }}>
                #
              </th>
              {allFields.map((f) => (
                <th key={f} className="text-left px-2 py-1.5 whitespace-nowrap" style={{ color: 'var(--cyan)' }}>
                  {f}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((rec, i) => (
              <tr
                key={i}
                className="cursor-pointer hover:opacity-80"
                style={{
                  borderBottom: '1px solid var(--border)',
                  background: selectedRecord === rec ? 'var(--border)' : undefined,
                }}
                onClick={() => setSelectedRecord(selectedRecord === rec ? null : rec)}
              >
                <td
                  className="px-2 py-1 sticky left-0"
                  style={{ background: selectedRecord === rec ? 'var(--border)' : 'var(--card)', color: 'var(--muted)' }}
                >
                  {i + 1}
                </td>
                {allFields.map((f) => (
                  <td
                    key={f}
                    className="px-2 py-1 whitespace-nowrap max-w-[400px] truncate"
                    title={String(rec[f] ?? '')}
                  >
                    {String(rec[f] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Selected record detail */}
      {selectedRecord && (
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--cyan)' }}>
              Record Detail
            </h3>
            <CopyButton text={JSON.stringify(selectedRecord, null, 2)} />
          </div>
          <div className="grid gap-1 text-xs" style={{ gridTemplateColumns: 'minmax(120px, auto) 1fr' }}>
            {allFields.map((f) => {
              const val = selectedRecord[f]
              if (val === null || val === undefined) return null
              return (
                <div key={f} className="contents">
                  <div className="px-2 py-1 font-medium" style={{ color: 'var(--muted)' }}>{f}</div>
                  <div className="px-2 py-1" style={{ wordBreak: 'break-all' }}>
                    {String(val)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
