import { useEffect, useState } from 'react'
import { Save, Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react'
import { fetchConfig, updateConfig } from '../api/client'

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

const PIPELINE_FIELDS = [
  {
    key: 'FTP_SERVER',
    label: 'FTP Server',
    type: 'text',
    placeholder: 'ftp.midominio.com',
    help: 'Servidor FTP para cargar el archivo NDJSON del pipeline',
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
      <label className="block text-xs font-medium text-gray-400 mb-1">
        {field.label}
        <span className="text-gray-600 ml-2 font-normal block sm:inline mt-0.5 sm:mt-0">
          {field.help}
        </span>
      </label>
      <div className="relative">
        <input
          type={isPassword && !showSecret ? 'password' : 'text'}
          value={value}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 pr-10 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-vtex-pink focus:ring-1 focus:ring-vtex-pink font-mono"
        />
        {isPassword && (
          <button
            type="button"
            onClick={onToggleSecret}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
          >
            {showSecret ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        )}
      </div>
    </div>
  )
}

export default function Config() {
  const [values, setValues] = useState<Record<string, string>>({})
  const [showVtexToken, setShowVtexToken] = useState(false)
  const [showFtpPassword, setShowFtpPassword] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [ftpConfigured, setFtpConfigured] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
      fetchConfig()
      .then((c) => {
        setValues(c.values)
        setConfigured(c.configured)
        setFtpConfigured(Boolean(c.values.FTP_SERVER && c.values.FTP_USER && c.values.FTP_PASSWORD))
      })
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setError(null)
    setSaved(false)
    try {
      // Don't save masked token value
      const toSave = { ...values }
      if (toSave['X-VTEX-API-AppToken']?.includes('●')) {
        delete toSave['X-VTEX-API-AppToken']
      }
      await updateConfig(toSave)
      setSaved(true)
      // Refresh to get updated masked values
      const c = await fetchConfig()
      setValues(c.values)
      setConfigured(c.configured)
      setFtpConfigured(Boolean(c.values.FTP_SERVER && c.values.FTP_USER && c.values.FTP_PASSWORD))
      setTimeout(() => setSaved(false), 3000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 text-sm text-gray-500">Cargando configuración…</div>
    )
  }

  return (
    <div className="p-4 md:p-6 max-w-xl">
      <div className="mb-5 md:mb-6">
        <h1 className="text-xl font-bold text-gray-100">Configuración</h1>
        <p className="text-sm text-gray-500 mt-1">
          Configura credenciales VTEX y del pipeline de inventario sin editar manualmente el archivo <code className="text-gray-400">.env</code>.
        </p>
      </div>

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
                Credenciales VTEX incompletas — algunos pasos del pipeline no funcionarán
              </span>
            </>
          )}
        </div>
        <div className="flex items-start gap-2">
          {ftpConfigured ? (
            <>
              <CheckCircle size={16} className="text-green-400 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-green-400">Pipeline de inventario configurado correctamente</span>
            </>
          ) : (
            <>
              <XCircle size={16} className="text-yellow-400 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-yellow-400">
                Faltan credenciales del pipeline de inventario — no se podrá enviar por FTP
              </span>
            </>
          )}
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 md:p-5 space-y-5">
        <div className="space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">VTEX</h2>
            <p className="text-xs text-gray-500 mt-1">
              Credenciales principales para consultas, mapeos y operaciones sobre VTEX.
            </p>
          </div>

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

        <div className="border-t border-gray-800 pt-5 space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Pipeline de Inventario</h2>
            <p className="text-xs text-gray-500 mt-1">
              Configuración usada para subir el NDJSON por FTP e invocar la Lambda posterior.
            </p>
          </div>

          {PIPELINE_FIELDS.map((field) => (
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

        {error && (
          <div className="text-xs text-red-400 bg-red-900/20 border border-red-800/50 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {saved && (
          <div className="text-xs text-green-400 bg-green-900/20 border border-green-800/50 rounded-lg px-3 py-2">
            Configuración guardada correctamente.
          </div>
        )}

        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-5 py-2 bg-vtex-pink hover:bg-pink-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Save size={14} />
          Guardar
        </button>
      </div>

      {/* Info */}
      <div className="mt-5 md:mt-6 bg-gray-900/50 border border-gray-800 rounded-lg p-4 text-xs text-gray-500 space-y-1">
        <p>
          <span className="text-gray-400 font-medium">Archivo .env:</span>{' '}
          {`${window.location.hostname === 'localhost' ? '<proyecto>/.env' : '.env'}`}
        </p>
        <p>Las credenciales se guardan por tenant y son leídas automáticamente por el backend y los scripts Python.</p>
        <p>Los secretos sensibles como tokens y contraseñas se almacenan cifrados.</p>
      </div>
    </div>
  )
}
