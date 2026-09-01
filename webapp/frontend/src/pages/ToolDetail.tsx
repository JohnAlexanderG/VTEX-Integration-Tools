import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { Wrench } from 'lucide-react'
import type { JobStatus, Tool } from '../types'
import { ApiError, fetchTool } from '../api/client'
import { useActiveJobs } from '../hooks/useActiveJobs'
import { useVtexStatus } from '../hooks/useVtexStatus'
import StatusBadge from '../components/StatusBadge'
import ToolRunPanel from '../components/tools/ToolRunPanel'
import ToolDocsPanel from '../components/tools/ToolDocsPanel'
import { iconForTool } from '../components/tools/toolIcons'
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  PageHeader,
  Skeleton,
  cn,
} from '../components/ui'

export default function ToolDetail() {
  const { toolId = '' } = useParams()
  const location = useLocation()
  // El catálogo pasa la herramienta por state: el header pinta al instante.
  // Un deep link o un F5 la resuelven igual con fetchTool.
  const seed = (location.state as { tool?: Tool } | null)?.tool
  const [tool, setTool] = useState<Tool | null>(seed?.id === toolId ? seed : null)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<JobStatus | null>(null)

  const { configured } = useVtexStatus()
  const { jobsByTool } = useActiveJobs(toolId)
  const resumeJobId = jobsByTool[toolId]?.id ?? null

  useEffect(() => {
    if (!toolId) return
    let cancelled = false
    setNotFound(false)
    setError(null)
    fetchTool(toolId)
      .then((t) => {
        if (!cancelled) setTool(t)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        // El backend responde 404 tanto si no existe como si el tenant no
        // tiene permiso: ese es el gate real de esta ruta.
        if (e instanceof ApiError && e.status === 404) setNotFound(true)
        else setError(e instanceof Error ? e.message : 'No se pudo cargar la herramienta')
      })
    return () => {
      cancelled = true
    }
  }, [toolId])

  const handleStatusChange = useCallback((next: JobStatus | null) => setStatus(next), [])

  if (notFound) {
    return (
      <div className="p-4 md:p-6">
        <EmptyState
          icon={Wrench}
          title="Herramienta no disponible"
          description="No existe o tu cuenta no tiene acceso a esta herramienta."
          action={
            <Link to="/tools">
              <Button variant="secondary">Volver al catálogo</Button>
            </Link>
          }
        />
      </div>
    )
  }

  if (!tool) {
    return (
      <div className="p-4 md:p-6 space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        <Skeleton className="h-10 w-72" />
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,44%)]">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    )
  }

  const Icon = iconForTool(tool)

  return (
    <div className="p-4 md:p-6">
      <PageHeader
        backTo="/tools"
        backLabel="Herramientas"
        title={tool.shortName}
        badge={
          <>
            <Badge tone={tool.requires_vtex ? 'info' : 'neutral'}>
              {tool.requires_vtex ? 'API VTEX' : 'Utilidad'}
            </Badge>
            <StatusBadge status={status} />
          </>
        }
        description={
          <span className="flex items-start gap-2.5">
            <span
              className={cn(
                'mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-control',
                tool.requires_vtex ? 'bg-blue-900/40 text-blue-300' : 'bg-surface-2 text-ink-3',
              )}
            >
              <Icon size={14} />
            </span>
            <span className="max-w-2xl">{tool.description}</span>
          </span>
        }
      />

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,44%)] xl:items-start">
        <Card className="min-w-0">
          <CardHeader title="Ejecutar" />
          <ToolRunPanel
            tool={tool}
            vtexConfigured={configured}
            resumeJobId={resumeJobId}
            onStatusChange={handleStatusChange}
          />
        </Card>

        <Card className="min-w-0 xl:sticky xl:top-6">
          <CardHeader title="Documentación" subtitle="Cómo funciona y cómo se usa esta herramienta." />
          <ToolDocsPanel toolId={tool.id} />
        </Card>
      </div>
    </div>
  )
}
