import { useState, useCallback, useRef, useEffect } from 'react'
import { Play, Square, ChevronDown, ChevronUp, AlertTriangle, Download, Upload, CheckCircle, XCircle, Loader } from 'lucide-react'
import type { Tool, JobStatus } from '../types'
import { runTool, getFileDownloadUrl, deployToFtp, fetchFtpStatus } from '../api/client'
import type { DeployResult, FtpStatus } from '../api/client'
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
type DeployStatus = null | 'checking' | 'ready' | 'deploying' | 'done' | 'error'

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
  const cardRef = useRef<HTMLDivElement>(null)
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

  // ── FTP Deploy state (only relevant for step_44) ──────────────────────────
  const isStockDiff = tool.id === 'step_44'
  const [ftpStatus, setFtpStatus] = useState<FtpStatus | null>(null)
  const [deployStatus, setDeployStatus] = useState<DeployStatus>(null)
  const [deployResult, setDeployResult] = useState<DeployResult | null>(null)

  // Check FTP config once when component mounts (only for step_44)
  useEffect(() => {
    if (!isStockDiff) return
    fetchFtpStatus()
      .then(setFtpStatus)
      .catch(() => setFtpStatus(null))
  }, [isStockDiff])

  const handleChange = useCallback((name: string, value: FieldValue) => {
    setFormValues((prev) => ({ ...prev, [name]: value }))
  }, [])

  const handleRun = async () => {
    setError(null)
    // Reset deploy state on new run
    if (isStockDiff) {
      setDeployStatus(null)
      setDeployResult(null)
    }

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
      // After the log panel expands, keep the card header in view
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        })
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al ejecutar')
    }
  }

  const handleDeploy = async () => {
    if (!jobId) return
    setDeployStatus('deploying')
    setDeployResult(null)
    try {
      const result = await deployToFtp(jobId)
      setDeployResult(result)
      setDeployStatus(result.ok ? 'done' : 'error')
    } catch (e: unknown) {
      setDeployResult({ ok: false, error: e instanceof Error ? e.message : 'Error desconocido' })
      setDeployStatus('error')
    }
  }

  const isRunning = status === 'running' || status === 'pending'
  const vtexWarning = tool.requires_vtex && !vtexConfigured

  // Notify parent when job completes with output files
  if (status === 'completed' && outputFiles.length > 0 && jobId && onComplete) {
    onComplete(jobId, outputFiles)
  }

  const showDeploySection = isStockDiff && status === 'completed' && jobId

  return (
    <div ref={cardRef} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
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
            toolId={tool.id}
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
              onClick={() => {
                setShowLogs((v) => {
                  if (!v) {
                    requestAnimationFrame(() => {
                      requestAnimationFrame(() => {
                        cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                      })
                    })
                  }
                  return !v
                })
              }}
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

      {/* ── Deploy to Pipeline — solo step_44, solo cuando completó ── */}
      {showDeploySection && (
        <div className="border-t border-gray-700 px-5 py-4 bg-gray-800/40 space-y-3">
          <div className="flex items-center gap-2">
            <Upload size={13} className="text-blue-400 flex-shrink-0" />
            <span className="text-xs font-semibold text-gray-200">Pipeline de inventario</span>
            {ftpStatus && !ftpStatus.ftp_configured && (
              <span className="ml-auto text-[10px] px-1.5 py-0.5 bg-yellow-900/50 text-yellow-400 border border-yellow-700/50 rounded">
                FTP no configurado
              </span>
            )}
          </div>

          <p className="text-xs text-gray-500 leading-relaxed">
            Sube el archivo <code className="text-gray-300 bg-gray-700 px-1 rounded">_to_update.ndjson</code> al
            servidor FTP e invoca <code className="text-gray-300 bg-gray-700 px-1 rounded">{ftpStatus?.lambda_function ?? 'demo-lambda'}</code> automáticamente.
          </p>

          {/* FTP not configured warning */}
          {ftpStatus && !ftpStatus.ftp_configured && deployStatus !== 'done' && (
            <div className="flex items-start gap-2 bg-yellow-900/20 border border-yellow-700/40 rounded-lg px-3 py-2">
              <AlertTriangle size={13} className="text-yellow-400 flex-shrink-0 mt-0.5" />
              <span className="text-xs text-yellow-300">
                Agrega <code>FTP_SERVER</code>, <code>FTP_USER</code> y <code>FTP_PASSWORD</code> al archivo <code>.env</code> para habilitar esta acción.
              </span>
            </div>
          )}

          {/* Deploy button */}
          {deployStatus !== 'done' && (
            <button
              onClick={handleDeploy}
              disabled={deployStatus === 'deploying' || (ftpStatus !== null && !ftpStatus.ftp_configured)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-700 hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
            >
              {deployStatus === 'deploying' ? (
                <Loader size={14} className="animate-spin" />
              ) : (
                <Upload size={14} />
              )}
              {deployStatus === 'deploying' ? 'Enviando al pipeline…' : 'Enviar al pipeline de inventario'}
            </button>
          )}

          {/* Deploy result */}
          {deployResult && deployStatus === 'done' && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 bg-green-900/20 border border-green-700/40 rounded-lg px-3 py-2">
                <CheckCircle size={13} className="text-green-400 flex-shrink-0" />
                <div className="text-xs text-green-300 space-y-0.5">
                  <div>
                    Archivo subido al FTP:{' '}
                    <code className="text-green-200">{deployResult.remote_filename}</code>
                  </div>
                  {deployResult.lambda_invoked ? (
                    <div>
                      Lambda <code className="text-green-200">{deployResult.lambda_function}</code> invocada correctamente.
                    </div>
                  ) : (
                    <div className="text-yellow-300">
                      FTP OK — Lambda no invocada: {deployResult.lambda_error}
                    </div>
                  )}
                </div>
              </div>
              <button
                onClick={() => { setDeployStatus(null); setDeployResult(null) }}
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                Volver a enviar
              </button>
            </div>
          )}

          {deployResult && deployStatus === 'error' && (
            <div className="flex items-start gap-2 bg-red-900/20 border border-red-700/40 rounded-lg px-3 py-2">
              <XCircle size={13} className="text-red-400 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-red-300">
                {deployResult.error ?? 'Error desconocido'}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
