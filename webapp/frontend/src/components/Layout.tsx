import { useState, useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Layers, Wrench, Settings, CheckCircle, XCircle, AlertCircle, Menu, X, Users, LogOut, KeyRound } from 'lucide-react'
import { fetchConfig } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const [vtexOk, setVtexOk]         = useState<boolean | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, logout, isAdmin, isSuperAdmin } = useAuth()
  const navigate                      = useNavigate()

  useEffect(() => {
    if (isAdmin) {
      fetchConfig()
        .then((c) => setVtexOk(c.configured))
        .catch(() => setVtexOk(false))
    }
  }, [isAdmin])

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
    <div className="flex h-screen bg-gray-950 overflow-hidden">

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-20 bg-black/60 md:hidden" onClick={closeSidebar} />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-30 w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col
          transform transition-transform duration-200 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:z-auto
        `}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-vtex-pink flex items-center justify-center text-white font-bold text-xs">
              VX
            </div>
            <span className="text-sm font-semibold text-gray-100 leading-tight">
              Integration<br />Tools
            </span>
          </div>
          <button
            onClick={closeSidebar}
            className="md:hidden text-gray-400 hover:text-gray-100 p-1 -mr-1"
            aria-label="Cerrar menú"
          >
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          <NavLink
            to="/pipeline"
            onClick={closeSidebar}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive ? 'bg-vtex-pink text-white' : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
              }`
            }
          >
            <Layers size={16} />
            Pipeline
          </NavLink>

          <NavLink
            to="/tools"
            onClick={closeSidebar}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive ? 'bg-vtex-pink text-white' : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
              }`
            }
          >
            <Wrench size={16} />
            Herramientas
          </NavLink>

          {/* Solo admin/superadmin */}
          {isAdmin && (
            <>
              <NavLink
                to="/config"
                onClick={closeSidebar}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive ? 'bg-vtex-pink text-white' : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                  }`
                }
              >
                <Settings size={16} />
                Configuración
              </NavLink>

              <NavLink
                to="/users"
                onClick={closeSidebar}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive ? 'bg-vtex-pink text-white' : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                  }`
                }
              >
                <Users size={16} />
                Usuarios
              </NavLink>

              {isSuperAdmin && (
                <NavLink
                  to="/access"
                  onClick={closeSidebar}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive ? 'bg-vtex-pink text-white' : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
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
        <div className="px-4 py-4 border-t border-gray-800 space-y-3">
          {/* VTEX status (solo admin) */}
          {isAdmin && (
            <div className="flex items-center gap-2 text-xs">
              {vtexOk === null ? (
                <AlertCircle size={14} className="text-gray-500" />
              ) : vtexOk ? (
                <CheckCircle size={14} className="text-green-400" />
              ) : (
                <XCircle size={14} className="text-red-400" />
              )}
              <span className={vtexOk ? 'text-green-400' : 'text-gray-500'}>
                VTEX {vtexOk ? 'configurado' : 'no configurado'}
              </span>
            </div>
          )}

          {/* Info de usuario */}
          {user && (
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <p className="text-xs font-medium text-gray-200 truncate">{user.username}</p>
                <p className="text-[11px] text-gray-500">{roleLabel[user.role] ?? user.role}</p>
              </div>
              <button
                onClick={handleLogout}
                title="Cerrar sesión"
                className="ml-2 p-1.5 text-gray-500 hover:text-red-400 hover:bg-gray-800 rounded-lg transition-colors"
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
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-gray-900 border-b border-gray-800 flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-gray-400 hover:text-gray-100 p-1 -ml-1"
            aria-label="Abrir menú"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-vtex-pink flex items-center justify-center text-white font-bold text-[10px]">
              VX
            </div>
            <span className="text-sm font-semibold text-gray-100">Integration Tools</span>
          </div>
        </header>

        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
