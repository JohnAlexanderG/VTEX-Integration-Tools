import { useEffect, useState } from 'react'
import { Download, History, RefreshCw, Trash2 } from 'lucide-react'
import type { Job } from '../types'
import { fetchJobs, downloadJobFile, deleteJob, reconcileJobs } from '../api/client'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'
import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  PageHeader,
  Skeleton,
  useToast,
} from '../components/ui'

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

      <div className="space-y-3 max-w-3xl">
        {loading && <Skeleton className="h-24" count={3} />}

        {!loading && jobs.length === 0 && !error && (
          <EmptyState
            icon={History}
            title="No hay jobs registrados"
            description="Cuando ejecutes una herramienta, su corrida aparece acá con sus archivos de salida."
          />
        )}

        {!loading &&
          jobs.map((job) => (
            <Card key={job.id} padded={false} className="overflow-hidden">
              <div className="px-4 md:px-5 py-4 border-b border-line-1">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-ink-1">{job.tool_name}</span>
                      <StatusBadge status={job.status} />
                      {isSuperAdmin && <Badge>Tenant {job.tenant_id}</Badge>}
                    </div>
                    <p className="text-xs text-ink-4 mt-0.5">{formatDateTime(job.created_at)}</p>
                  </div>

                  {isAdmin && (
                    <button
                      onClick={() => setJobToDelete(job)}
                      disabled={deletingId === job.id}
                      title="Eliminar job"
                      aria-label={`Eliminar job ${job.tool_name}`}
                      className="flex-shrink-0 rounded-control p-1.5 text-ink-4 hover:bg-surface-2 hover:text-red-400 disabled:opacity-40"
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </div>

              {job.output_files.length > 0 && (
                <div className="px-4 md:px-5 py-4">
                  <p className="text-xs font-medium text-ink-3 mb-2">Archivos de salida</p>
                  <div className="flex flex-wrap gap-2">
                    {job.output_files.map((filename) => (
                      <Button
                        key={filename}
                        variant="secondary"
                        size="sm"
                        className="max-w-full"
                        onClick={() => void handleDownload(job.id, filename)}
                      >
                        <Download size={12} className="flex-shrink-0" />
                        <span className="truncate">{filename}</span>
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          ))}
      </div>

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
