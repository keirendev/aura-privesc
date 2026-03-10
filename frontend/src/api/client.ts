import type {
  PresetConfig,
  ScanCreateRequest,
  ScanDetail,
  ScanStatus,
  ScanSummary,
} from './types'

const BASE = '/api'

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json()
}

export async function getPresets(): Promise<PresetConfig[]> {
  return fetchJson('/presets')
}

export async function createScan(body: ScanCreateRequest): Promise<ScanDetail> {
  return fetchJson('/scans', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function listScans(): Promise<ScanSummary[]> {
  return fetchJson('/scans')
}

export async function getScan(id: string): Promise<ScanDetail> {
  return fetchJson(`/scans/${id}`)
}

export async function getScanStatus(id: string): Promise<ScanStatus> {
  return fetchJson(`/scans/${id}/status`)
}

export async function deleteScan(id: string): Promise<void> {
  await fetchJson(`/scans/${id}`, { method: 'DELETE' })
}

export async function getObjectRecords(
  scanId: string,
  objectName: string,
): Promise<{ object_name: string; record_count: number | null; records: Record<string, unknown>[] }> {
  return fetchJson(`/scans/${scanId}/records/${objectName}`)
}

export async function graphqlRecords(body: {
  scan_id: string
  object_name: string
  fields: string[]
  first?: number
  after?: string | null
}): Promise<Record<string, unknown>> {
  return fetchJson('/graphql/records', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function graphqlQuery(body: {
  scan_id: string
  object_name: string
  fields: string[]
  where: Record<string, Record<string, string>>
  first?: number
}): Promise<Record<string, unknown>> {
  return fetchJson('/graphql/query', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function graphqlExplore(body: {
  scan_id: string
  object_name: string
  relationship: string
  fields: string[]
  first?: number
}): Promise<Record<string, unknown>> {
  return fetchJson('/graphql/explore', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
