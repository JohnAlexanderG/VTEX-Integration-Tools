import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Layers, Wrench, Settings, CheckCircle, XCircle, AlertCircle, Menu, X } from 'lucide-react'
import { fetchConfig } from '../api/client'

export default function Layout() {
  const [vtexOk, setVtexOk] = useState<boolean | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    fetchConfig()
      .then((c) => setVtexOk(c.configured))
      .catch(() => setVtexOk(false))
  }, [])

  // Close sidebar when route changes (mobile)
  const closeSidebar = () => setSidebarOpen(false)

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">

      {/* Mobile overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/60 md:hidden"
          onClick={closeSidebar}
        />
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
          {/* Close button — only on mobile */}
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
                isActive
                  ? 'bg-vtex-pink text-white'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
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
                isActive
                  ? 'bg-vtex-pink text-white'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
              }`
            }
          >
            <Wrench size={16} />
            Herramientas
          </NavLink>
          <NavLink
            to="/config"
            onClick={closeSidebar}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-vtex-pink text-white'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
              }`
            }
          >
            <Settings size={16} />
            Configuración
          </NavLink>
        </nav>

        {/* VTEX Status */}
        <div className="px-4 py-4 border-t border-gray-800">
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
        </div>
      </aside>

      {/* Main content */}
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
