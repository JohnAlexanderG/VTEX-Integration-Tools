import { Link } from 'react-router-dom'
import { ChevronRight, FileText } from 'lucide-react'
import type { Job, Tool } from '../../types'
import { Badge, Card, cn } from '../ui'
import { iconForTool } from './toolIcons'

interface Props {
  tool: Tool
  activeJob?: Job
}

export default function ToolCatalogCard({ tool, activeJob }: Props) {
  const Icon = iconForTool(tool)
  const isRunning = activeJob?.status === 'running' || activeJob?.status === 'pending'

  return (
    <Link to={`/tools/${tool.id}`} state={{ tool }} className="block">
      <Card interactive padded={false} className="h-full p-4">
        <div className="flex items-start justify-between gap-3">
          <span
            className={cn(
              'flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-control',
              tool.requires_vtex ? 'bg-blue-900/40 text-blue-300' : 'bg-surface-2 text-ink-3',
            )}
          >
            <Icon size={16} />
          </span>
          <ChevronRight size={15} className="flex-shrink-0 text-ink-4" />
        </div>

        <p className="mt-3 text-sm font-semibold text-ink-1">{tool.shortName}</p>
        <p className="mt-1 text-xs leading-relaxed text-ink-4">{tool.description}</p>

        {(isRunning || tool.has_readme) && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {isRunning && (
              <Badge tone="info" pulse>
                Ejecutando
              </Badge>
            )}
            {tool.has_readme && (
              <span className="inline-flex items-center gap-1 text-[11px] text-ink-4">
                <FileText size={11} />
                Documentación
              </span>
            )}
          </div>
        )}
      </Card>
    </Link>
  )
}
