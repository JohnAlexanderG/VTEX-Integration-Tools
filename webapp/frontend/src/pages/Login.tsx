import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

interface TenantOption {
  slug: string
  name: string
}

export default function Login() {
  const { login, user } = useAuth()
  const navigate        = useNavigate()

  const [tenants,      setTenants]      = useState<TenantOption[]>([])
  const [tenantSlug,   setTenantSlug]   = useState('')
  const [username,     setUsername]     = useState('')
  const [password,     setPassword]     = useState('')
  const [error,        setError]        = useState('')
  const [loading,      setLoading]      = useState(false)
  const [loadingTenants, setLoadingTenants] = useState(true)

  // Si ya está autenticado, redirigir
  useEffect(() => {
    if (user) navigate('/pipeline', { replace: true })
  }, [user, navigate])

  // Cargar tenants disponibles
  useEffect(() => {
    fetch('/auth/tenants')
      .then(r => r.json())
      .then(d => {
        setTenants(d.tenants || [])
        if (d.tenants?.length === 1) setTenantSlug(d.tenants[0].slug)
      })
      .catch(() => setError('Error al conectar con el servidor'))
      .finally(() => setLoadingTenants(false))
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await fetch('/auth/login', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ username, password, tenant_slug: tenantSlug }),
      })
      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'Credenciales incorrectas')
        return
      }

      login(data.access_token, data.user)
      navigate('/pipeline', { replace: true })
    } catch {
      setError('Error de red. Verifica tu conexión.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo / título */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-600 mb-4">
            <svg className="w-9 h-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white">VTEX Integration Tools</h1>
          <p className="text-gray-400 text-sm mt-1">Inicia sesión para continuar</p>
        </div>

        {/* Card */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-5">

            {/* Selector de cuenta (tenant) */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Cuenta
              </label>
              {loadingTenants ? (
                <div className="h-10 bg-gray-800 rounded-lg animate-pulse" />
              ) : (
                <select
                  value={tenantSlug}
                  onChange={e => setTenantSlug(e.target.value)}
                  required
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5
                             focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                             text-sm"
                >
                  <option value="">Selecciona una cuenta...</option>
                  {tenants.map(t => (
                    <option key={t.slug} value={t.slug}>{t.name}</option>
                  ))}
                </select>
              )}
            </div>

            {/* Usuario */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Usuario
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoComplete="username"
                placeholder="tu_usuario"
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5
                           focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                           text-sm placeholder-gray-500"
              />
            </div>

            {/* Contraseña */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5
                           focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                           text-sm placeholder-gray-500"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 bg-red-950 border border-red-800 text-red-300
                              rounded-lg px-3 py-2.5 text-sm">
                <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0
                       00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {error}
              </div>
            )}

            {/* Botón */}
            <button
              type="submit"
              disabled={loading || loadingTenants}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900
                         disabled:text-indigo-400 text-white font-medium rounded-lg py-2.5
                         transition-colors text-sm"
            >
              {loading ? 'Ingresando...' : 'Ingresar'}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-600 text-xs mt-6">
          Laburu Agencia © {new Date().getFullYear()}
        </p>
      </div>
    </div>
  )
}
