import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import type { Tool } from '../types'
import { fetchTools, fetchVtexStatus, fetchJobs } from '../api/client'
import ToolCard from '../components/ToolCard'

export default function Tools() {
  const [tools, setTools] = useState<Tool[]>([])
  const [vtexConfigured, setVtexConfigured] = useState<boolean | null>(null)
  const [search, setSearch] = useState('')
  const [activeToolId, setActiveToolId] = useState<string | null>(null)
  const [activeJobsByTool, setActiveJobsByTool] = useState<Record<string, string>>({})

  useEffect(() => {
    fetchTools().then((all) => {
      setTools(
        all
          .filter((t) => t.enabled !== false)
          .sort((a, b) => {
            const stepA = a.step ?? Number.MAX_SAFE_INTEGER
            const stepB = b.step ?? Number.MAX_SAFE_INTEGER
            if (stepA !== stepB) return stepA - stepB
            return a.shortName.localeCompare(b.shortName, 'es')
          }),
      )
    })
    // /api/vtex-status es legible por cualquier rol; /api/config era admin-only
    // y dejaba a los operadores con el botón Ejecutar deshabilitado. Si falla,
    // queda en null: mostramos la UI habilitada y deja que el backend valide.
    fetchVtexStatus()
      .then((s) => setVtexConfigured(s.configured))
      .catch(() => setVtexConfigured(null))

    // Reenganchar jobs para cada tool: los que siguen corriendo en el servidor
    // (el usuario pudo recargar la página o colapsar la tarjeta sin que el job
    // terminara) y también los que ya terminaron mientras el usuario no miraba,
    // para no perder el acceso a sus archivos de salida. `fetchJobs()` ya viene
    // ordenado por fecha descendente, así que el primer job visto por tool_id
    // es siempre el más reciente.
    fetchJobs()
      .then((jobs) => {
        const byTool: Record<string, string> = {}
        for (const job of jobs) {
          if (!byTool[job.tool_id]) byTool[job.tool_id] = job.id
        }
        setActiveJobsByTool(byTool)

        // Solo autoabrir el acordeón si hay una ejecución realmente activa —
        // no forzar la apertura de tools cuya última corrida ya terminó.
        const runningJob = jobs.find((j) => j.status === 'running' || j.status === 'pending')
        if (runningJob) {
          setActiveToolId((prev) => prev ?? runningJob.tool_id)
        }
      })
      .catch(() => {})
  }, [])

  const filtered = tools.filter(
    (t) =>
      t.enabled !== false &&
      (search === '' ||
        t.name.toLowerCase().includes(search.toLowerCase()) ||
        t.description.toLowerCase().includes(search.toLowerCase())),
  )

  return (
    <div className="p-4 md:p-6">
      <div className="mb-5 md:mb-6">
        <h1 className="text-xl font-bold text-ink-1">Herramientas</h1>
        <p className="text-sm text-ink-4 mt-1">Utilidades individuales para transformación y gestión de datos.</p>
      </div>

      {/* Search */}
      <div className="relative mb-5 md:mb-6 max-w-md">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-4" />
        <input
          type="text"
          placeholder="Buscar herramienta…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 bg-surface-2 border border-line-2 rounded-lg text-sm text-ink-1 placeholder-ink-4 focus:outline-none focus:border-accent"
        />
      </div>

      {/* Tools grid */}
      <div className="space-y-4 max-w-3xl">
        {filtered.length === 0 && (
          <p className="text-sm text-ink-4">
            {tools.length === 0 ? 'No hay herramientas disponibles para tu cuenta.' : 'No se encontraron herramientas.'}
          </p>
        )}
        {filtered.map((tool) => {
          const isOpen = activeToolId === tool.id
          return (
            <div key={tool.id} className="bg-surface-1 border border-line-1 rounded-card overflow-hidden">
              <button
                onClick={() => {
                  setActiveToolId(isOpen ? null : tool.id)
                }}
                className="w-full flex items-center justify-between gap-3 px-4 md:px-5 py-3 md:py-4 text-left hover:bg-surface-2/40 transition-colors"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-ink-1">{tool.shortName}</span>
                    {tool.requires_vtex && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-accent/20 text-accent rounded font-medium">
                        VTEX API
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-ink-4 truncate mt-0.5">{tool.description}</p>
                </div>
                <span className="text-ink-4 flex-shrink-0">{isOpen ? '▲' : '▼'}</span>
              </button>

              {isOpen && (
                <div className="border-t border-line-1 p-4 md:p-5">
                  <ToolCard
                    tool={tool}
                    vtexConfigured={vtexConfigured}
                    resumeJobId={activeJobsByTool[tool.id]}
                    onJobStart={(jobId) =>
                      setActiveJobsByTool((prev) => ({ ...prev, [tool.id]: jobId }))
                    }
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
