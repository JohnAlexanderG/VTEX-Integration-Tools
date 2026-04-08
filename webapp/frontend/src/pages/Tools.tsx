import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import type { Tool } from '../types'
import { fetchTools, fetchConfig } from '../api/client'
import AccessDeniedModal from '../components/AccessDeniedModal'
import ToolCard from '../components/ToolCard'
import { useAuth } from '../context/AuthContext'

export default function Tools() {
  const { hasSectionAccess, isAdmin } = useAuth()
  const toolsAllowed = hasSectionAccess('tools')
  const [tools, setTools] = useState<Tool[]>([])
  const [vtexConfigured, setVtexConfigured] = useState(false)
  const [search, setSearch] = useState('')
  const [activeToolId, setActiveToolId] = useState<string | null>(null)
  const [showDeniedModal, setShowDeniedModal] = useState(false)

  useEffect(() => {
    fetchTools().then((all) => {
      setTools(all.filter((t) => t.category === 'tools'))
    })
    if (isAdmin) {
      fetchConfig().then((c) => setVtexConfigured(c.configured)).catch(() => setVtexConfigured(false))
    } else {
      setVtexConfigured(false)
    }
  }, [isAdmin])

  useEffect(() => {
    if (!toolsAllowed) setShowDeniedModal(true)
  }, [toolsAllowed])

  const filtered = tools.filter(
    (t) =>
      search === '' ||
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="p-4 md:p-6">
      <div className="mb-5 md:mb-6">
        <h1 className="text-xl font-bold text-gray-100">Herramientas</h1>
        <p className="text-sm text-gray-500 mt-1">Utilidades individuales para transformación y gestión de datos.</p>
      </div>

      {/* Search */}
      <div className="relative mb-5 md:mb-6 max-w-md">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          type="text"
          placeholder="Buscar herramienta…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-vtex-pink"
        />
      </div>

      {/* Tools grid */}
      <div className="space-y-4 max-w-3xl">
        {filtered.length === 0 && (
          <p className="text-sm text-gray-600">No se encontraron herramientas.</p>
        )}
        {filtered.map((tool) => {
          const isOpen = activeToolId === tool.id
          return (
            <div key={tool.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <button
                onClick={() => {
                  if (!toolsAllowed || tool.enabled === false) {
                    setShowDeniedModal(true)
                    return
                  }
                  setActiveToolId(isOpen ? null : tool.id)
                }}
                className="w-full flex items-center justify-between gap-3 px-4 md:px-5 py-3 md:py-4 text-left hover:bg-gray-800/40 transition-colors"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-100">{tool.shortName}</span>
                    {tool.requires_vtex && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-vtex-pink/20 text-vtex-pink rounded font-medium">
                        VTEX API
                      </span>
                    )}
                    {tool.enabled === false && (
                      <span className="rounded border border-red-800 bg-red-950 px-1.5 py-0.5 text-[10px] font-medium text-red-300">
                        Bloqueado
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 truncate mt-0.5">{tool.description}</p>
                </div>
                <span className="text-gray-600 flex-shrink-0">{isOpen ? '▲' : '▼'}</span>
              </button>

              {isOpen && (
                <div className="border-t border-gray-800 p-4 md:p-5">
                  <ToolCard
                    tool={tool}
                    vtexConfigured={vtexConfigured}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>

      <AccessDeniedModal
        open={showDeniedModal}
        title="Herramientas bloqueadas"
        message="Tu cuenta no tiene permisos para acceder a esta sección o a alguna de sus herramientas. Solicita la habilitación desde Laburu Agencia."
        onClose={() => setShowDeniedModal(false)}
      />
    </div>
  )
}
