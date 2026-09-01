import { useEffect, useMemo, useState } from 'react'
import { Download, History, RefreshCw, Search, Trash2 } from 'lucide-react'
import type { Job, JobStatus } from '../types'
import { fetchJobs, downloadJobFile, deleteJob, reconcileJobs } from '../api/client'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'
import {
  Alert,
  Button,
  ConfirmDialog,
  EmptyState,
  Input,
  PageHeader,
  Select,
  Skeleton,
  useToast,
} from '../components/ui'

const STATUS_OPTIONS: { value: JobStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Todos los estados' },
  { value: 'pending', label: 'Pendiente' },
  { value: 'running', label: 'Ejecutando' },
  { value: 'completed', label: 'Completado' },
  { value: 'failed', label: 'Con errores' },
]

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function JobHistory() {
  const { isAdmin, isSuperAdmin } = useAuth()
  const toast = useToast()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<JobStatus | 'all'>('all')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [jobToDelete, setJobToDelete] = useState<Job | null>(null)
  const [reconciling, setReconciling] = useState(false)

  const load = () => {
    setLoading(true)
    setError('')
    fetchJobs()
      .then(setJobs)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo cargar el historial'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    return jobs.filter((job) => {
      const matchesStatus = statusFilter === 'all' || job.status === statusFilter
      const matchesSearch = term === '' || job.tool_name.toLowerCase().includes(term)
      return matchesStatus && matchesSearch
    })
  }, [jobs, search, statusFilter])

  const handleDownload = async (jobId: string, filename: string) => {
    try {
      await downloadJobFile(jobId, filename)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'No se pudo descargar el archivo')
    }
  }

  const confirmDelete = async () => {
    if (!jobToDelete) return
    setDeletingId(jobToDelete.id)
    try {
      await deleteJob(jobToDelete.id)
      setJobs((prev) => prev.filter((j) => j.id !== jobToDelete.id))
      setJobToDelete(null)
      toast.success('Job eliminado.')
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'No se pudo eliminar el job')
    } finally {
      setDeletingId(null)
    }
  }

  const handleReconcile = async () => {
    setReconciling(true)
    setError('')
    setNotice('')
    try {
      const result = await reconcileJobs()
      const base = result.recovered === 1
        ? 'Se recuperó 1 job desde archivos existentes.'
        : `Se recuperaron ${result.recovered} jobs desde archivos existentes.`
      const firstError = result.errors?.[0]?.error
      setNotice(result.failed > 0 && firstError
        ? `${base} ${result.failed} no se pudieron recuperar. Primer error: ${firstError}`
        : result.failed > 0
          ? `${base} ${result.failed} no se pudieron recuperar.`
          : base)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'No se pudieron recuperar archivos existentes')
    } finally {
      setReconciling(false)
    }
  }

  return (
    <div className="p-4 md:p-6">
      <PageHeader
        title="Historial de Jobs"
        description="Ejecuciones pasadas y sus archivos de salida."
        actions={
          <>
            {isSuperAdmin && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void handleReconcile()}
                disabled={loading || reconciling}
              >
                <RefreshCw size={13} className={reconciling ? 'animate-spin' : ''} />
                Recuperar archivos
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              Actualizar
            </Button>
          </>
        }
      />

      {error && <Alert tone="error" className="mb-4 max-w-3xl">{error}</Alert>}
      {notice && !error && <Alert tone="success" className="mb-4 max-w-3xl">{notice}</Alert>}

      {!loading && jobs.length > 0 && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center mb-4">
          <div className="w-full sm:w-72">
            <Input
              type="text"
              leftIcon={Search}
              placeholder="Buscar por herramienta…"
              aria-label="Buscar por herramienta"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="w-full sm:w-48">
            <Select
              aria-label="Filtrar por estado"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as JobStatus | 'all')}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </div>
        </div>
      )}

      {loading && <Skeleton className="h-10" count={4} />}

      {!loading && jobs.length === 0 && !error && (
        <EmptyState
          icon={History}
          title="No hay jobs registrados"
          description="Cuando ejecutes una herramienta, su corrida aparece acá con sus archivos de salida."
        />
      )}

      {!loading && jobs.length > 0 && filtered.length === 0 && (
        <EmptyState
          icon={Search}
          title="Sin resultados"
          description="Ningún job coincide con la búsqueda o el filtro aplicado."
        />
      )}

      {!loading && filtered.length > 0 && (
        <div className="overflow-x-auto rounded-card border border-line-1">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line-1">
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-4">
                  Herramienta
                </th>
                {isSuperAdmin && (
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-4">
                    Tenant
                  </th>
                )}
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-4">
                  Estado
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-4">
                  Fecha
                </th>
                <th className="px-4 py-2.5" />
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((job) => (
                <tr key={job.id} className="border-b border-line-1 last:border-b-0 hover:bg-surface-1">
                  <td className="px-4 py-3 font-medium text-ink-1">{job.tool_name}</td>
                  {isSuperAdmin && (
                    <td className="px-4 py-3 text-ink-4">{job.tenant_name}</td>
                  )}
                  <td className="px-4 py-3">
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="px-4 py-3 text-ink-4">{formatDateTime(job.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col items-start gap-1.5">
                      {job.output_files.map((filename) => (
                        <Button
                          key={filename}
                          variant="secondary"
                          size="sm"
                          className="max-w-[220px]"
                          onClick={() => void handleDownload(job.id, filename)}
                          title={filename}
                        >
                          <Download size={12} className="flex-shrink-0" />
                          <span className="truncate">{filename}</span>
                        </Button>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {isAdmin && (
                      <button
                        onClick={() => setJobToDelete(job)}
                        disabled={deletingId === job.id}
                        title="Eliminar job"
                        aria-label={`Eliminar job ${job.tool_name}`}
                        className="rounded-control p-1.5 text-ink-4 hover:bg-surface-2 hover:text-red-400 disabled:opacity-40"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={jobToDelete !== null}
        title="Eliminar job"
        message={
          <>
            Se eliminará <span className="font-medium text-ink-1">{jobToDelete?.tool_name || jobToDelete?.id}</span>{' '}
            y sus archivos generados. Esta acción no se puede deshacer.
          </>
        }
        confirmLabel="Eliminar"
        loading={deletingId !== null}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setJobToDelete(null)}
      />
    </div>
  )
}
