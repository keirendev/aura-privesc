export interface ScanStatus {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  phase: string
  progress: number
  phase_detail: string
}

export interface ScanSummary {
  id: string
  url: string
  status: string
  phase: string
  progress: number
  summary: ScanSummaryStats | null
  created_at: string
  finished_at: string | null
}

export interface ScanSummaryStats {
  objects_scanned: number
  accessible: number
  writable: number
  proven_writes: number
  callable_apex: number
  graphql_counted: number
  graphql_available: boolean
}

export interface ScanDetail {
  id: string
  url: string
  config: Record<string, unknown>
  status: string
  phase: string
  progress: number
  phase_detail: string
  result: ScanResult | null
  error: string | null
  logs: string | null
  summary: ScanSummaryStats | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface ScanResult {
  target_url: string
  discovery: DiscoveryInfo | null
  user_info: UserInfo | null
  soql_capable: boolean
  objects: ObjectResult[]
  apex_results: ApexResult[]
  graphql_available: boolean
  graphql_results: GraphQLResult[]
  aura_url: string | null
  aura_token: string | null
  aura_context: string | null
  sid: string | null
}

export interface DiscoveryInfo {
  endpoint: string
  fwuid: string | null
  app_name: string | null
  mode: string
}

export interface UserInfo {
  user_id: string | null
  username: string | null
  display_name: string | null
  email: string | null
  is_guest: boolean
}

export interface CrudPermissions {
  createable: boolean
  readable: boolean
  updateable: boolean
  deletable: boolean
  queryable: boolean
}

export interface CrudOperationResult {
  operation: string
  success: boolean
  record_id: string | null
  error: string | null
  proof: string | null
  timestamp: string | null
}

export interface CrudValidationResult {
  object_name: string
  read: CrudOperationResult | null
  create: CrudOperationResult | null
  update: CrudOperationResult | null
  delete: CrudOperationResult | null
  skipped: boolean
  skip_reason: string | null
}

export interface ObjectResult {
  name: string
  accessible: boolean
  crud: CrudPermissions
  record_count: number | null
  sample_records: Record<string, unknown>[]
  risk: string
  error: string | null
  proof: string | null
  proof_records: string | null
  validated: boolean | null
  validation_detail: string | null
  crud_validation: CrudValidationResult | null
}

export interface ApexResult {
  controller_method: string
  status: 'callable' | 'denied' | 'not_found' | 'error'
  message: string | null
  proof: string | null
  validated: boolean | null
  validation_detail: string | null
}

export interface GraphQLFieldInfo {
  name: string
  data_type: string
}

export interface GraphQLResult {
  object_name: string
  total_count: number | null
  fields: GraphQLFieldInfo[]
  error: string | null
  proof_count: string | null
  proof_fields: string | null
}

export interface PresetConfig {
  id: string
  label: string
  description: string
  config: Record<string, unknown>
}

export interface ScanCreateRequest {
  url: string
  token?: string | null
  sid?: string | null
  manual_context?: string | null
  manual_endpoint?: string | null
  skip_crud?: boolean
  skip_records?: boolean
  skip_apex?: boolean
  skip_validation?: boolean
  skip_crud_test?: boolean
  skip_graphql?: boolean
  timeout?: number
  delay?: number
  concurrency?: number
  proxy?: string | null
  insecure?: boolean
  verbose?: boolean
}
