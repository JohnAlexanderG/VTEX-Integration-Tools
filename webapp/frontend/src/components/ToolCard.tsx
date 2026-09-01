import { useState, useCallback, useRef, useEffect } from 'react'
import { Play, ChevronDown, ChevronUp, AlertTriangle, Download, Upload, CheckCircle, XCircle, Loader } from 'lucide-react'
import type { Tool, JobProgress } from '../types'
import { runTool, downloadJobFile, deployToFtp, fetchFtpStatus } from '../api/client'
import type { DeployResult, FtpStatus } from '../api/client'
import { useJob } from '../hooks/useJob'
import FormField from './FormField'
import LogPanel from './LogPanel'
import StatusBadge from './StatusBadge'

interface Props {
  tool: Tool
  /** `null` = no se pudo determinar; no bloquea la ejecución. */
  vtexConfigured: boolean | null
  initialValues?: Record<string, string | boolean | File | null>
  onComplete?: (jobId: string, outputFiles: string[]) => void
  /** Job todavía activo en el servidor para esta tool (reenganche tras reload/colapso). */
  resumeJobId?: string | null
  onJobStart?: (jobId: string) => void
}

type FieldValue = string | boolean | File | null
type DeployStatus = null | 'checking' | 'ready' | 'deploying' | 'done' | 'error'

function BatchInventoryProgress({ progress, isRunning }: { progress: JobProgress | null; isRunning: boolean }) {
  const rawPercent = typeof progress?.percent === 'number' ? progress.percent : null
  const percent = rawPercent === null ? null : Math.max(0, Math.min(100, rawPercent))
  const phase = progress?.phase ?? (isRunning ? 'running' : '')
  const isDone = phase === 'done'
  const isFailed = phase === 'failed'
  const accent = isFailed
    ? 'bg-red-400'
    : isDone
    ? 'bg-green-400'
    : 'bg-blue-400'
  const border = isFailed
    ? 'border-red-800/50 bg-red-900/15'
    : isDone
    ? 'border-green-800/50 bg-green-900/15'
    : 'border-blue-800/50 bg-blue-900/15'
  const title = progress?.phase_label ?? (isRunning ? 'Procesando batch inventory' : 'Batch inventory')
  const elapsed = typeof progress?.elapsed_seconds === 'number'
    ? `${progress.elapsed_seconds.toFixed(1)}s`
    : null

  return (
    <div className={`rounded-lg border px-3 py-3 space-y-3 ${border}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-ink-1 truncate">{title}</div>
          <div className="mt-0.5 text-[11px] text-ink-3">
            {progress?.part_number ? `Parte ${progress.part_number}` : 'Preparando partes'}
          </div>
        </div>
        {percent !== null && (
          <span className="text-xs font-medium text-ink-2 tabular-nums">{Math.round(percent)}%</span>
        )}
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
        {percent === null ? (
          <div className={`h-full w-1/3 rounded-full ${accent} animate-pulse`} />
        ) : (
          <div className={`h-full rounded-full ${accent} transition-all duration-500`} style={{ width: `${percent}%` }} />
        )}
      </div>

      <div className="grid gap-2 text-[11px] text-ink-3 sm:grid-cols-2">
        {progress?.batch_id && (
          <div className="min-w-0">
            <span className="text-ink-4">Batch: </span>
            <span className="break-all text-ink-2">{progress.batch_id}</span>
          </div>
        )}
        {progress?.status_name && (
          <div>
            <span className="text-ink-4">Status VTEX: </span>
            <span className={isFailed ? 'text-red-300' : isDone ? 'text-green-300' : 'text-blue-300'}>
              {progress.status_name}
            </span>
          </div>
        )}
        {(progress?.completed_parts !== undefined || progress?.failed_parts !== undefined) && (
          <div>
            <span className="text-ink-4">Partes: </span>
            <span className="text-ink-2">
              {progress.completed_parts ?? 0} OK / {progress.failed_parts ?? 0} error
            </span>
          </div>
        )}
        {elapsed && (
          <div>
            <span className="text-ink-4">Polling: </span>
            <span className="text-ink-2">{elapsed}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ToolCard({ tool, vtexConfigured, initialValues = {}, onComplete, resumeJobId, onJobStart }: Props) {
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

  const [jobId, setJobId] = useState<string | null>(resumeJobId ?? null)
  const [error, setError] = useState<string | null>(null)
  const [showLogs, setShowLogs] = useState(() => Boolean(resumeJobId))

  // resumeJobId puede llegar después del montaje (fetchJobs resuelve tarde).
  // Solo lo adoptamos si todavía no hay job, para no pisar una corrida recién
  // iniciada por el usuario.
  useEffect(() => {
    if (!resumeJobId || jobId !== null) return
    setJobId(resumeJobId)
    setShowLogs(true)
  }, [resumeJobId, jobId])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [lastRunWasDryRun, setLastRunWasDryRun] = useState(false)
  const { logs, status, progress, outputFiles, exitCode, connectionState } = useJob(jobId)

  // ── FTP Deploy state (only relevant for step_44) ──────────────────────────
  const isStockDiff = tool.id === 'step_44'
  const isBatchInventory = tool.id === 'step_67'
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
    setIsSubmitting(true)
    // Reset deploy state on new run
    if (isStockDiff) {
      setDeployStatus(null)
      setDeployResult(null)
    }

    // Validate required fields
    for (const inp of tool.inputs) {
      if (inp.required && !formValues[inp.name]) {
        setError(`El campo "${inp.label}" es requerido.`)
        setIsSubmitting(false)
        return
      }
    }

    setLastRunWasDryRun(formValues.dry_run === true)

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
      onJobStart?.(result.job_id)
      setShowLogs(true)
      // After the log panel expands, keep the card header in view
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        })
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al ejecutar')
    } finally {
      setIsSubmitting(false)
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

  const handleDownload = async (filename: string) => {
    if (!jobId) return
    try {
      await downloadJobFile(jobId, filename)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'No se pudo descargar el archivo')
    }
  }

  const isRunning = isSubmitting || status === 'running' || status === 'pending'
  const isBootstrapping =
    isSubmitting ||
    status === 'pending' ||
    (jobId !== null && status === 'running' && connectionState === 'connecting')
  // `false` significa "sabemos que no está configurado"; `null` es "no pudimos
  // averiguarlo" y no debe bloquear la ejecución (el backend valida igual).
  const vtexWarning = tool.requires_vtex && vtexConfigured === false

  // Notify parent when job completes with output files. Debe ser un efecto:
  // llamarlo durante el render dispara un setState del padre en pleno render
  // del hijo, y se repite en cada render mientras el job siga completado.
  const notifiedJobRef = useRef<string | null>(null)
  useEffect(() => {
    if (status !== 'completed' || !jobId || outputFiles.length === 0) return
    if (notifiedJobRef.current === jobId) return
    notifiedJobRef.current = jobId
    onComplete?.(jobId, outputFiles)
  }, [status, jobId, outputFiles, onComplete])

  const showDeploySection = isStockDiff && status === 'completed' && jobId && !lastRunWasDryRun
  const deployHasLambdaWarning = deployResult?.ok && !deployResult.lambda_invoked

  return (
    <div ref={cardRef} className="bg-surface-1 border border-line-1 rounded-card overflow-hidden">
      {/* Header */}
      <div className="px-4 md:px-5 py-4 border-b border-line-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-ink-1">{tool.name}</h3>
            <p className="text-xs text-ink-4 mt-0.5 leading-relaxed">{tool.description}</p>
          </div>
          <div className="flex-shrink-0">
            <StatusBadge status={status} />
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="px-4 md:px-5 py-4 space-y-4">
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

        {isBootstrapping && (
          <div className="bg-blue-900/20 border border-blue-800/50 rounded-lg px-3 py-3 space-y-2">
            <div className="flex items-center gap-2 text-xs text-blue-300">
              <Loader size={14} className="animate-spin flex-shrink-0" />
              <span>
                {isSubmitting
                  ? 'Subiendo archivos y enviando la ejecución al servidor. Esto puede tardar un momento con archivos grandes.'
                  : 'Preparando la ejecución y conectando los logs en tiempo real. Esto puede tardar un momento con archivos grandes.'}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
              <div className="h-full w-1/3 rounded-full bg-blue-400 animate-pulse" />
            </div>
          </div>
        )}

        {isBatchInventory && jobId && (progress || isRunning) && (
          <BatchInventoryProgress progress={progress} isRunning={isRunning} />
        )}

        <div className="flex items-center gap-3 pt-1 flex-wrap">
          <button
            onClick={handleRun}
            disabled={isRunning || vtexWarning}
            className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {isRunning ? <Loader size={14} className="animate-spin" /> : <Play size={14} />}
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
              className="flex items-center gap-1 text-xs text-ink-3 hover:text-ink-2"
            >
              {showLogs ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              Logs
            </button>
          )}
        </div>
      </div>

      {/* Logs panel */}
      {jobId && showLogs && (
        <div className="border-t border-line-1 px-4 md:px-5 py-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-3">Logs</span>
            {isSubmitting && (
              <span className="text-xs text-blue-400 flex items-center gap-1.5">
                <Loader size={12} className="animate-spin" />
                Enviando archivos…
              </span>
            )}
            {status === 'pending' && (
              <span className="text-xs text-blue-400 flex items-center gap-1.5">
                <Loader size={12} className="animate-spin" />
                Iniciando ejecución…
              </span>
            )}
            {status === 'running' && connectionState === 'reconnecting' && (
              <span className="text-xs text-blue-400 flex items-center gap-1.5">
                <Loader size={12} className="animate-spin" />
                Reconectando logs…
              </span>
            )}
            {status === 'running' && connectionState === 'stale' && (
              <span className="text-xs text-yellow-400 flex items-center gap-1.5">
                <Loader size={12} className="animate-spin" />
                Logs desconectados — el proceso sigue activo en el servidor
              </span>
            )}
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
              <p className="text-xs font-medium text-ink-3 mb-2">Archivos de salida</p>
                <div className="flex flex-wrap gap-2">
                  {outputFiles.map((filename) => (
                  <button
                    key={filename}
                    type="button"
                    onClick={() => {
                      void handleDownload(filename)
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-2 hover:bg-surface-3 border border-line-2 rounded-lg text-xs text-ink-2 hover:text-white transition-colors max-w-full"
                  >
                    <Download size={12} className="flex-shrink-0" />
                    <span className="truncate">{filename}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Envío de inventario — solo step_44, solo cuando completó ── */}
      {showDeploySection && (
        <div className="border-t border-line-2 px-4 md:px-5 py-4 bg-surface-2/40 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Upload size={13} className="text-blue-400 flex-shrink-0" />
            <span className="text-xs font-semibold text-ink-2">Envío de inventario</span>
            {ftpStatus && !ftpStatus.ftp_configured && (
              <span className="ml-auto text-[10px] px-1.5 py-0.5 bg-yellow-900/50 text-yellow-400 border border-yellow-700/50 rounded">
                FTP no configurado
              </span>
            )}
          </div>

          <p className="text-xs text-ink-4 leading-relaxed">
            Sube el archivo <code className="text-ink-2 bg-surface-3 px-1 rounded">_to_update.ndjson</code> al
            servidor FTP e invoca <code className="text-ink-2 bg-surface-3 px-1 rounded">{ftpStatus?.lambda_function ?? 'demo-lambda'}</code> automáticamente.
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
              {deployStatus === 'deploying' ? 'Enviando…' : 'Enviar inventario por FTP'}
            </button>
          )}

          {/* Deploy result */}
          {deployResult && deployStatus === 'done' && (
            <div className="space-y-2">
              <div className={`flex items-start gap-2 rounded-lg px-3 py-2 ${
                deployHasLambdaWarning
                  ? 'bg-yellow-900/20 border border-yellow-700/40'
                  : 'bg-green-900/20 border border-green-700/40'
              }`}>
                {deployHasLambdaWarning ? (
                  <AlertTriangle size={13} className="text-yellow-400 flex-shrink-0 mt-0.5" />
                ) : (
                  <CheckCircle size={13} className="text-green-400 flex-shrink-0 mt-0.5" />
                )}
                <div className={`text-xs space-y-0.5 min-w-0 ${
                  deployHasLambdaWarning ? 'text-yellow-300' : 'text-green-300'
                }`}>
                  <div className="break-words">
                    Archivo subido al FTP:{' '}
                    <code className={`${deployHasLambdaWarning ? 'text-yellow-200' : 'text-green-200'} break-all`}>
                      {deployResult.remote_filename}
                    </code>
                  </div>
                  {deployResult.lambda_invoked ? (
                    <div>
                      Lambda <code className="text-green-200">{deployResult.lambda_function}</code> invocada correctamente.
                    </div>
                  ) : (
                    <div>
                      FTP OK — Lambda no invocada: {deployResult.lambda_error}
                    </div>
                  )}
                </div>
              </div>
              <button
                onClick={() => { setDeployStatus(null); setDeployResult(null) }}
                className="text-xs text-ink-4 hover:text-ink-2 transition-colors"
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
