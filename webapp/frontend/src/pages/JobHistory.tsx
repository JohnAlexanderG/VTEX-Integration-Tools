import { useEffect, useState } from 'react'
import { Download, RefreshCw, Trash2 } from 'lucide-react'
import type { Job } from '../types'
import { fetchJobs, downloadJobFile, deleteJob } from '../api/client'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'

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
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)

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
      alert(e instanceof Error ? e.message : 'No se pudo descargar el archivo')
    }
  }

  const handleDelete = async (job: Job) => {
    const label = job.tool_name || job.id
    if (!window.confirm(`¿Eliminar el job "${label}" y sus archivos? Esta acción no se puede deshacer.`)) {
      return
    }
    setDeletingId(job.id)
    try {
      await deleteJob(job.id)
      setJobs((prev) => prev.filter((j) => j.id !== job.id))
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'No se pudo eliminar el job')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="p-4 md:p-6">
      <div className="mb-5 md:mb-6 flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-100">Historial de Jobs</h1>
          <p className="text-sm text-gray-500 mt-1">
            Ejecuciones pasadas y sus archivos de salida.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 border border-gray-700 rounded-lg text-xs text-gray-300 hover:text-white transition-colors flex-shrink-0"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Actualizar
        </button>
      </div>

      {error && (
        <div className="mb-4 text-xs text-red-400 bg-red-900/20 border border-red-800/50 rounded-lg px-3 py-2 max-w-3xl">
          {error}
        </div>
      )}

      <div className="space-y-3 max-w-3xl">
        {!loading && jobs.length === 0 && !error && (
          <p className="text-sm text-gray-600">No hay jobs registrados.</p>
        )}

        {jobs.map((job) => (
          <div key={job.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="px-4 md:px-5 py-4 border-b border-gray-800">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-100">{job.tool_name}</span>
                    <StatusBadge status={job.status} />
                    {isSuperAdmin && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-gray-800 text-gray-400 border border-gray-700 rounded">
                        Tenant {job.tenant_id}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{formatDateTime(job.created_at)}</p>
                </div>

                {isAdmin && (
                  <button
                    onClick={() => void handleDelete(job)}
                    disabled={deletingId === job.id}
                    title="Eliminar job"
                    className="flex-shrink-0 p-1.5 text-gray-500 hover:text-red-400 hover:bg-gray-800 disabled:opacity-40 rounded-lg transition-colors"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </div>

            {job.output_files.length > 0 && (
              <div className="px-4 md:px-5 py-4">
                <p className="text-xs font-medium text-gray-400 mb-2">Archivos de salida</p>
                <div className="flex flex-wrap gap-2">
                  {job.output_files.map((filename) => (
                    <button
                      key={filename}
                      type="button"
                      onClick={() => void handleDownload(job.id, filename)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-xs text-gray-300 hover:text-white transition-colors max-w-full"
                    >
                      <Download size={12} className="flex-shrink-0" />
                      <span className="truncate">{filename}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
