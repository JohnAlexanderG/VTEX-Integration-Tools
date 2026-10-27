import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Zap } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { loginWithEmail, selectAccount, type AccountSummary } from '../api/client'
import AccountList from '../components/AccountList'
import { Alert, Button, Field, Input } from '../components/ui'

interface Selection {
  token:    string
  accounts: AccountSummary[]
}

export default function Login() {
  const { login, user } = useAuth()
  const navigate        = useNavigate()

  const [email,     setEmail]     = useState('')
  const [password,  setPassword]  = useState('')
  const [error,     setError]     = useState('')
  const [loading,   setLoading]   = useState(false)
  // Paso 2: el email pertenece a varias cuentas y hay que elegir una
  const [selection, setSelection] = useState<Selection | null>(null)
  const [pendingId, setPendingId] = useState<number | null>(null)

  // Si ya está autenticado, redirigir
  useEffect(() => {
    if (user) navigate('/tools', { replace: true })
  }, [user, navigate])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const data = await loginWithEmail(email, password)
      if ('requires_account_selection' in data) {
        setSelection({ token: data.selection_token, accounts: data.accounts })
        return
      }
      login(data.access_token, data.user)
      navigate('/tools', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de red. Verifica tu conexión.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSelect(account: AccountSummary) {
    if (!selection) return
    setError('')
    setPendingId(account.user_id)
    try {
      const data = await selectAccount(selection.token, account.user_id)
      login(data.access_token, data.user)
      navigate('/tools', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo seleccionar la cuenta')
    } finally {
      setPendingId(null)
    }
  }

  function backToCredentials() {
    setSelection(null)
    setPassword('')
    setError('')
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
          <p className="text-ink-3 text-sm mt-1">
            {selection ? 'Elige la cuenta con la que quieres entrar' : 'Inicia sesión para continuar'}
          </p>
        </div>

        {/* Card */}
        <div className="bg-surface-1 border border-line-1 rounded-card p-8 shadow-xl">
          {selection ? (
            <div className="space-y-5">
              <p className="text-xs text-ink-4 truncate">{email}</p>

              <AccountList accounts={selection.accounts} onSelect={handleSelect} pendingId={pendingId} />

              {error && <Alert tone="error">{error}</Alert>}

              <Button variant="ghost" fullWidth onClick={backToCredentials} disabled={pendingId !== null}>
                <ArrowLeft size={15} /> Usar otro correo
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <Field label="Correo" htmlFor="email">
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  placeholder="tu@correo.com"
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

              <Button type="submit" fullWidth loading={loading}>
                {loading ? 'Ingresando…' : 'Ingresar'}
              </Button>
            </form>
          )}
        </div>

        <p className="text-center text-ink-4 text-xs mt-6">
          Laburu Agencia © {new Date().getFullYear()}
        </p>
      </div>
    </div>
  )
}
