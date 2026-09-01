import type { ComponentType } from 'react'
import type { JobProgress, JobStatus, Tool } from '../../../types'
import BatchInventoryProgress from './BatchInventoryProgress'
import FtpDeployPanel from './FtpDeployPanel'

export interface ToolExtraProps {
  tool: Tool
  jobId: string | null
  status: JobStatus | null
  progress: JobProgress | null
  isRunning: boolean
  lastRunWasDryRun: boolean
}

export interface ToolExtras {
  /** Debajo de los campos, encima del botón Ejecutar. */
  beforeRun?: ComponentType<ToolExtraProps>
  /** Debajo del panel de logs. */
  afterRun?: ComponentType<ToolExtraProps>
}

/**
 * Piezas específicas de una herramienta. Cada extra decide por sí mismo si
 * corresponde renderizarse, así ToolRunPanel no necesita casos especiales.
 */
export const TOOL_EXTRAS: Record<string, ToolExtras> = {
  step_67: { beforeRun: BatchInventoryProgress },
  step_44: { afterRun: FtpDeployPanel },
}
