export interface ToolInput {
  name: string
  type: 'file' | 'text' | 'number' | 'checkbox' | 'select'
  label: string
  required?: boolean
  accept?: string
  default?: string | number | boolean
  flag?: string
  position?: number
  role?: 'input_file' | 'output_file' | 'output_dir' | 'param'
  options?: string[]
}

export interface Tool {
  id: string
  name: string
  shortName: string
  description: string
  category: 'tools' | string
  step?: number
  script: string
  requires_vtex: boolean
  inputs: ToolInput[]
  enabled?: boolean
  blocked_reason?: string | null
}

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface JobProgress {
  tool_id?: string
  phase?: 'dry_run' | 'create' | 'upload' | 'commit' | 'status_polling' | 'done' | 'failed' | string
  phase_label?: string
  part_number?: number
  batch_id?: string
  rows?: number
  bytes?: number
  status_name?: string
  http_status?: number | string
  percent?: number
  completed_parts?: number
  failed_parts?: number
  elapsed_seconds?: number
  attempt?: number
  message?: string
  status_metrics?: Record<string, string | number | boolean | null>
}

export interface Job {
  id: string
  tool_id: string
  tool_name: string
  status: JobStatus
  created_at: string
  finished_at: string | null
  exit_code: number | null
  command: string[]
  output_files: string[]
  job_dir: string
}

export interface LogEntry {
  type: 'log' | 'status' | 'outputs' | 'progress' | 'ping'
  stream?: 'stdout' | 'stderr' | 'system'
  text?: string
  status?: JobStatus
  exit_code?: number
  files?: string[]
  progress?: JobProgress
}

export interface Config {
  configured: boolean
  values: Record<string, string>
}

export interface PermissionSet {
  sections: Record<string, boolean>
  tools: Record<string, boolean>
}

export interface AccessCatalogSection {
  id: string
  label: string
  description: string
  permission_key: string
}

export interface AccessCatalogTool {
  id: string
  name: string
  shortName: string
  category: 'tools' | string
  step?: number
  permission_key: string
}

export interface AccessCatalog {
  sections: AccessCatalogSection[]
  tools: AccessCatalogTool[]
}

export interface TenantAccessUser {
  id: number
  username: string
  email: string | null
  role: string
  is_active: boolean
  tenant_id: number
  tenant_slug: string
  tenant_name: string
  created_at: string
}

export interface TenantAccess {
  id: number
  name: string
  slug: string
  is_active: boolean
  users: TenantAccessUser[]
  permissions: PermissionSet
}
