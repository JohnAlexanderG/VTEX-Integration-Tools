import { useEffect, useMemo, useState } from 'react'
import { Cloud, Search, Wrench } from 'lucide-react'
import type { Tool } from '../types'
import { fetchTools } from '../api/client'
import { useActiveJobs } from '../hooks/useActiveJobs'
import ToolCatalogCard from '../components/tools/ToolCatalogCard'
import { Alert, EmptyState, Input, PageHeader, Skeleton, cn } from '../components/ui'

type CategoryFilter = 'all' | 'vtex' | 'utility'

const FILTERS: Array<{ id: CategoryFilter; label: string }> = [
  { id: 'all', label: 'Todas' },
  { id: 'vtex', label: 'API VTEX' },
  { id: 'utility', label: 'Utilidades' },
]

function sortTools(tools: Tool[]): Tool[] {
  return [...tools].sort((a, b) => {
    const stepA = a.step ?? Number.MAX_SAFE_INTEGER
    const stepB = b.step ?? Number.MAX_SAFE_INTEGER
    if (stepA !== stepB) return stepA - stepB
    return a.shortName.localeCompare(b.shortName, 'es')
  })
}

export default function ToolsCatalog() {
  const [tools, setTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<CategoryFilter>('all')
  const { jobsByTool } = useActiveJobs()

  useEffect(() => {
    fetchTools()
      .then((all) => setTools(sortTools(all.filter((t) => t.enabled !== false))))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : 'No se pudieron cargar las herramientas'),
      )
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    return tools.filter((t) => {
      if (filter === 'vtex' && !t.requires_vtex) return false
      if (filter === 'utility' && t.requires_vtex) return false
      if (!term) return true
      // shortName va incluido: es lo que muestra la tarjeta, y antes buscar lo
      // que estabas viendo no devolvía nada.
      return (
        t.shortName.toLowerCase().includes(term) ||
        t.name.toLowerCase().includes(term) ||
        t.description.toLowerCase().includes(term)
      )
    })
  }, [tools, search, filter])

  const vtexTools = filtered.filter((t) => t.requires_vtex)
  const utilityTools = filtered.filter((t) => !t.requires_vtex)

  const renderSection = (
    key: string,
    title: string,
    hint: string,
    icon: typeof Cloud,
    accentClass: string,
    items: Tool[],
  ) => {
    if (items.length === 0) return null
    const Icon = icon
    return (
      <section key={key} className="mb-8 last:mb-0">
        <div className="mb-3 flex items-center gap-2.5">
          <span className={cn('flex h-7 w-7 items-center justify-center rounded-control', accentClass)}>
            <Icon size={14} />
          </span>
          <h2 className="text-sm font-bold text-ink-1">{title}</h2>
          <span className="text-xs text-ink-4">{hint}</span>
          <span className="ml-auto text-xs text-ink-4">{items.length}</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((tool) => (
            <ToolCatalogCard key={tool.id} tool={tool} activeJob={jobsByTool[tool.id]} />
          ))}
        </div>
      </section>
    )
  }

  return (
    <div className="p-4 md:p-6">
      <PageHeader
        title="Herramientas"
        description="Elegí una herramienta para ver su documentación y ejecutarla."
      />

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5 rounded-control border border-line-1 bg-surface-1 p-1">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={cn(
                'rounded-control px-3.5 py-1.5 text-xs font-semibold',
                filter === f.id ? 'bg-accent text-accent-fg' : 'text-ink-3 hover:text-ink-1',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="w-full sm:w-80">
          <Input
            type="text"
            leftIcon={Search}
            placeholder="Buscar herramienta…"
            aria-label="Buscar herramienta"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Wrench}
          title={tools.length === 0 ? 'No hay herramientas disponibles' : 'Sin resultados'}
          description={
            tools.length === 0
              ? 'Tu cuenta no tiene herramientas habilitadas. Pedile acceso a un administrador.'
              : 'Probá con otro término o cambiá el filtro de categoría.'
          }
        />
      ) : (
        <>
          {renderSection(
            'vtex',
            'API VTEX',
            'se conectan a la API',
            Cloud,
            'bg-blue-900/40 text-blue-300',
            vtexTools,
          )}
          {renderSection(
            'utility',
            'Utilidades',
            'transformación local',
            Wrench,
            'bg-surface-2 text-ink-3',
            utilityTools,
          )}
        </>
      )}
    </div>
  )
}
