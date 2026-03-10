import { useState, useMemo } from 'react'
import type { GraphQLResult, GraphQLFieldInfo, GraphQLWriteTestResult } from '../../api/types'
import { getObjectFields, introspectSchema, introspectTypeFields, graphqlWriteTest } from '../../api/client'
import SearchInput from '../shared/SearchInput'
import CopyButton from '../shared/CopyButton'
import { ChevronDown, ChevronRight, Loader2, ExternalLink, Search, FlaskConical } from 'lucide-react'

export default function GraphQLTable({
  results,
  scanId,
}: {
  results: GraphQLResult[]
  scanId: string
}) {
  const [search, setSearch] = useState('')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [discoveredObjects, setDiscoveredObjects] = useState<string[]>([])
  const [discoverLoading, setDiscoverLoading] = useState(false)
  const [discoverError, setDiscoverError] = useState<string | null>(null)
  const [discoverProof, setDiscoverProof] = useState<string | null>(null)

  // Merge scan results with discovered objects (discovered ones not already in results)
  const mergedResults = useMemo(() => {
    const existingNames = new Set(results.map((r) => r.object_name))
    const extraResults: GraphQLResult[] = discoveredObjects
      .filter((name) => !existingNames.has(name))
      .map((name) => ({
        object_name: name,
        total_count: null,
        fields: [],
        error: null,
        proof_count: null,
        proof_fields: null,
      }))
    return [...results, ...extraResults]
  }, [results, discoveredObjects])

  const filtered = useMemo(() => {
    let items = [...mergedResults]
    if (search) {
      const q = search.toLowerCase()
      items = items.filter((r) => r.object_name.toLowerCase().includes(q))
    }
    return items.sort((a, b) => a.object_name.localeCompare(b.object_name))
  }, [mergedResults, search])

  if (!results.length && !discoveredObjects.length) return null

  const toggleExpand = (name: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const handleDiscover = async () => {
    if (discoverLoading) return
    setDiscoverLoading(true)
    setDiscoverError(null)
    try {
      const data = await introspectSchema(scanId)
      setDiscoveredObjects(data.objects)
      setDiscoverProof(data.proof)
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : String(err))
    } finally {
      setDiscoverLoading(false)
    }
  }

  return (
    <div className="mb-6">
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-lg font-semibold" style={{ color: 'var(--cyan)' }}>
          GraphQL Enumeration ({mergedResults.length} objects)
        </h3>
        <button
          onClick={handleDiscover}
          disabled={discoverLoading}
          className="px-3 py-1 rounded text-xs font-semibold cursor-pointer inline-flex items-center gap-1"
          style={{
            background: 'var(--cyan)',
            color: 'var(--bg)',
            opacity: discoverLoading ? 0.6 : 1,
          }}
        >
          {discoverLoading ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
          Discover Objects
        </button>
      </div>

      {discoverError && (
        <div className="mb-3 p-2 rounded text-xs" style={{ background: 'var(--card)', color: 'var(--red, #ef4444)' }}>
          Introspection: {discoverError}
        </div>
      )}

      {discoverProof && discoveredObjects.length > 0 && (
        <div className="mb-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs" style={{ color: 'var(--muted)' }}>
              Discovered {discoveredObjects.length} objects via __schema introspection
            </span>
            <CopyButton text={discoverProof} />
          </div>
        </div>
      )}

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
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => {
              const expanded = expandedRows.has(r.object_name)
              return (
                <GraphQLRow
                  key={r.object_name}
                  result={r}
                  expanded={expanded}
                  onToggle={() => toggleExpand(r.object_name)}
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

function GraphQLRow({
  result,
  expanded,
  onToggle,
  scanId,
}: {
  result: GraphQLResult
  expanded: boolean
  onToggle: () => void
  scanId: string
}) {
  const [fields, setFields] = useState<GraphQLFieldInfo[]>(result.fields)
  const [fieldsLoading, setFieldsLoading] = useState(false)
  const [fieldsError, setFieldsError] = useState<string | null>(null)
  const [introspectLoading, setIntrospectLoading] = useState(false)
  const [introspectError, setIntrospectError] = useState<string | null>(null)
  const [writeTestLoading, setWriteTestLoading] = useState(false)
  const [writeTestResult, setWriteTestResult] = useState<GraphQLWriteTestResult | null>(null)
  const [writeTestError, setWriteTestError] = useState<string | null>(null)

  const count = result.total_count != null ? result.total_count.toString() : '-'
  const nFields = fields.length || '-'
  const hasFields = fields.length > 0
  const recordsUrl = `/scan/${scanId}/records/graphql/${result.object_name}`

  const handleFetchFields = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (fieldsLoading) return
    setFieldsLoading(true)
    setFieldsError(null)
    try {
      const data = await getObjectFields(scanId, result.object_name)
      setFields(data.fields)
    } catch (err) {
      setFieldsError(err instanceof Error ? err.message : String(err))
    } finally {
      setFieldsLoading(false)
    }
  }

  const handleIntrospectFields = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (introspectLoading) return
    setIntrospectLoading(true)
    setIntrospectError(null)
    try {
      const data = await introspectTypeFields(scanId, result.object_name)
      setFields(data.fields)
    } catch (err) {
      setIntrospectError(err instanceof Error ? err.message : String(err))
    } finally {
      setIntrospectLoading(false)
    }
  }

  const handleWriteTest = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (writeTestLoading) return
    setWriteTestLoading(true)
    setWriteTestError(null)
    setWriteTestResult(null)
    try {
      const data = await graphqlWriteTest({
        scan_id: scanId,
        object_name: result.object_name,
      })
      setWriteTestResult(data)
    } catch (err) {
      setWriteTestError(err instanceof Error ? err.message : String(err))
    } finally {
      setWriteTestLoading(false)
    }
  }

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
      </tr>
      {expanded && (
        <tr style={{ background: 'var(--bg)' }}>
          <td colSpan={5} className="p-4">
            {/* Action buttons */}
            <div className="flex gap-2 mb-3 flex-wrap">
              {!hasFields && (
                <>
                  <button
                    onClick={handleFetchFields}
                    disabled={fieldsLoading}
                    className="px-3 py-1 rounded text-xs font-semibold cursor-pointer inline-flex items-center gap-1"
                    style={{
                      background: 'var(--border)',
                      color: 'var(--text)',
                      opacity: fieldsLoading ? 0.6 : 1,
                    }}
                  >
                    {fieldsLoading && <Loader2 size={12} className="animate-spin" />}
                    Fetch Fields
                  </button>
                  <button
                    onClick={handleIntrospectFields}
                    disabled={introspectLoading}
                    className="px-3 py-1 rounded text-xs font-semibold cursor-pointer inline-flex items-center gap-1"
                    style={{
                      background: 'var(--border)',
                      color: 'var(--text)',
                      opacity: introspectLoading ? 0.6 : 1,
                    }}
                  >
                    {introspectLoading ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
                    Introspect Fields
                  </button>
                </>
              )}
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
              <button
                onClick={handleWriteTest}
                disabled={writeTestLoading}
                className="px-3 py-1 rounded text-xs font-semibold cursor-pointer inline-flex items-center gap-1"
                style={{
                  background: 'var(--border)',
                  color: 'var(--text)',
                  opacity: writeTestLoading ? 0.6 : 1,
                }}
              >
                {writeTestLoading ? <Loader2 size={12} className="animate-spin" /> : <FlaskConical size={12} />}
                Test Write (GraphQL)
              </button>
            </div>

            {/* Errors */}
            {fieldsError && (
              <div className="mb-3 p-2 rounded text-xs" style={{ background: 'var(--card)', color: 'var(--red, #ef4444)' }}>
                Fields: {fieldsError}
              </div>
            )}
            {introspectError && (
              <div className="mb-3 p-2 rounded text-xs" style={{ background: 'var(--card)', color: 'var(--red, #ef4444)' }}>
                Introspect: {introspectError}
              </div>
            )}
            {writeTestError && (
              <div className="mb-3 p-2 rounded text-xs" style={{ background: 'var(--card)', color: 'var(--red, #ef4444)' }}>
                Write test: {writeTestError}
              </div>
            )}

            {/* Write test result */}
            {writeTestResult && (
              <div className="mb-3 p-2 rounded text-xs" style={{ background: 'var(--card)' }}>
                <div className="font-semibold mb-1" style={{ color: 'var(--cyan)' }}>
                  GraphQL Write Test — {result.object_name}
                </div>
                {writeTestResult.create && (
                  <div className="flex items-center gap-2 mb-1">
                    <span style={{ color: writeTestResult.create.success ? 'var(--green, #22c55e)' : 'var(--red, #ef4444)' }}>
                      CREATE: {writeTestResult.create.success ? 'SUCCESS' : 'FAILED'}
                    </span>
                    {writeTestResult.create.record_id && (
                      <span style={{ color: 'var(--muted)' }}>ID: {writeTestResult.create.record_id}</span>
                    )}
                    {writeTestResult.create.error && (
                      <span style={{ color: 'var(--muted)' }}>{writeTestResult.create.error}</span>
                    )}
                  </div>
                )}
                {writeTestResult.delete && (
                  <div className="flex items-center gap-2 mb-1">
                    <span style={{ color: writeTestResult.delete.success ? 'var(--green, #22c55e)' : 'var(--red, #ef4444)' }}>
                      DELETE: {writeTestResult.delete.success ? 'SUCCESS' : 'FAILED'}
                    </span>
                    {writeTestResult.delete.error && (
                      <span style={{ color: 'var(--muted)' }}>{writeTestResult.delete.error}</span>
                    )}
                  </div>
                )}
                {writeTestResult.create?.proof && (
                  <div className="mt-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span style={{ color: 'var(--muted)' }}>Create mutation curl</span>
                      <CopyButton text={writeTestResult.create.proof} />
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Fields table */}
            {hasFields && (
              <table className="w-full text-xs mb-3">
                <thead>
                  <tr style={{ background: 'var(--border)' }}>
                    <th className="text-left px-2 py-1" style={{ color: 'var(--cyan)' }}>Field</th>
                    <th className="text-left px-2 py-1" style={{ color: 'var(--cyan)' }}>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {[...fields]
                    .sort((a, b) => a.name.localeCompare(b.name))
                    .map((f) => (
                      <tr key={f.name} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td className="px-2 py-1">{f.name}</td>
                        <td className="px-2 py-1" style={{ color: 'var(--muted)' }}>{f.data_type}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
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
