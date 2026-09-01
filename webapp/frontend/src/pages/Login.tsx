import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Zap } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { Alert, Button, Field, Input, Select, Skeleton } from '../components/ui'

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
    if (user) navigate('/tools', { replace: true })
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
      navigate('/tools', { replace: true })
    } catch {
      setError('Error de red. Verifica tu conexión.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-0 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo / título */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-card bg-accent mb-4">
            <Zap size={34} className="text-accent-fg" strokeWidth={1.8} />
          </div>
          <h1 className="text-2xl font-bold text-ink-1">VTEX Integration Tools</h1>
          <p className="text-ink-3 text-sm mt-1">Inicia sesión para continuar</p>
        </div>

        {/* Card */}
        <div className="bg-surface-1 border border-line-1 rounded-card p-8 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-5">

            {/* Selector de cuenta (tenant) */}
            <Field label="Cuenta" htmlFor="tenant">
              {loadingTenants ? (
                <Skeleton className="h-10" />
              ) : (
                <Select
                  id="tenant"
                  value={tenantSlug}
                  onChange={e => setTenantSlug(e.target.value)}
                  required
                >
                  <option value="">Selecciona una cuenta...</option>
                  {tenants.map(t => (
                    <option key={t.slug} value={t.slug}>{t.name}</option>
                  ))}
                </Select>
              )}
            </Field>

            <Field label="Usuario" htmlFor="username">
              <Input
                id="username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoComplete="username"
                placeholder="tu_usuario"
              />
            </Field>

            <Field label="Contraseña" htmlFor="password">
              <Input
                id="password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
              />
            </Field>

            {error && <Alert tone="error">{error}</Alert>}

            <Button type="submit" fullWidth loading={loading} disabled={loadingTenants}>
              {loading ? 'Ingresando…' : 'Ingresar'}
            </Button>
          </form>
        </div>

        <p className="text-center text-ink-4 text-xs mt-6">
          Laburu Agencia © {new Date().getFullYear()}
        </p>
      </div>
    </div>
  )
}
