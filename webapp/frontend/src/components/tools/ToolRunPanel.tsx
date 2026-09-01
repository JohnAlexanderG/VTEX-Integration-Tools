import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, Download, Loader, Play } from 'lucide-react'
import type { JobStatus, Tool } from '../../types'
import { downloadJobFile, runTool } from '../../api/client'
import { useJob } from '../../hooks/useJob'
import { useToolForm } from '../../hooks/useToolForm'
import type { FieldValue } from '../../hooks/useToolForm'
import FormField from '../FormField'
import LogPanel from '../LogPanel'
import { Alert, Button } from '../ui'
import { TOOL_EXTRAS } from './extras'
import type { ToolExtraProps } from './extras'

interface Props {
  tool: Tool
  /** `null` = no se pudo determinar; no bloquea la ejecución. */
  vtexConfigured: boolean | null
  /** Job todavía vivo en el servidor para esta herramienta. */
  resumeJobId?: string | null
  initialValues?: Record<string, FieldValue>
  onJobStart?: (jobId: string) => void
  onComplete?: (jobId: string, outputFiles: string[]) => void
  onStatusChange?: (status: JobStatus | null) => void
}

export default function ToolRunPanel({
  tool,
  vtexConfigured,
  resumeJobId,
  initialValues = {},
  onJobStart,
  onComplete,
  onStatusChange,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null)
  const { values, setValue, validate, toPayload } = useToolForm(tool, initialValues)

  const [jobId, setJobId] = useState<string | null>(resumeJobId ?? null)
  const [error, setError] = useState<string | null>(null)
  const [showLogs, setShowLogs] = useState(() => Boolean(resumeJobId))
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [lastRunWasDryRun, setLastRunWasDryRun] = useState(false)

  const { logs, status, progress, outputFiles, exitCode, connectionState } = useJob(jobId)

  // resumeJobId puede llegar después del montaje (la búsqueda de jobs resuelve
  // tarde). Solo se adopta si todavía no hay job, para no pisar una corrida
  // que el usuario acaba de iniciar.
  useEffect(() => {
    if (!resumeJobId || jobId !== null) return
    setJobId(resumeJobId)
    setShowLogs(true)
  }, [resumeJobId, jobId])

  // Ambos callbacks van como efecto: llamarlos en el render dispara un
  // setState del padre mientras el hijo renderiza.
  useEffect(() => {
    onStatusChange?.(status)
  }, [status, onStatusChange])

  const notifiedJobRef = useRef<string | null>(null)
  useEffect(() => {
    if (status !== 'completed' || !jobId || outputFiles.length === 0) return
    if (notifiedJobRef.current === jobId) return
    notifiedJobRef.current = jobId
    onComplete?.(jobId, outputFiles)
  }, [status, jobId, outputFiles, onComplete])

  const isRunning = isSubmitting || status === 'running' || status === 'pending'
  const isBootstrapping =
    isSubmitting ||
    status === 'pending' ||
    (jobId !== null && status === 'running' && connectionState === 'connecting')
  const vtexWarning = tool.requires_vtex && vtexConfigured === false

  const handleRun = async () => {
    setError(null)

    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setIsSubmitting(true)
    setLastRunWasDryRun(values.dry_run === true)

    try {
      const { params, files } = toPayload()
      const result = await runTool(tool.id, params, files)
      setJobId(result.job_id)
      onJobStart?.(result.job_id)
      setShowLogs(true)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        })
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al ejecutar')
    } finally {
      setIsSubmitting(false)
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

  const { beforeRun: BeforeRun, afterRun: AfterRun } = TOOL_EXTRAS[tool.id] ?? {}
  const extraProps: ToolExtraProps = {
    tool,
    jobId,
    status,
    progress,
    isRunning,
    lastRunWasDryRun,
  }

  return (
    <div ref={panelRef} className="space-y-4">
      {vtexWarning && (
        <Alert tone="warning">Esta herramienta requiere credenciales VTEX configuradas.</Alert>
      )}

      {tool.inputs.map((inp) => (
        <FormField
          key={inp.name}
          field={inp}
          value={values[inp.name] ?? null}
          onChange={setValue}
          toolId={tool.id}
        />
      ))}

      {error && <Alert tone="error">{error}</Alert>}

      {isBootstrapping && (
        <Alert tone="info" icon={false}>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
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
        </Alert>
      )}

      {BeforeRun && <BeforeRun {...extraProps} />}

      <div className="flex items-center gap-3 pt-1 flex-wrap">
        <Button
          icon={isRunning ? undefined : Play}
          loading={isRunning}
          disabled={vtexWarning}
          onClick={() => void handleRun()}
        >
          {isRunning ? 'Ejecutando…' : 'Ejecutar'}
        </Button>

        {jobId && (
          <Button variant="ghost" size="sm" onClick={() => setShowLogs((v) => !v)}>
            {showLogs ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            Logs
          </Button>
        )}
      </div>

      {jobId && showLogs && (
        <div className="space-y-3 border-t border-line-1 pt-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
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
              <span className="text-xs text-green-400">Salió con código {exitCode}</span>
            )}
            {status === 'failed' && (
              <span className="text-xs text-red-400">Salió con código {exitCode}</span>
            )}
          </div>

          <LogPanel logs={logs} className="h-48" />

          {outputFiles.length > 0 && (
            <div>
              <p className="text-xs font-medium text-ink-3 mb-2">Archivos de salida</p>
              <div className="flex flex-wrap gap-2">
                {outputFiles.map((filename) => (
                  <Button
                    key={filename}
                    variant="secondary"
                    size="sm"
                    className="max-w-full"
                    onClick={() => void handleDownload(filename)}
                  >
                    <Download size={12} className="flex-shrink-0" />
                    <span className="truncate">{filename}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {AfterRun && <AfterRun {...extraProps} />}
    </div>
  )
}
