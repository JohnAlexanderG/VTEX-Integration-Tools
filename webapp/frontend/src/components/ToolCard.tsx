import { useState, useCallback } from 'react'
import { Play, Square, ChevronDown, ChevronUp, AlertTriangle, Download } from 'lucide-react'
import type { Tool, JobStatus } from '../types'
import { runTool, getFileDownloadUrl } from '../api/client'
import { useJob } from '../hooks/useJob'
import FormField from './FormField'
import LogPanel from './LogPanel'

interface Props {
  tool: Tool
  vtexConfigured: boolean
  initialValues?: Record<string, string | boolean | File | null>
  onComplete?: (jobId: string, outputFiles: string[]) => void
}

type FieldValue = string | boolean | File | null

function StatusBadge({ status }: { status: JobStatus | null }) {
  if (!status) return null
  const map: Record<string, string> = {
    pending: 'bg-gray-700 text-gray-300',
    running: 'bg-blue-900 text-blue-300 animate-pulse',
    completed: 'bg-green-900 text-green-300',
    failed: 'bg-red-900 text-red-300',
  }
  const labels: Record<string, string> = {
    pending: 'Pendiente',
    running: 'Ejecutando…',
    completed: 'Completado',
    failed: 'Error',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${map[status]}`}>
      {labels[status]}
    </span>
  )
}

export default function ToolCard({ tool, vtexConfigured, initialValues = {}, onComplete }: Props) {
  const [formValues, setFormValues] = useState<Record<string, FieldValue>>(() => {
    const defaults: Record<string, FieldValue> = {}
    for (const inp of tool.inputs) {
      defaults[inp.name] =
        initialValues[inp.name] !== undefined
          ? (initialValues[inp.name] as FieldValue)
          : inp.default !== undefined
          ? (inp.default as FieldValue)
          : inp.type === 'checkbox'
          ? false
          : null
    }
    return defaults
  })

  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showLogs, setShowLogs] = useState(false)
  const { logs, status, outputFiles, exitCode } = useJob(jobId)

  const handleChange = useCallback((name: string, value: FieldValue) => {
    setFormValues((prev) => ({ ...prev, [name]: value }))
  }, [])

  const handleRun = async () => {
    setError(null)

    // Validate required fields
    for (const inp of tool.inputs) {
      if (inp.required && !formValues[inp.name]) {
        setError(`El campo "${inp.label}" es requerido.`)
        return
      }
    }

    const params: Record<string, string> = {}
    const files: Array<{ fieldName: string; file: File }> = []

    for (const inp of tool.inputs) {
      const val = formValues[inp.name]
      if (inp.type === 'file') {
        if (val instanceof File) {
          files.push({ fieldName: inp.name, file: val })
        }
      } else if (inp.type === 'checkbox') {
        if (val === true) params[inp.name] = 'true'
      } else if (val !== null && val !== undefined && val !== '') {
        params[inp.name] = String(val)
      }
    }

    try {
      const result = await runTool(tool.id, params, files)
      setJobId(result.job_id)
      setShowLogs(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al ejecutar')
    }
  }

  const isRunning = status === 'running' || status === 'pending'
  const vtexWarning = tool.requires_vtex && !vtexConfigured

  // Notify parent when job completes with output files
  if (status === 'completed' && outputFiles.length > 0 && jobId && onComplete) {
    onComplete(jobId, outputFiles)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-800">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-100">{tool.name}</h3>
            <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{tool.description}</p>
          </div>
          <div className="flex-shrink-0">
            <StatusBadge status={status} />
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="px-5 py-4 space-y-4">
        {vtexWarning && (
          <div className="flex items-center gap-2 bg-yellow-900/30 border border-yellow-700/50 rounded-lg px-3 py-2">
            <AlertTriangle size={14} className="text-yellow-400 flex-shrink-0" />
            <span className="text-xs text-yellow-300">
              Esta herramienta requiere credenciales VTEX configuradas.
            </span>
          </div>
        )}

        {tool.inputs.map((inp) => (
          <FormField
            key={inp.name}
            field={inp}
            value={formValues[inp.name] ?? null}
            onChange={handleChange}
          />
        ))}

        {error && (
          <div className="text-xs text-red-400 bg-red-900/20 border border-red-800/50 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleRun}
            disabled={isRunning || vtexWarning}
            className="flex items-center gap-2 px-4 py-2 bg-vtex-pink hover:bg-pink-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {isRunning ? <Square size={14} /> : <Play size={14} />}
            {isRunning ? 'Ejecutando…' : 'Ejecutar'}
          </button>

          {jobId && (
            <button
              onClick={() => setShowLogs((v) => !v)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200"
            >
              {showLogs ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              Logs
            </button>
          )}
        </div>
      </div>

      {/* Logs panel */}
      {jobId && showLogs && (
        <div className="border-t border-gray-800 px-5 py-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400">Logs</span>
            {status === 'completed' && (
              <span className="text-xs text-green-400">
                Salió con código {exitCode}
              </span>
            )}
            {status === 'failed' && (
              <span className="text-xs text-red-400">
                Salió con código {exitCode}
              </span>
            )}
          </div>
          <LogPanel logs={logs} className="h-48" />

          {/* Output files */}
          {outputFiles.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-400 mb-2">Archivos de salida</p>
              <div className="flex flex-wrap gap-2">
                {outputFiles.map((filename) => (
                  <a
                    key={filename}
                    href={getFileDownloadUrl(jobId, filename)}
                    download={filename}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-xs text-gray-300 hover:text-white transition-colors"
                  >
                    <Download size={12} />
                    {filename}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
