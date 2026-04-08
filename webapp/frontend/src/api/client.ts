import type { AccessCatalog, Config, Job, PermissionSet, TenantAccess, Tool } from '../types'

const BASE = '/api'

// ─── Auth header helper ───────────────────────────────────────────────────────

function authHeaders(): Record<string, string> {
  const token = sessionStorage.getItem('vtex_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** fetch con Authorization automático. Lanza error 401 como excepción especial. */
async function apiFetch(input: RequestInfo, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(input, {
    ...init,
    headers: { ...(init.headers as Record<string, string> ?? {}), ...authHeaders() },
  })
  if (res.status === 401) {
    sessionStorage.removeItem('vtex_token')
    sessionStorage.removeItem('vtex_user')
    window.location.href = '/login'
    throw new Error('Sesión expirada')
  }
  return res
}

// ─── WebSocket URL con token ──────────────────────────────────────────────────

export function buildWsUrl(jobId: string): string {
  const token    = sessionStorage.getItem('vtex_token') ?? ''
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host     = window.location.host
  return `${protocol}://${host}/ws/${jobId}?token=${encodeURIComponent(token)}`
}

// ─── Tools ───────────────────────────────────────────────────────────────────

export async function fetchTools(): Promise<Tool[]> {
  const res = await apiFetch(`${BASE}/tools`)
  if (!res.ok) throw new Error('Failed to fetch tools')
  const data = await res.json()
  return data.tools
}

// ─── Jobs ─────────────────────────────────────────────────────────────────────

export async function fetchJobs(): Promise<Job[]> {
  const res = await apiFetch(`${BASE}/jobs`)
  if (!res.ok) throw new Error('Failed to fetch jobs')
  const data = await res.json()
  return data.jobs
}

export async function fetchJob(jobId: string): Promise<Job> {
  const res = await apiFetch(`${BASE}/jobs/${jobId}`)
  if (!res.ok) throw new Error('Job not found')
  return res.json()
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiFetch(`${BASE}/jobs/${jobId}`, { method: 'DELETE' })
}

export async function runTool(
  toolId: string,
  params: Record<string, string>,
  files: Array<{ fieldName: string; file: File }>,
): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('params', JSON.stringify(params))
  for (const { fieldName, file } of files) {
    form.append(`file__${fieldName}`, file, file.name)
  }
  const res = await apiFetch(`${BASE}/tools/${toolId}/run`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(err.error || 'Failed to run tool')
  }
  return res.json()
}

// ─── Config ───────────────────────────────────────────────────────────────────

export async function fetchConfig(): Promise<Config> {
  const res = await apiFetch(`${BASE}/config`)
  if (!res.ok) throw new Error('Failed to fetch config')
  return res.json()
}

export async function updateConfig(values: Record<string, string>): Promise<void> {
  const res = await apiFetch(`${BASE}/config`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(values),
  })
  if (!res.ok) throw new Error('Failed to update config')
}

export function getFileDownloadUrl(jobId: string, filename: string): string {
  return `${BASE}/jobs/${jobId}/files/${encodeURIComponent(filename)}`
}

// ─── FTP Deploy ───────────────────────────────────────────────────────────────

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
  const res = await apiFetch(`${BASE}/ftp-status`)
  if (!res.ok) throw new Error('Failed to fetch FTP status')
  return res.json()
}

export async function deployToFtp(jobId: string): Promise<DeployResult> {
  const res  = await apiFetch(`${BASE}/jobs/${jobId}/ftp-deploy`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Error al enviar al pipeline')
  return data
}

// ─── Users API ────────────────────────────────────────────────────────────────

export interface ApiUser {
  id:          number
  username:    string
  email:       string | null
  role:        string
  is_active:   boolean
  tenant_id:   number
  tenant_slug: string
  tenant_name: string
  created_at:  string
}

export async function fetchUsers(): Promise<ApiUser[]> {
  const res = await apiFetch(`${BASE}/users`)
  if (!res.ok) throw new Error('Failed to fetch users')
  const data = await res.json()
  return data.users
}

export async function createUser(payload: {
  username:  string
  password:  string
  email?:    string
  role:      string
  tenant_id?: number
}): Promise<void> {
  const res = await apiFetch(`${BASE}/users`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Error al crear usuario' }))
    throw new Error(err.error)
  }
}

export async function updateUser(
  id: number,
  payload: Partial<{ is_active: boolean; role: string; email: string; password: string }>,
): Promise<void> {
  const res = await apiFetch(`${BASE}/users/${id}`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Error al actualizar' }))
    throw new Error(err.error)
  }
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const res = await apiFetch('/auth/change-password', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Error al cambiar contraseña' }))
    throw new Error(err.error)
  }
}

// ─── Tenant Access API ───────────────────────────────────────────────────────

export async function fetchAccessOverview(): Promise<{ catalog: AccessCatalog; tenants: TenantAccess[] }> {
  const res = await apiFetch(`${BASE}/access`)
  if (!res.ok) throw new Error('Failed to fetch access overview')
  return res.json()
}

export async function updateTenantAccess(
  tenantId: number,
  permissions: Record<string, boolean>,
): Promise<PermissionSet> {
  const res = await apiFetch(`${BASE}/access/${tenantId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ permissions }),
  })
  const data = await res.json().catch(() => ({ error: 'Error al actualizar accesos' }))
  if (!res.ok) throw new Error(data.error || 'Error al actualizar accesos')
  return data.permissions
}
