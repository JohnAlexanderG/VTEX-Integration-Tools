import { Alert } from '../../ui'
import type { ToolExtraProps } from './index'

/**
 * Aviso permanente de la cuenta destino para el borrado de Master Data
 * (step_78). Las credenciales vienen del tenant logueado, no del .env del
 * servidor, así que la cuenta mostrada es exactamente donde se borrará.
 */
export default function MasterDataDeleteGuard({ vtexAccount, vtexEnvironment }: ToolExtraProps) {
  return (
    <Alert tone="error" title="Acción irreversible">
      <div className="space-y-1.5">
        <p>
          Los documentos se eliminarán en la cuenta VTEX{' '}
          <strong>{vtexAccount ?? '(no configurada)'}</strong>
          {vtexEnvironment ? ` (${vtexEnvironment})` : ''}, configurada para tu tenant.
        </p>
        <p>
          Antes de borrar, exporta la entidad completa con “Exportar Master Data” (campos{' '}
          <code>_all</code>) y descarga el CSV como respaldo. Ejecuta primero en dry-run.
        </p>
        <p>El borrado real solo lo pueden ejecutar administradores.</p>
      </div>
    </Alert>
  )
}
