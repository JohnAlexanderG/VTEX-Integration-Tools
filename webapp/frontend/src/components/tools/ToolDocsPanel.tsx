import { Suspense, lazy, useMemo } from 'react'
import { FileText } from 'lucide-react'
import { useToolReadme } from '../../hooks/useToolReadme'
import { Alert, EmptyState, Skeleton } from '../ui'

// react-markdown solo lo paga esta vista, no el login ni el catálogo.
const Markdown = lazy(() => import('../ui/Markdown'))

/** Los 70 README abren con `# <nombre-carpeta>`, que duplica el header. */
function stripLeadingH1(source: string): string {
  return source.replace(/^\s*#\s+.*\n/, '')
}

export default function ToolDocsPanel({ toolId }: { toolId: string }) {
  const { markdown, loading, error } = useToolReadme(toolId)
  const body = useMemo(() => (markdown ? stripLeadingH1(markdown) : null), [markdown])

  if (loading) return <Skeleton className="h-4" count={8} />
  if (error) return <Alert tone="error">{error}</Alert>

  if (!body) {
    return (
      <EmptyState
        size="sm"
        icon={FileText}
        title="Sin documentación"
        description="Esta herramienta todavía no tiene un README asociado en el repositorio."
      />
    )
  }

  return (
    <div className="scrollbar-thin max-h-[70vh] overflow-y-auto pr-1 text-xs">
      <Suspense fallback={<Skeleton className="h-4" count={8} />}>
        <Markdown source={body} />
      </Suspense>
    </div>
  )
}
