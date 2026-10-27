import type { ComponentType } from 'react'
import type { JobProgress, JobStatus, Tool } from '../../../types'
import BatchInventoryProgress from './BatchInventoryProgress'
import FtpDeployPanel from './FtpDeployPanel'
import MasterDataDeleteGuard from './MasterDataDeleteGuard'
import SellerPortalProgress from './SellerPortalProgress'

export interface ToolExtraProps {
  tool: Tool
  jobId: string | null
  status: JobStatus | null
  progress: JobProgress | null
  isRunning: boolean
  lastRunWasDryRun: boolean
  /** Cuenta VTEX del tenant sobre la que corre la herramienta. */
  vtexAccount: string | null
  vtexEnvironment: string | null
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
  step_78: { beforeRun: MasterDataDeleteGuard },
  step_79: { beforeRun: SellerPortalProgress },
}
