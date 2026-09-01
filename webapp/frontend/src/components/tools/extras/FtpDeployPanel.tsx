import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle, Upload, XCircle } from 'lucide-react'
import { deployToFtp, fetchFtpStatus } from '../../../api/client'
import type { DeployResult, FtpStatus } from '../../../api/client'
import { Alert, Button } from '../../ui'
import type { ToolExtraProps } from './index'

type DeployStatus = null | 'deploying' | 'done' | 'error'

/**
 * Envío del NDJSON de inventario por FTP (step_44). Es dueño de su propia
 * condición de visibilidad y de resetearse cuando cambia el job, así el panel
 * de ejecución no necesita saber que el FTP existe.
 */
export default function FtpDeployPanel({ jobId, status, lastRunWasDryRun }: ToolExtraProps) {
  const visible = Boolean(jobId) && status === 'completed' && !lastRunWasDryRun

  const [ftpStatus, setFtpStatus] = useState<FtpStatus | null>(null)
  const [deployStatus, setDeployStatus] = useState<DeployStatus>(null)
  const [deployResult, setDeployResult] = useState<DeployResult | null>(null)

  // Solo consulta el FTP cuando el panel aparece de verdad.
  useEffect(() => {
    if (!visible) return
    let cancelled = false
    fetchFtpStatus()
      .then((s) => {
        if (!cancelled) setFtpStatus(s)
      })
      .catch(() => {
        if (!cancelled) setFtpStatus(null)
      })
    return () => {
      cancelled = true
    }
  }, [visible])

  // Cada corrida nueva arranca con el envío en blanco.
  useEffect(() => {
    setDeployStatus(null)
    setDeployResult(null)
  }, [jobId])

  if (!visible || !jobId) return null

  const handleDeploy = async () => {
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

  const lambdaWarning = deployResult?.ok && !deployResult.lambda_invoked

  return (
    <div className="rounded-card border border-line-2 bg-surface-2/40 px-4 py-4 space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Upload size={13} className="text-blue-400 flex-shrink-0" />
        <span className="text-xs font-semibold text-ink-2">Envío de inventario</span>
      </div>

      <p className="text-xs text-ink-4 leading-relaxed">
        Sube el archivo <code className="text-ink-2 bg-surface-3 px-1 rounded">_to_update.ndjson</code>{' '}
        al servidor FTP e invoca{' '}
        <code className="text-ink-2 bg-surface-3 px-1 rounded">
          {ftpStatus?.lambda_function ?? 'demo-lambda'}
        </code>{' '}
        automáticamente.
      </p>

      {ftpStatus && !ftpStatus.ftp_configured && deployStatus !== 'done' && (
        <Alert tone="warning">
          Agrega <code>FTP_SERVER</code>, <code>FTP_USER</code> y <code>FTP_PASSWORD</code> en
          Configuración para habilitar esta acción.
        </Alert>
      )}

      {deployStatus !== 'done' && (
        <Button
          icon={Upload}
          loading={deployStatus === 'deploying'}
          disabled={ftpStatus !== null && !ftpStatus.ftp_configured}
          onClick={() => void handleDeploy()}
        >
          {deployStatus === 'deploying' ? 'Enviando…' : 'Enviar inventario por FTP'}
        </Button>
      )}

      {deployResult && deployStatus === 'done' && (
        <div className="space-y-2">
          <Alert tone={lambdaWarning ? 'warning' : 'success'} icon={false}>
            <div className="flex items-start gap-2">
              {lambdaWarning ? (
                <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" />
              ) : (
                <CheckCircle size={13} className="flex-shrink-0 mt-0.5" />
              )}
              <div className="space-y-0.5 min-w-0">
                <div className="break-words">
                  Archivo subido al FTP:{' '}
                  <code className="break-all">{deployResult.remote_filename}</code>
                </div>
                {deployResult.lambda_invoked ? (
                  <div>
                    Lambda <code>{deployResult.lambda_function}</code> invocada correctamente.
                  </div>
                ) : (
                  <div>FTP OK — Lambda no invocada: {deployResult.lambda_error}</div>
                )}
              </div>
            </div>
          </Alert>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setDeployStatus(null)
              setDeployResult(null)
            }}
          >
            Volver a enviar
          </Button>
        </div>
      )}

      {deployResult && deployStatus === 'error' && (
        <Alert tone="error" icon={false}>
          <div className="flex items-start gap-2">
            <XCircle size={13} className="flex-shrink-0 mt-0.5" />
            <span>{deployResult.error ?? 'Error desconocido'}</span>
          </div>
        </Alert>
      )}
    </div>
  )
}
