import type { Tool, Job, Config } from '../types'

const BASE = '/api'

export async function fetchTools(): Promise<Tool[]> {
  const res = await fetch(`${BASE}/tools`)
  if (!res.ok) throw new Error('Failed to fetch tools')
  const data = await res.json()
  return data.tools
}

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch(`${BASE}/jobs`)
  if (!res.ok) throw new Error('Failed to fetch jobs')
  const data = await res.json()
  return data.jobs
}

export async function fetchJob(jobId: string): Promise<Job> {
  const res = await fetch(`${BASE}/jobs/${jobId}`)
  if (!res.ok) throw new Error('Job not found')
  return res.json()
}

export async function deleteJob(jobId: string): Promise<void> {
  await fetch(`${BASE}/jobs/${jobId}`, { method: 'DELETE' })
}

export async function runTool(
  toolId: string,
  params: Record<string, string>,
  files: Array<{ fieldName: string; file: File }>,
): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('params', JSON.stringify(params))
  // Each file is submitted as file__{fieldName} so the backend can map them back
  for (const { fieldName, file } of files) {
    form.append(`file__${fieldName}`, file, file.name)
  }

  const res = await fetch(`${BASE}/tools/${toolId}/run`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(err.error || 'Failed to run tool')
  }
  return res.json()
}

export async function fetchConfig(): Promise<Config> {
  const res = await fetch(`${BASE}/config`)
  if (!res.ok) throw new Error('Failed to fetch config')
  return res.json()
}

export async function updateConfig(values: Record<string, string>): Promise<void> {
  const res = await fetch(`${BASE}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  })
  if (!res.ok) throw new Error('Failed to update config')
}

export function getFileDownloadUrl(jobId: string, filename: string): string {
  return `${BASE}/jobs/${jobId}/files/${encodeURIComponent(filename)}`
}

// ── FTP Deploy — Pipeline de inventario ──────────────────────────────────────

export interface DeployResult {
  ok: boolean
  source_file?: string
  remote_filename?: string
  ftp_server?: string
  lambda_invoked?: boolean
  lambda_function?: string
  lambda_response?: Record<string, unknown> | null
  lambda_error?: string | null
  error?: string
}

export interface FtpStatus {
  ftp_configured: boolean
  lambda_function: string
  aws_region: string
}

export async function fetchFtpStatus(): Promise<FtpStatus> {
  const res = await fetch(`${BASE}/ftp-status`)
  if (!res.ok) throw new Error('Failed to fetch FTP status')
  return res.json()
}

export async function deployToFtp(jobId: string): Promise<DeployResult> {
  const res = await fetch(`${BASE}/jobs/${jobId}/ftp-deploy`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.error || 'Error al enviar al pipeline')
  }
  return data
}
