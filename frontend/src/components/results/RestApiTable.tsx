import type { RestApiResult } from '../../api/types'
import CopyButton from '../shared/CopyButton'

export default function RestApiTable({ result }: { result: RestApiResult }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-lg font-semibold" style={{ color: 'var(--cyan)' }}>
          REST API (API Enabled)
        </h3>
        <span
          className="px-2 py-0.5 rounded text-xs font-semibold"
          style={{
            background: result.api_enabled ? 'var(--green)' : 'var(--red)',
            color: result.api_enabled ? '#000' : '#fff',
          }}
        >
          {result.api_enabled ? 'ENABLED' : 'DISABLED'}
        </span>
      </div>

      <div
        className="rounded-lg overflow-hidden"
        style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
      >
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: 'var(--border)' }}>
              <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Check</th>
              <th className="text-center px-3 py-2" style={{ color: 'var(--cyan)' }}>Status</th>
              <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Endpoint</th>
              <th className="text-left px-3 py-2" style={{ color: 'var(--cyan)' }}>Detail</th>
              <th className="text-center px-3 py-2" style={{ color: 'var(--cyan)' }}></th>
            </tr>
          </thead>
          <tbody>
            {result.checks.map((check) => (
              <tr key={check.name} style={{ borderBottom: '1px solid var(--border)' }}>
                <td className="px-3 py-2 font-medium">{check.name}</td>
                <td className="text-center px-3 py-2">
                  <span style={{ color: check.success ? 'var(--green)' : 'var(--red)' }}>
                    {check.success ? '\u2713' : '\u2717'}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs" style={{ color: 'var(--muted)' }}>
                  {check.endpoint}
                </td>
                <td className="px-3 py-2 text-xs">
                  {check.detail || check.error || ''}
                </td>
                <td className="text-center px-3 py-2">
                  {check.proof && <CopyButton text={check.proof} />}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.soql_example_curl && (
        <div className="mt-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold" style={{ color: 'var(--cyan)' }}>
              SOQL Query (REST API)
            </span>
            <CopyButton text={result.soql_example_curl} />
          </div>
          <pre
            className="text-xs p-3 rounded"
            style={{
              background: 'var(--bg)',
              color: 'var(--green)',
              border: '1px solid var(--border)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {result.soql_example_curl}
          </pre>
        </div>
      )}
    </div>
  )
}
