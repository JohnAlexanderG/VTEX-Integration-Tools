import { useEffect, useState } from 'react'
import { Save, Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react'
import { fetchConfig, updateConfig } from '../api/client'

const FIELDS = [
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

export default function Config() {
  const [values, setValues] = useState<Record<string, string>>({})
  const [showToken, setShowToken] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchConfig()
      .then((c) => {
        setValues(c.values)
        setConfigured(c.configured)
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
          Credenciales VTEX guardadas en el archivo <code className="text-gray-400">.env</code> del proyecto.
        </p>
      </div>

      {/* Status badge */}
      <div className="flex items-start gap-2 mb-5 md:mb-6">
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

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 md:p-5 space-y-5">
        {FIELDS.map((field) => (
          <div key={field.key}>
            <label className="block text-xs font-medium text-gray-400 mb-1">
              {field.label}
              <span className="text-gray-600 ml-2 font-normal block sm:inline mt-0.5 sm:mt-0">
                {field.help}
              </span>
            </label>
            <div className="relative">
              <input
                type={
                  field.type === 'password' && !showToken ? 'password' : 'text'
                }
                value={values[field.key] ?? ''}
                placeholder={field.placeholder}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                }
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 pr-10 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-vtex-pink focus:ring-1 focus:ring-vtex-pink font-mono"
              />
              {field.type === 'password' && (
                <button
                  type="button"
                  onClick={() => setShowToken((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                >
                  {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              )}
            </div>
          </div>
        ))}

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
        <p>Las credenciales son leídas automáticamente por todos los scripts Python.</p>
        <p>El token es almacenado en texto plano en el .env — trátalo como contraseña.</p>
      </div>
    </div>
  )
}
