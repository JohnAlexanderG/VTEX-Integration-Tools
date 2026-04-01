import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

export type UserRole = 'superadmin' | 'admin' | 'operator'

export interface AuthUser {
  id:          number
  username:    string
  email:       string | null
  role:        UserRole
  tenant_id:   number
  tenant_slug: string
  tenant_name: string
}

interface AuthState {
  user:    AuthUser | null
  token:   string | null
  loading: boolean
}

interface AuthContextValue extends AuthState {
  login:  (token: string, user: AuthUser) => void
  logout: () => void
  isAdmin:      boolean
  isSuperAdmin: boolean
}

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null)

const TOKEN_KEY = 'vtex_token'
const USER_KEY  = 'vtex_user'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user:    null,
    token:   null,
    loading: true,
  })

  // Restaurar sesión guardada al cargar
  useEffect(() => {
    const token = sessionStorage.getItem(TOKEN_KEY)
    const raw   = sessionStorage.getItem(USER_KEY)
    if (token && raw) {
      try {
        const user: AuthUser = JSON.parse(raw)
        setState({ user, token, loading: false })
        return
      } catch {
        // datos corruptos → limpiar
        sessionStorage.removeItem(TOKEN_KEY)
        sessionStorage.removeItem(USER_KEY)
      }
    }
    setState(s => ({ ...s, loading: false }))
  }, [])

  function login(token: string, user: AuthUser) {
    sessionStorage.setItem(TOKEN_KEY, token)
    sessionStorage.setItem(USER_KEY, JSON.stringify(user))
    setState({ user, token, loading: false })
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
    setState({ user: null, token: null, loading: false })
  }

  const isAdmin      = state.user?.role === 'admin' || state.user?.role === 'superadmin'
  const isSuperAdmin = state.user?.role === 'superadmin'

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAdmin, isSuperAdmin }}>
      {children}
    </AuthContext.Provider>
  )
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
