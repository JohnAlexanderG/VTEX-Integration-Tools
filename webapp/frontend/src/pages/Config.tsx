import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Save, Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react'
import { fetchConfig, updateConfig } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Alert, Button, Card, Input, Label, PageHeader, Skeleton, useToast } from '../components/ui'

const VTEX_FIELDS = [
  {
    key: 'X-VTEX-API-AppKey',
    label: 'App Key',
    type: 'text',
    placeholder: 'vtexappkey-...',
    help: 'Clave de aplicación VTEX API',
  },
  {
    key: 'X-VTEX-API-AppToken',
    label: 'App Token',
    type: 'password',
    placeholder: '●●●●●●●●',
    help: 'Token de aplicación VTEX API (se guarda encriptado)',
  },
  {
    key: 'VTEX_ACCOUNT_NAME',
    label: 'Account Name',
    type: 'text',
    placeholder: 'mitienda',
    help: 'Nombre de cuenta VTEX (sin .vtexcommercestable.com)',
  },
  {
    key: 'VTEX_ENVIRONMENT',
    label: 'Environment',
    type: 'text',
    placeholder: 'vtexcommercestable',
    help: 'Entorno VTEX (por defecto: vtexcommercestable)',
  },
]

const INVENTORY_DELIVERY_FIELDS = [
  {
    key: 'FTP_SERVER',
    label: 'FTP Server',
    type: 'text',
    placeholder: 'ftp.midominio.com',
    help: 'Servidor FTP para cargar el archivo NDJSON de inventario',
  },
  {
    key: 'FTP_USER',
    label: 'FTP User',
    type: 'text',
    placeholder: 'usuario_ftp',
    help: 'Usuario del servidor FTP',
  },
  {
    key: 'FTP_PASSWORD',
    label: 'FTP Password',
    type: 'password',
    placeholder: '●●●●●●●●',
    help: 'Contraseña FTP (se guarda encriptada)',
  },
  {
    key: 'FTP_PORT',
    label: 'FTP Port',
    type: 'text',
    placeholder: '21',
    help: 'Puerto FTP (por defecto: 21)',
  },
  {
    key: 'LAMBDA1_FUNCTION_NAME',
    label: 'Lambda Function',
    type: 'text',
    placeholder: 'demo-lambda',
    help: 'Nombre de la Lambda que se invoca después de subir el archivo',
  },
  {
    key: 'AWS_REGION',
    label: 'AWS Region',
    type: 'text',
    placeholder: 'us-east-1',
    help: 'Región AWS donde vive la Lambda',
  },
]

function ConfigField({
  field,
  value,
  showSecret,
  onToggleSecret,
  onChange,
}: {
  field: { key: string; label: string; type: string; placeholder: string; help: string }
  value: string
  showSecret: boolean
  onToggleSecret: () => void
  onChange: (value: string) => void
}) {
  const isPassword = field.type === 'password'

  return (
    <div>
      <Label htmlFor={field.key}>
        {field.label}
        <span className="text-ink-4 ml-2 font-normal block sm:inline mt-0.5 sm:mt-0">
          {field.help}
        </span>
      </Label>
      <Input
        id={field.key}
        type={isPassword && !showSecret ? 'password' : 'text'}
        value={value}
        placeholder={field.placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="font-mono"
        rightSlot={
          isPassword ? (
            <button
              type="button"
              onClick={onToggleSecret}
              aria-label={showSecret ? 'Ocultar valor' : 'Mostrar valor'}
              className="text-ink-4 hover:text-ink-2"
            >
              {showSecret ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          ) : undefined
        }
      />
    </div>
  )
}

export default function Config() {
  const { hasSectionAccess } = useAuth()
  const configAllowed = hasSectionAccess('config')
  const toast = useToast()
  const [values, setValues] = useState<Record<string, string>>({})
  const [showVtexToken, setShowVtexToken] = useState(false)
  const [showFtpPassword, setShowFtpPassword] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [ftpConfigured, setFtpConfigured] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!configAllowed) {
      setLoading(false)
      return
    }
    fetchConfig()
      .then((c) => {
        setValues(c.values)
        setConfigured(c.configured)
        setFtpConfigured(Boolean(c.values.FTP_SERVER && c.values.FTP_USER && c.values.FTP_PASSWORD))
      })
      .finally(() => setLoading(false))
  }, [configAllowed])

  const handleSave = async () => {
    setError(null)
    try {
      // Don't save masked token value
      const toSave = { ...values }
      if (toSave['X-VTEX-API-AppToken']?.includes('●')) {
        delete toSave['X-VTEX-API-AppToken']
      }
      await updateConfig(toSave)
      toast.success('Configuración guardada correctamente.')
      // Refresh to get updated masked values
      const c = await fetchConfig()
      setValues(c.values)
      setConfigured(c.configured)
      setFtpConfigured(Boolean(c.values.FTP_SERVER && c.values.FTP_USER && c.values.FTP_PASSWORD))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 max-w-3xl space-y-4">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (!configAllowed) {
    return <Navigate to="/tools" replace />
  }

  return (
    <div className="p-4 md:p-6 max-w-3xl">
      <PageHeader
        title="Configuración"
        description={
          <>
            Configura credenciales VTEX y del envío de inventario sin editar manualmente el archivo{' '}
            <code className="text-ink-3">.env</code>.
          </>
        }
      />

      <div className="space-y-2 mb-5 md:mb-6">
        <div className="flex items-start gap-2">
          {configured ? (
            <>
              <CheckCircle size={16} className="text-green-400 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-green-400">Credenciales VTEX configuradas correctamente</span>
            </>
          ) : (
            <>
              <XCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-red-400">
                Credenciales VTEX incompletas — algunas herramientas VTEX no funcionarán
              </span>
            </>
          )}
        </div>
        <div className="flex items-start gap-2">
          {ftpConfigured ? (
            <>
              <CheckCircle size={16} className="text-green-400 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-green-400">Envío de inventario configurado correctamente</span>
            </>
          ) : (
            <>
              <XCircle size={16} className="text-yellow-400 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-yellow-400">
                Faltan credenciales del envío de inventario — no se podrá enviar por FTP
              </span>
            </>
          )}
        </div>
      </div>

      <Card className="mb-5 md:mb-6">
        <h2 className="text-sm font-semibold text-ink-1">VTEX</h2>
        <p className="text-xs text-ink-4 mt-1 mb-4">
          Credenciales principales para consultas, mapeos y operaciones sobre VTEX.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {VTEX_FIELDS.map((field) => (
            <ConfigField
              key={field.key}
              field={field}
              value={values[field.key] ?? ''}
              showSecret={showVtexToken}
              onToggleSecret={() => setShowVtexToken((v) => !v)}
              onChange={(value) => setValues((prev) => ({ ...prev, [field.key]: value }))}
            />
          ))}
        </div>
      </Card>

      <Card className="mb-5 md:mb-6">
        <h2 className="text-sm font-semibold text-ink-1">FTP &amp; Lambda de inventario</h2>
        <p className="text-xs text-ink-4 mt-1 mb-4">
          Configuración usada para subir el NDJSON por FTP e invocar la Lambda posterior.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {INVENTORY_DELIVERY_FIELDS.map((field) => (
            <ConfigField
              key={field.key}
              field={field}
              value={values[field.key] ?? ''}
              showSecret={showFtpPassword}
              onToggleSecret={() => setShowFtpPassword((v) => !v)}
              onChange={(value) => setValues((prev) => ({ ...prev, [field.key]: value }))}
            />
          ))}
        </div>
      </Card>

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <Button icon={Save} onClick={handleSave}>
        Guardar cambios
      </Button>

      {/* Info */}
      <div className="mt-5 md:mt-6 bg-surface-1/50 border border-line-1 rounded-control p-4 text-xs text-ink-4 space-y-1">
        <p>
          <span className="text-ink-3 font-medium">Archivo .env:</span>{' '}
          {`${window.location.hostname === 'localhost' ? '<proyecto>/.env' : '.env'}`}
        </p>
        <p>Las credenciales se guardan por tenant y son leídas automáticamente por el backend y los scripts Python.</p>
        <p>Los secretos sensibles como tokens y contraseñas se almacenan cifrados.</p>
      </div>
    </div>
  )
}
