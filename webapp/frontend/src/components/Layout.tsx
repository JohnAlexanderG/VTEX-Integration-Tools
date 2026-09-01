import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Wrench, History, Settings, CheckCircle, XCircle, AlertCircle, Menu, X, Users, LogOut, KeyRound } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useVtexStatus } from '../hooks/useVtexStatus'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  // /api/vtex-status lo puede leer cualquier rol; /api/config es admin-only y
  // dejaba a los operadores sin saber si VTEX estaba configurado.
  const { configured: vtexOk } = useVtexStatus()
  const { user, logout, isAdmin, isSuperAdmin, hasSectionAccess } = useAuth()
  const navigate                      = useNavigate()
  const hasToolsAccess = hasSectionAccess('tools')
  const hasHistoryAccess = hasSectionAccess('history')
  const hasConfigAccess = hasSectionAccess('config')
  const hasUsersAccess = hasSectionAccess('users')

  const closeSidebar = () => setSidebarOpen(false)

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  const roleLabel: Record<string, string> = {
    superadmin: 'Super Admin',
    admin:      'Admin',
    operator:   'Operador',
  }

  return (
    <div className="flex h-screen bg-surface-0 overflow-hidden">

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-20 bg-black/60 md:hidden" onClick={closeSidebar} />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-30 w-56 flex-shrink-0 bg-surface-1 border-r border-line-1 flex flex-col
          transform transition-transform duration-200 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:z-auto
        `}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-line-1 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-accent flex items-center justify-center text-white font-bold text-xs">
              VX
            </div>
            <span className="text-sm font-semibold text-ink-1 leading-tight">
              Integration<br />Tools
            </span>
          </div>
          <button
            onClick={closeSidebar}
            className="md:hidden text-ink-3 hover:text-ink-1 p-1 -mr-1"
            aria-label="Cerrar menú"
          >
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {hasToolsAccess && (
            <NavLink
              to="/tools"
              onClick={closeSidebar}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-accent text-white' : 'text-ink-3 hover:text-ink-1 hover:bg-surface-2'
                }`
              }
            >
              <Wrench size={16} />
              Herramientas
            </NavLink>
          )}

          {hasHistoryAccess && (
            <NavLink
              to="/jobs"
              onClick={closeSidebar}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-accent text-white' : 'text-ink-3 hover:text-ink-1 hover:bg-surface-2'
                }`
              }
            >
              <History size={16} />
              Historial
            </NavLink>
          )}

          {/* Solo admin/superadmin */}
          {isAdmin && (
            <>
              {hasConfigAccess && (
                <NavLink
                  to="/config"
                  onClick={closeSidebar}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive ? 'bg-accent text-white' : 'text-ink-3 hover:text-ink-1 hover:bg-surface-2'
                    }`
                  }
                >
                  <Settings size={16} />
                  Configuración
                </NavLink>
              )}

              {hasUsersAccess && (
                <NavLink
                  to="/users"
                  onClick={closeSidebar}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive ? 'bg-accent text-white' : 'text-ink-3 hover:text-ink-1 hover:bg-surface-2'
                    }`
                  }
                >
                  <Users size={16} />
                  Usuarios
                </NavLink>
              )}

              {isSuperAdmin && (
                <NavLink
                  to="/access"
                  onClick={closeSidebar}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive ? 'bg-accent text-white' : 'text-ink-3 hover:text-ink-1 hover:bg-surface-2'
                    }`
                  }
                >
                  <KeyRound size={16} />
                  Accesos
                </NavLink>
              )}
            </>
          )}
        </nav>

        {/* Footer: info de usuario + logout */}
        <div className="px-4 py-4 border-t border-line-1 space-y-3">
          {/* Estado de VTEX — visible para todos los roles */}
          {vtexOk !== null && (
            <div className="flex items-center gap-2 text-xs">
              {vtexOk === null ? (
                <AlertCircle size={14} className="text-ink-4" />
              ) : vtexOk ? (
                <CheckCircle size={14} className="text-green-400" />
              ) : (
                <XCircle size={14} className="text-red-400" />
              )}
              <span className={vtexOk ? 'text-green-400' : 'text-ink-4'}>
                VTEX {vtexOk ? 'configurado' : 'no configurado'}
              </span>
            </div>
          )}

          {/* Info de usuario */}
          {user && (
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <p className="text-xs font-medium text-ink-2 truncate">{user.username}</p>
                <p className="text-[11px] text-ink-4">{roleLabel[user.role] ?? user.role}</p>
              </div>
              <button
                onClick={handleLogout}
                title="Cerrar sesión"
                className="ml-2 p-1.5 text-ink-4 hover:text-red-400 hover:bg-surface-2 rounded-lg transition-colors"
              >
                <LogOut size={15} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-surface-1 border-b border-line-1 flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-ink-3 hover:text-ink-1 p-1 -ml-1"
            aria-label="Abrir menú"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-accent flex items-center justify-center text-white font-bold text-[10px]">
              VX
            </div>
            <span className="text-sm font-semibold text-ink-1">Integration Tools</span>
          </div>
        </header>

        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
