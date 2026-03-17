export interface ToolInput {
  name: string
  type: 'file' | 'text' | 'number' | 'checkbox' | 'select'
  label: string
  required?: boolean
  accept?: string
  default?: string | number | boolean
  flag?: string
  position?: number
  role?: 'input_file' | 'output_file' | 'param'
  options?: string[]
}

export interface Tool {
  id: string
  name: string
  shortName: string
  description: string
  category: 'pipeline' | 'tools'
  step?: number
  script: string
  requires_vtex: boolean
  inputs: ToolInput[]
}

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed'

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
  type: 'log' | 'status' | 'outputs' | 'ping'
  stream?: 'stdout' | 'stderr' | 'system'
  text?: string
  status?: JobStatus
  exit_code?: number
  files?: string[]
}

export interface Config {
  configured: boolean
  values: Record<string, string>
}
